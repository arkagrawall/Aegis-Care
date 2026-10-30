package com.aegis.saathi.ble

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Log
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.util.UUID

/**
 * Real Bluetooth LE connection to the senior's watch, built to stay connected:
 *  - remembers the paired watch and reconnects after disconnects, Bluetooth toggles and app restarts
 *    (exponential back-off 2 s -> 60 s, then Android's own background auto-connect),
 *  - a watchdog re-opens the connection if it was lost silently,
 *  - GATT operations are queued one at a time (Android drops parallel descriptor writes),
 *  - standard heart-rate and battery services are decoded; vendor packets are logged raw.
 *
 * Process-wide singleton: the background service keeps the process (and so this connection) alive.
 */
@SuppressLint("MissingPermission")
class WatchManager private constructor(private val app: Context) {

    companion object {
        private const val TAG = "WatchManager"

        @Volatile
        private var instance: WatchManager? = null

        fun get(context: Context): WatchManager =
            instance ?: synchronized(this) {
                instance ?: WatchManager(context.applicationContext).also { instance = it }
            }

        /** Runtime permissions needed to scan for and talk to a watch. */
        fun requiredPermissions(): Array<String> =
            if (Build.VERSION.SDK_INT >= 31)
                arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
            else
                arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
    }

    private val main = Handler(Looper.getMainLooper())
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private val adapter: BluetoothAdapter? =
        (app.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager)?.adapter

    private var gatt: BluetoothGatt? = null
    private var wantConnected = false
    private var attempts = 0
    private var started = false
    private var demoJob: Job? = null

    private val found = LinkedHashMap<String, ScanDevice>()
    private var scanCallback: ScanCallback? = null

    // A busy street reports dozens of adverts a second; publishing each one rebuilt the device list on the
    // main thread until Android killed the app (ANR). The list is published at most every 500 ms instead.
    private val publishDevices = Runnable {
        publishPending = false
        WatchRepository.setDevices(
            found.values.sortedWith(compareByDescending<ScanDevice> { it.likelyWatch }.thenByDescending { it.rssi })
        )
    }
    private var publishPending = false

    // ---------------------------------------------------------------------------- capability checks
    fun hasBle(): Boolean = app.packageManager.hasSystemFeature(PackageManager.FEATURE_BLUETOOTH_LE) && adapter != null
    fun isBluetoothOn(): Boolean = try { adapter?.isEnabled == true } catch (e: SecurityException) { false }

    fun hasPermissions(): Boolean = requiredPermissions().all {
        ContextCompat.checkSelfPermission(app, it) == PackageManager.PERMISSION_GRANTED
    }

    private fun canConnect(): Boolean =
        if (Build.VERSION.SDK_INT >= 31)
            ContextCompat.checkSelfPermission(app, Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED
        else true

    // ----------------------------------------------------------------------------------- lifecycle
    /** Call whenever the app/service starts: resumes the saved watch and keeps it connected. */
    fun start() {
        if (started) {
            if (wantConnected && WatchRepository.state.value.link != WatchLink.CONNECTED && gatt == null) reopen()
            return
        }
        started = true
        try {
            app.registerReceiver(object : BroadcastReceiver() {
                override fun onReceive(context: Context?, intent: Intent?) {
                    when (intent?.getIntExtra(BluetoothAdapter.EXTRA_STATE, -1)) {
                        BluetoothAdapter.STATE_ON -> if (wantConnected) { attempts = 0; reopen() }
                        BluetoothAdapter.STATE_OFF -> {
                            closeGatt()
                            WatchRepository.update { it.copy(link = if (wantConnected) WatchLink.RECONNECTING else WatchLink.NONE) }
                        }
                    }
                }
            }, IntentFilter(BluetoothAdapter.ACTION_STATE_CHANGED))
        } catch (e: Exception) {
            Log.w(TAG, "Bluetooth state receiver not registered: ${e.message}")
        }

        val saved = WatchRepository.savedAddress(app)
        if (saved != null) {
            wantConnected = true
            WatchRepository.update { it.copy(address = saved, deviceName = WatchRepository.savedName(app)) }
            reopen()
        }
        watchdog()
    }

    /** Every 90 s: if the watch should be connected but nothing is happening, try again. */
    private fun watchdog() {
        main.postDelayed({
            if (wantConnected && !WatchRepository.state.value.demo &&
                WatchRepository.state.value.link != WatchLink.CONNECTED && gatt == null
            ) {
                Log.i(TAG, "Watchdog: reconnecting")
                reopen()
            }
            watchdog()
        }, 90_000L)
    }

    // ----------------------------------------------------------------------------------- scanning
    fun startScan(): Boolean {
        if (!hasBle() || !hasPermissions() || !isBluetoothOn()) return false
        stopScan()
        main.removeCallbacks(publishDevices)
        publishPending = false
        found.clear()
        WatchRepository.setDevices(emptyList())
        val scanner = adapter?.bluetoothLeScanner ?: return false
        val cb = object : ScanCallback() {
            override fun onScanResult(callbackType: Int, result: ScanResult) {
                val dev = result.device ?: return
                val name = try { dev.name } catch (e: SecurityException) { null }
                    ?: result.scanRecord?.deviceName ?: ""
                val uuids = result.scanRecord?.serviceUuids?.map { it.uuid } ?: emptyList()
                val likely = DaFitGattAttributes.LIKELY_WATCH_NAME.containsMatchIn(name) ||
                    uuids.contains(DaFitGattAttributes.MOYOUNG_SERVICE_UUID) ||
                    uuids.contains(DaFitGattAttributes.MOYOUNG_FEEA_SERVICE_UUID) ||
                    uuids.contains(DaFitGattAttributes.HEART_RATE_SERVICE)
                found[dev.address] = ScanDevice(name, dev.address, result.rssi, likely)
                if (!publishPending) {
                    publishPending = true
                    main.postDelayed(publishDevices, 500L)
                }
            }

            override fun onScanFailed(errorCode: Int) {
                Log.w(TAG, "Scan failed: $errorCode")
                WatchRepository.update { it.copy(scanning = false, error = "scan:$errorCode") }
            }
        }
        scanCallback = cb
        return try {
            scanner.startScan(null, ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(), cb)
            WatchRepository.update { it.copy(scanning = true, error = "") }
            main.postDelayed({ stopScan() }, 20_000L)
            true
        } catch (e: Exception) {
            Log.w(TAG, "startScan: ${e.message}")
            scanCallback = null
            false
        }
    }

    fun stopScan() {
        val cb = scanCallback ?: return
        try { adapter?.bluetoothLeScanner?.stopScan(cb) } catch (_: Exception) {}
        scanCallback = null
        WatchRepository.update { it.copy(scanning = false) }
    }

    // ----------------------------------------------------------------------------------- connecting
    fun connect(device: ScanDevice) {
        stopDemo()
        stopScan()
        WatchRepository.saveDevice(app, device.name, device.address)
        wantConnected = true
        attempts = 0
        WatchRepository.update {
            WatchState(link = WatchLink.CONNECTING, address = device.address, deviceName = device.name.ifEmpty { device.address })
        }
        reopen()
    }

    /** [forget] = remove the saved watch so it is no longer reconnected automatically. */
    fun disconnect(forget: Boolean) {
        wantConnected = false
        main.removeCallbacks(reconnectRunnable)
        closeGatt()
        if (forget) WatchRepository.forget(app)
        WatchRepository.update {
            WatchState(scanning = it.scanning, address = if (forget) "" else it.address, deviceName = if (forget) "" else it.deviceName)
        }
    }

    private fun reopen() {
        val address = WatchRepository.state.value.address.ifEmpty { WatchRepository.savedAddress(app) ?: return }
        if (!hasBle() || !canConnect() || !isBluetoothOn()) {
            WatchRepository.update { it.copy(link = if (wantConnected) WatchLink.RECONNECTING else WatchLink.NONE) }
            return
        }
        closeGatt()
        val device = try { adapter?.getRemoteDevice(address) } catch (e: IllegalArgumentException) { null } ?: return
        WatchRepository.update {
            it.copy(link = if (attempts == 0) WatchLink.CONNECTING else WatchLink.RECONNECTING, address = address)
        }
        WatchRepository.log("connecting to $address (attempt ${attempts + 1})")
        // First tries: fast direct connect. Later: let Android keep trying in the background until it hears the watch.
        val auto = attempts >= 3
        gatt = try {
            if (Build.VERSION.SDK_INT >= 23) device.connectGatt(app, auto, callback, BluetoothDevice.TRANSPORT_LE)
            else device.connectGatt(app, auto, callback)
        } catch (e: Exception) {
            Log.w(TAG, "connectGatt: ${e.message}")
            null
        }
        if (gatt == null) scheduleReconnect()
    }

    private val reconnectRunnable = Runnable {
        if (wantConnected && !WatchRepository.state.value.demo &&
            WatchRepository.state.value.link != WatchLink.CONNECTED
        ) reopen()
    }

    private fun scheduleReconnect() {
        attempts++
        val delayMs = 1000L * (1 shl minOf(attempts, 6)).coerceAtMost(60)
        main.removeCallbacks(reconnectRunnable)
        main.postDelayed(reconnectRunnable, delayMs.coerceAtMost(60_000L))
    }

    private fun closeGatt() {
        ops.clear()
        busy = false
        main.removeCallbacks(opTimeout)
        val g = gatt ?: return
        gatt = null
        try { g.disconnect() } catch (_: Exception) {}
        try { g.close() } catch (_: Exception) {}
    }

    // ------------------------------------------------------------------------------ GATT operations
    private val ops = ArrayDeque<() -> Boolean>()
    private var busy = false
    private val opTimeout = Runnable { busy = false; runNext() }

    private fun enqueue(op: () -> Boolean) {
        ops.addLast(op)
        runNext()
    }

    private fun runNext() {
        if (busy) return
        val op = ops.removeFirstOrNull() ?: return
        busy = true
        main.postDelayed(opTimeout, 3000L)
        val started = try { op() } catch (e: Exception) { Log.w(TAG, "op failed: ${e.message}"); false }
        if (!started) opDone()
    }

    private fun opDone() {
        busy = false
        main.removeCallbacks(opTimeout)
        runNext()
    }

    private val callback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
            main.post {
                if (g !== gatt) {
                    try { g.close() } catch (_: Exception) {}
                    return@post
                }
                if (newState == BluetoothProfile.STATE_CONNECTED && status == BluetoothGatt.GATT_SUCCESS) {
                    attempts = 0
                    WatchRepository.log("connected")
                    WatchRepository.update {
                        it.copy(
                            link = WatchLink.CONNECTED, error = "",
                            deviceName = (try { g.device.name } catch (e: SecurityException) { null }).takeUnless { n -> n.isNullOrEmpty() } ?: it.deviceName
                        )
                    }
                    main.postDelayed({ if (g === gatt) g.discoverServices() }, 600L)
                } else {
                    WatchRepository.log("disconnected (status $status)")
                    closeGatt()
                    WatchRepository.update { it.copy(link = if (wantConnected) WatchLink.RECONNECTING else WatchLink.NONE) }
                    if (wantConnected) scheduleReconnect()
                }
            }
        }

        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            main.post {
                if (g !== gatt) return@post
                if (status != BluetoothGatt.GATT_SUCCESS) {
                    WatchRepository.log("service discovery failed ($status)")
                    return@post
                }
                setUpNotifications(g)
            }
        }

        override fun onDescriptorWrite(g: BluetoothGatt, d: BluetoothGattDescriptor, status: Int) {
            main.post { opDone() }
        }

        @Suppress("DEPRECATION")
        override fun onCharacteristicRead(g: BluetoothGatt, c: BluetoothGattCharacteristic, status: Int) {
            val value = c.value
            main.post {
                if (status == BluetoothGatt.GATT_SUCCESS && value != null) handleValue(c.uuid, value)
                opDone()
            }
        }

        @Suppress("DEPRECATION")
        override fun onCharacteristicChanged(g: BluetoothGatt, c: BluetoothGattCharacteristic) {
            val value = c.value ?: return
            main.post { handleValue(c.uuid, value) }
        }
    }

    @Suppress("DEPRECATION")
    private fun setUpNotifications(g: BluetoothGatt) {
        ops.clear()
        for (service in g.services) {
            if (service.uuid in DaFitGattAttributes.IGNORED_SERVICES) continue
            WatchRepository.log("service ${service.uuid.toString().substring(4, 8)}")
            for (ch in service.characteristics) {
                val props = ch.properties
                val canNotify = props and BluetoothGattCharacteristic.PROPERTY_NOTIFY != 0
                val canIndicate = props and BluetoothGattCharacteristic.PROPERTY_INDICATE != 0
                WatchRepository.log("  char ${ch.uuid.toString().substring(4, 8)} props=$props")
                if (canNotify || canIndicate) {
                    enqueue {
                        g.setCharacteristicNotification(ch, true)
                        val d = ch.getDescriptor(DaFitGattAttributes.CLIENT_CHARACTERISTIC_CONFIG) ?: return@enqueue false
                        d.value = if (canNotify) BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                        else BluetoothGattDescriptor.ENABLE_INDICATION_VALUE
                        g.writeDescriptor(d)
                    }
                }
                if (ch.uuid == DaFitGattAttributes.BATTERY_LEVEL && props and BluetoothGattCharacteristic.PROPERTY_READ != 0) {
                    enqueue { g.readCharacteristic(ch) }
                }
            }
        }
    }

    private val moyoung = MoyoungDecoder.Reassembler()

    private fun handleValue(uuid: UUID, data: ByteArray) {
        val short = uuid.toString().substring(4, 8)
        WatchRepository.log("$short  ${data.joinToString(" ") { "%02X".format(it) }}")
        when (uuid) {
            DaFitGattAttributes.HEART_RATE_MEASUREMENT -> {
                DaFitGattAttributes.parseHeartRate(data)?.let { hr ->
                    WatchRepository.update { it.copy(heartRate = hr, lastReadingMs = System.currentTimeMillis()) }
                }
            }
            DaFitGattAttributes.BATTERY_LEVEL -> {
                if (data.isNotEmpty()) {
                    val pct = data[0].toInt() and 0xFF
                    if (pct in 0..100) WatchRepository.update { it.copy(battery = pct, lastReadingMs = System.currentTimeMillis()) }
                }
            }
            // Vendor packets (Da Fit / Moyoung): EXPERIMENTAL decode, plausibility-checked, raw packet logged above
            DaFitGattAttributes.MOYOUNG_STEPS -> MoyoungDecoder.parseSteps(data)?.let { st ->
                WatchRepository.log("  decoded (experimental): steps=${st.steps}")
                WatchRepository.update { it.copy(steps = st.steps, lastReadingMs = System.currentTimeMillis()) }
            }
            DaFitGattAttributes.MOYOUNG_DATA_IN -> moyoung.feed(data)?.let { f ->
                when (f.command) {
                    MoyoungDecoder.CMD_SYNC_STEPS -> MoyoungDecoder.parseSteps(f.payload)?.let { st ->
                        WatchRepository.log("  decoded (experimental): steps=${st.steps}")
                        WatchRepository.update { it.copy(steps = st.steps, lastReadingMs = System.currentTimeMillis()) }
                    }
                    MoyoungDecoder.CMD_HEART_RATE -> MoyoungDecoder.parseHeartRate(f.payload)?.let { hr ->
                        WatchRepository.log("  decoded (experimental): hr=$hr")
                        WatchRepository.update { it.copy(heartRate = hr, lastReadingMs = System.currentTimeMillis()) }
                    }
                    MoyoungDecoder.CMD_BLOOD_OXYGEN -> MoyoungDecoder.parseSpo2(f.payload)?.let { sp ->
                        WatchRepository.log("  decoded (experimental): spo2=$sp")
                        WatchRepository.update { it.copy(spo2 = sp.toDouble(), lastReadingMs = System.currentTimeMillis()) }
                    }
                }
            }
        }
    }

    // ----------------------------------------------------------------------------------- demo mode
    /** Fake readings for emulators / testing. Clearly flagged in the UI and never uploaded. */
    fun startDemo() {
        disconnect(forget = false)
        WatchRepository.update {
            WatchState(link = WatchLink.CONNECTED, demo = true, deviceName = "Demo watch",
                heartRate = 74, spo2 = 98.0, steps = 1850, battery = 92, lastReadingMs = System.currentTimeMillis())
        }
        demoJob?.cancel()
        demoJob = scope.launch {
            while (isActive) {
                delay(3000)
                WatchRepository.update {
                    it.copy(
                        heartRate = (70..78).random(), spo2 = 98.0,
                        steps = (it.steps ?: 0) + (4..15).random(),
                        lastReadingMs = System.currentTimeMillis()
                    )
                }
            }
        }
    }

    fun stopDemo() {
        demoJob?.cancel()
        demoJob = null
        if (WatchRepository.state.value.demo) WatchRepository.update { WatchState() }
    }
}
