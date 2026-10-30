package com.aegis.saathi.ui

import android.animation.ObjectAnimator
import android.animation.PropertyValuesHolder
import android.bluetooth.BluetoothAdapter
import android.content.Intent
import android.content.res.ColorStateList
import android.os.Bundle
import android.provider.Settings
import android.view.LayoutInflater
import android.view.View
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.aegis.saathi.LocaleManager
import com.aegis.saathi.R
import com.aegis.saathi.api.AegisApiClient
import com.aegis.saathi.ble.ScanDevice
import com.aegis.saathi.ble.WatchLink
import com.aegis.saathi.ble.WatchManager
import com.aegis.saathi.ble.WatchRepository
import com.aegis.saathi.ble.WatchState
import com.aegis.saathi.call.CallApi
import com.aegis.saathi.databinding.ActivityWatchBinding
import com.aegis.saathi.databinding.ItemWatchDeviceBinding
import kotlinx.coroutines.launch
import java.text.DateFormat
import java.util.Date

/**
 * Pair and manage the smartwatch: search, connect, disconnect, forget. Once a watch is chosen it is
 * remembered and kept connected in the background by the service (see WatchManager).
 */
class WatchActivity : BaseActivity() {

    private lateinit var binding: ActivityWatchBinding
    private lateinit var manager: WatchManager
    private var pulse: ObjectAnimator? = null
    private var showAll = false
    private var lastDevices: List<ScanDevice> = emptyList()
    private var pendingScan = false
    private var shownCount = 0
    private var shownKey = ""

    private val permissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
            refreshNotice()
            if (pendingScan && manager.hasPermissions()) startScan()
            pendingScan = false
        }

    private val enableBluetoothLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { refreshNotice() }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityWatchBinding.inflate(layoutInflater)
        setContentView(binding.root)
        manager = WatchManager.get(this)

        binding.btnBack.setOnClickListener { finish() }
        binding.langToggle.onLanguageSelected = { lang ->
            LocaleManager.set(this, lang)
            val id = getSharedPreferences("aegis_senior_prefs", MODE_PRIVATE).getString("senior_id", "") ?: ""
            if (id.isNotEmpty()) lifecycleScope.launch { CallApi.setLanguage(id, lang) }
            binding.watchRoot.animate().alpha(0f).setDuration(140).withEndAction { recreate() }.start()
        }

        listOf(binding.btnScan, binding.btnDisconnect, binding.btnFix, binding.btnDemo).forEach { it.pressable() }
        binding.btnScan.setOnClickListener {
            if (WatchRepository.state.value.scanning) manager.stopScan() else requestAndScan()
        }
        binding.btnDisconnect.setOnClickListener {
            if (WatchRepository.state.value.demo) manager.stopDemo() else manager.disconnect(forget = false)
        }
        binding.btnForget.setOnClickListener {
            manager.disconnect(forget = true)
            binding.tvLinkDevice.text = ""
        }
        binding.btnDemo.setOnClickListener { manager.startDemo() }
        binding.cbShowAll.setOnCheckedChangeListener { _, checked ->
            showAll = checked
            renderDevices(lastDevices)
        }
        binding.rawToggle.setOnClickListener {
            val show = binding.rawBox.visibility != View.VISIBLE
            binding.rawBox.visibility = if (show) View.VISIBLE else View.GONE
        }

        binding.statusCard.slideUpIn(0)
        refreshNotice()

        lifecycleScope.launch { WatchRepository.state.collect { render(it) } }
        lifecycleScope.launch { WatchRepository.devices.collect { lastDevices = it; renderDevices(it) } }
        lifecycleScope.launch { WatchRepository.raw.collect { binding.tvRawLog.text = it.joinToString("\n") } }
    }

    override fun onResume() {
        super.onResume()
        refreshNotice()
    }

    // ----------------------------------------------------------------------------- actions
    private fun requestAndScan() {
        when {
            !manager.hasBle() -> refreshNotice()
            !manager.hasPermissions() -> {
                pendingScan = true
                permissionLauncher.launch(WatchManager.requiredPermissions())
            }
            !manager.isBluetoothOn() -> enableBluetooth()
            else -> startScan()
        }
    }

    private fun startScan() {
        binding.btnScan.tick()
        manager.startScan()
    }

    private fun enableBluetooth() {
        try {
            enableBluetoothLauncher.launch(Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE))
        } catch (e: Exception) {
            startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS))
        }
    }

    // ---------------------------------------------------------------------------- rendering
    /** Explains and offers a one-tap fix for whatever blocks scanning. */
    private fun refreshNotice() {
        val box = binding.noticeBox
        when {
            !manager.hasBle() -> {
                binding.tvNotice.text = getString(R.string.watch_no_ble)
                binding.btnFix.visibility = View.GONE
                box.visibility = View.VISIBLE
            }
            !manager.hasPermissions() -> {
                binding.tvNotice.text = getString(R.string.watch_perm_needed)
                binding.btnFix.text = getString(R.string.watch_perm_btn)
                binding.btnFix.visibility = View.VISIBLE
                binding.btnFix.setOnClickListener { permissionLauncher.launch(WatchManager.requiredPermissions()) }
                box.visibility = View.VISIBLE
            }
            !manager.isBluetoothOn() -> {
                binding.tvNotice.text = getString(R.string.watch_bt_off)
                binding.btnFix.text = getString(R.string.watch_bt_on_btn)
                binding.btnFix.visibility = View.VISIBLE
                binding.btnFix.setOnClickListener { enableBluetooth() }
                box.visibility = View.VISIBLE
            }
            else -> box.visibility = View.GONE
        }
        binding.btnScan.alpha = if (manager.hasBle()) 1f else 0.45f
    }

    private fun render(st: WatchState) {
        val title = when {
            st.link == WatchLink.CONNECTED -> R.string.watch_st_connected
            st.link == WatchLink.CONNECTING -> R.string.watch_st_connecting
            st.link == WatchLink.RECONNECTING -> R.string.watch_st_reconnecting
            st.scanning -> R.string.watch_st_scanning
            else -> R.string.watch_st_none
        }
        binding.tvLinkTitle.text = getString(title)
        binding.tvLinkDevice.text = when {
            st.demo -> getString(R.string.watch_demo_on)
            st.deviceName.isNotEmpty() -> st.deviceName
            else -> ""
        }

        val connected = st.link == WatchLink.CONNECTED
        val color = ContextCompat.getColor(
            this,
            when (st.link) {
                WatchLink.CONNECTED -> R.color.good
                WatchLink.CONNECTING, WatchLink.RECONNECTING -> R.color.warn
                WatchLink.NONE -> R.color.primary
            }
        )
        binding.ivWatchBig.imageTintList = ColorStateList.valueOf(color)

        val dash = "–"
        binding.wSteps.text = if (connected) st.steps?.let { String.format(LocaleManager.locale(this), "%,d", it) } ?: dash else dash
        binding.wHr.text = if (connected) st.heartRate?.toString() ?: dash else dash
        binding.wSpo2.text = if (connected) st.spo2?.let { "${it.toInt()}%" } ?: dash else dash
        binding.wBattery.text = if (connected) st.battery?.let { "$it%" } ?: dash else dash
        binding.tvLastReading.text = if (connected && st.lastReadingMs > 0)
            getString(R.string.watch_last_data, DateFormat.getTimeInstance(DateFormat.SHORT, LocaleManager.locale(this)).format(Date(st.lastReadingMs)))
        else if (connected) getString(R.string.watch_card_waiting) else ""

        binding.btnScan.text = getString(if (st.scanning) R.string.watch_stop else R.string.watch_scan)
        binding.btnDisconnect.visibility = if (st.link != WatchLink.NONE) View.VISIBLE else View.GONE
        binding.btnForget.visibility =
            if (WatchRepository.savedAddress(this) != null && !st.demo) View.VISIBLE else View.GONE

        // gentle breathing while searching / reconnecting
        val busy = st.scanning || st.link == WatchLink.CONNECTING || st.link == WatchLink.RECONNECTING
        if (busy && pulse == null) {
            pulse = ObjectAnimator.ofPropertyValuesHolder(
                binding.pulseRing,
                PropertyValuesHolder.ofFloat(View.SCALE_X, 1f, 1.25f),
                PropertyValuesHolder.ofFloat(View.SCALE_Y, 1f, 1.25f),
                PropertyValuesHolder.ofFloat(View.ALPHA, 1f, 0.35f)
            ).apply {
                duration = 900
                repeatCount = ObjectAnimator.INFINITE
                repeatMode = ObjectAnimator.REVERSE
                start()
            }
        } else if (!busy) {
            pulse?.cancel()
            pulse = null
            binding.pulseRing.scaleX = 1f
            binding.pulseRing.scaleY = 1f
            binding.pulseRing.alpha = 1f
        }
    }

    private fun renderDevices(all: List<ScanDevice>) {
        val list = if (showAll) all else all.filter { it.likelyWatch || it.name.isNotEmpty() }
        // Signal strength jitters on every advert; only rebuild the rows when what the senior sees changes
        // (RSSI in 5 dBm steps).
        val key = list.take(25).joinToString("|") { "${it.address}/${it.name}/${it.rssi / 5}" }
        if (key == shownKey) return
        shownKey = key
        binding.deviceList.removeAllViews()
        binding.tvNoDevices.visibility = if (list.isEmpty()) View.VISIBLE else View.GONE
        val inflater = LayoutInflater.from(this)
        list.take(25).forEachIndexed { i, d ->
            val row = ItemWatchDeviceBinding.inflate(inflater, binding.deviceList, false)
            row.tvDeviceName.text = d.name.ifEmpty { d.address }
            row.tvDeviceMeta.text = "${d.address}  ·  ${d.rssi} dBm"
            row.btnDeviceConnect.pressable()
            row.btnDeviceConnect.setOnClickListener {
                it.tick()
                manager.connect(d)
            }
            binding.deviceList.addView(row.root)
            if (i >= shownCount) row.root.slideUpIn((i - shownCount) * 40L)  // only new rows animate
        }
        shownCount = minOf(list.size, 25)
    }

    override fun onDestroy() {
        pulse?.cancel()
        super.onDestroy()
    }
}
