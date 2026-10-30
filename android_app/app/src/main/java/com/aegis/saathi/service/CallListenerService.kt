package com.aegis.saathi.service

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.net.ConnectivityManager
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.net.Network
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.Person
import androidx.core.app.ServiceCompat
import androidx.core.graphics.drawable.IconCompat
import androidx.core.content.ContextCompat
import com.aegis.saathi.LocaleManager
import com.aegis.saathi.R
import com.aegis.saathi.api.AegisApiClient
import com.aegis.saathi.ble.WatchLink
import com.aegis.saathi.ble.WatchManager
import com.aegis.saathi.ble.WatchRepository
import com.aegis.saathi.call.CallActionReceiver
import com.aegis.saathi.call.CallApi
import com.aegis.saathi.call.IncomingCalls
import com.aegis.saathi.call.Ringer
import com.aegis.saathi.sensor.FallDetector
import com.aegis.saathi.ui.BaseActivity
import com.aegis.saathi.ui.CallActivity
import com.aegis.saathi.ui.FallCheckActivity
import com.aegis.saathi.ui.IncomingCallActivity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import kotlin.random.Random

/**
 * Keeps the phone reachable and the watch connected while the app is closed:
 *  - one WebSocket to the server for incoming AI calls (reconnects with back-off, instantly when
 *    the network comes back, and re-registers the senior if the server no longer knows them),
 *  - the Bluetooth watch connection (see WatchManager),
 *  - uploads of real watch readings.
 * Nothing in here is allowed to throw out of a callback: a crash in this service kills the whole app.
 */
class CallListenerService : Service() {

    companion object {
        private const val TAG = "CallListenerService"
        private const val FOREGROUND_CHANNEL_ID = "aegis_service_channel"
        // a new id: channel sound/importance cannot change once a phone has the channel. Silent: Ringer rings.
        private const val CALL_CHANNEL_ID = "saathi_call_v2"
        private const val ALERT_CHANNEL_ID = "aegis_incoming_call_channel"   // emergencies and falls keep their sound
        private const val ONGOING_CHANNEL_ID = "saathi_call_ongoing"
        private const val FOREGROUND_NOTIF_ID = 1001
        private const val EMERGENCY_NOTIF_ID = 2003
        private const val RING_MS = 30_000L
        private const val ACTION_RECONNECT = "com.aegis.saathi.RECONNECT"
        private const val ACTION_FALL_REFRESH = "com.aegis.saathi.FALL_REFRESH"
        private const val ACTION_CALL_ON = "com.aegis.saathi.CALL_ON"
        private const val ACTION_CALL_OFF = "com.aegis.saathi.CALL_OFF"

        /** A call started or ended on screen: switch the foreground notification and microphone permission. */
        fun callStarted(context: Context, callId: String) = signal(context, Intent(context, CallListenerService::class.java)
            .setAction(ACTION_CALL_ON).putExtra("CALL_ID", callId))

        fun callEnded(context: Context) = signal(context, Intent(context, CallListenerService::class.java).setAction(ACTION_CALL_OFF))

        private fun signal(context: Context, intent: Intent) {
            try { ContextCompat.startForegroundService(context, intent) } catch (e: Exception) { Log.w(TAG, "signal: ${e.message}") }
        }

        /** Android 14+ lets the user switch off full-screen calls; without it the call only shows as a notification. */
        fun canShowFullScreen(context: Context): Boolean =
            Build.VERSION.SDK_INT < 34 ||
                (context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).canUseFullScreenIntent()
        const val PREF_FALL_DETECT = "fall_detect"
        private const val PREFS = "aegis_senior_prefs"

        @Volatile
        var activeSocket: WebSocket? = null

        /** Starts (or nudges) the service. Never throws: some phones refuse background starts. */
        fun start(context: Context) {
            try {
                ContextCompat.startForegroundService(context, Intent(context, CallListenerService::class.java))
            } catch (e: Exception) {
                Log.w(TAG, "Could not start service: ${e.message}")
            }
        }

        /** After the server address or the senior changed: drop the socket and connect again. */
        fun reconnect(context: Context) {
            try {
                ContextCompat.startForegroundService(
                    context,
                    Intent(context, CallListenerService::class.java).setAction(ACTION_RECONNECT)
                )
            } catch (e: Exception) {
                Log.w(TAG, "Could not signal service: ${e.message}")
            }
        }

        /** The senior switched fall detection on or off: start or stop listening to the accelerometer. */
        fun refreshFallDetection(context: Context) {
            try {
                ContextCompat.startForegroundService(
                    context,
                    Intent(context, CallListenerService::class.java).setAction(ACTION_FALL_REFRESH)
                )
            } catch (e: Exception) {
                Log.w(TAG, "Could not signal service: ${e.message}")
            }
        }

        fun sendSocketEvent(json: JSONObject) {
            try {
                activeSocket?.send(json.toString())
            } catch (e: Exception) {
                Log.w(TAG, "sendSocketEvent: ${e.message}")
            }
        }
    }

    private val client = OkHttpClient.Builder()
        .pingInterval(20, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var socket: WebSocket? = null
    private var attempt = 0
    private var reconnectJob: Job? = null
    private var syncJob: Job? = null
    private var networkCallback: ConnectivityManager.NetworkCallback? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private var destroyed = false
    private var foregroundOk = false
    private var fallListener: SensorEventListener? = null
    private val fallDetector = FallDetector { impact -> scope.launch { onFallDetected(impact) } }

    private val prefs get() = getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    // ---------------------------------------------------------------------------------- lifecycle
    override fun attachBaseContext(base: Context) {
        super.attachBaseContext(LocaleManager.wrap(base))
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
        foregroundOk = startAsForeground()
        if (!foregroundOk) {
            stopSelf()
            return
        }
        registerNetworkCallback()
        WatchManager.get(this).start()
        startVitalsSync()
        applyFallSetting()
        connect()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!foregroundOk) return START_NOT_STICKY
        if (intent?.action == ACTION_FALL_REFRESH) applyFallSetting()
        if (intent?.action == ACTION_CALL_ON) showOngoingCall(intent.getStringExtra("CALL_ID").orEmpty())
        if (intent?.action == ACTION_CALL_OFF) endOngoingCall()
        if (intent?.action == ACTION_RECONNECT && !destroyed) {
            reconnectJob?.cancel()
            attempt = 0
            connect()
        }
        try {
            WatchManager.get(this).start()
        } catch (e: Exception) {
            Log.w(TAG, "watch start: ${e.message}")
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        destroyed = true
        stopFallListening()
        scope.cancel()
        try { socket?.close(1000, "Service destroyed") } catch (_: Exception) {}
        socket = null
        activeSocket = null
        try {
            networkCallback?.let { getSystemService(ConnectivityManager::class.java).unregisterNetworkCallback(it) }
        } catch (_: Exception) {}
        try { wakeLock?.let { if (it.isHeld) it.release() } } catch (_: Exception) {}
        super.onDestroy()
    }

    /**
     * Becomes a foreground service. The declared types are phoneCall (incoming AI calls) and
     * connectedDevice (the watch); connectedDevice is only requested when the Bluetooth permission is
     * really granted, because Android 14 kills the app if a declared type's permission is missing.
     */
    private fun startAsForeground(): Boolean = startForegroundWith(guardNotification(), withMic = false)

    /**
     * (Re)declares the foreground service. During a call the microphone type is added (only while the call screen is
     * open, as Android requires), so the senior can keep talking with the screen off at the ear.
     */
    private fun startForegroundWith(notification: Notification, withMic: Boolean): Boolean {
        val withBle = Build.VERSION.SDK_INT < 31 ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED
        val mic = withMic && Build.VERSION.SDK_INT >= 30 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        val micType = if (mic) ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE else 0
        val attempts = if (Build.VERSION.SDK_INT >= 29) {
            listOfNotNull(
                if (withBle) ServiceInfo.FOREGROUND_SERVICE_TYPE_PHONE_CALL or ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE or micType else null,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_PHONE_CALL or micType,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_PHONE_CALL
            ).distinct()
        } else listOf(0)
        for (type in attempts) {
            try {
                ServiceCompat.startForeground(this, FOREGROUND_NOTIF_ID, notification, type)
                return true
            } catch (e: Exception) {
                Log.w(TAG, "startForeground(type=$type) failed: ${e.message}")
            }
        }
        return false
    }

    // -------------------------------------------------------------------------------- WebSocket
    private fun wsUrl(seniorId: String): String =
        AegisApiClient.baseUrl.replace("https://", "wss://").replace("http://", "ws://") + "/ws/seniors/$seniorId" +
            "?token=" + java.net.URLEncoder.encode(AegisApiClient.deviceKey, "UTF-8")

    private fun connect() {
        if (destroyed) return
        val seniorId = prefs.getString("senior_id", null)
        if (seniorId.isNullOrEmpty()) {
            Log.i(TAG, "No registered senior yet; call listener starts after onboarding")
            return
        }
        try { socket?.cancel() } catch (_: Exception) {}
        activeSocket = null
        val url = wsUrl(seniorId)
        Log.d(TAG, "Connecting to call signaling: $url (attempt ${attempt + 1})")
        try {
            socket = client.newWebSocket(Request.Builder().url(url).build(), object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    Log.i(TAG, "WebSocket connected for $seniorId")
                    attempt = 0
                    activeSocket = webSocket
                }

                override fun onMessage(webSocket: WebSocket, text: String) {
                    onSocketMessage(text)
                }

                override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                    webSocket.close(code, reason)
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    onSocketLost(webSocket, code)
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    Log.w(TAG, "WebSocket failure: ${t.message}")
                    onSocketLost(webSocket, -1)
                }
            })
        } catch (e: Exception) {
            Log.w(TAG, "newWebSocket: ${e.message}")
            scheduleReconnect()
        }
    }

    private fun onSocketLost(lost: WebSocket, code: Int) {
        scope.launch {
            if (destroyed || lost !== socket) return@launch
            if (activeSocket === lost) activeSocket = null
            if (code == 4004 || code == 4001) recoverRegistration() else scheduleReconnect()
        }
    }

    /** 2 s, 4 s, 8 s ... capped at 60 s, plus a little randomness so many phones don't reconnect in lock-step. */
    private fun scheduleReconnect() {
        if (destroyed) return
        attempt++
        val base = 1000L * (1 shl minOf(attempt, 6)).coerceAtMost(60)
        val wait = base.coerceAtMost(60_000L) + Random.nextLong(0, 1000)
        Log.d(TAG, "Reconnecting in ${wait / 1000}s")
        reconnectJob?.cancel()
        reconnectJob = scope.launch {
            delay(wait)
            connect()
        }
    }

    /** The server answered "unknown senior" (e.g. its data was reset): register again with the saved profile. */
    private fun recoverRegistration() {
        scope.launch {
            val p = prefs
            val name = p.getString("senior_name", null)
            val code = p.getString("coordinator_code", null)
            if (name == null || code == null) {
                scheduleReconnect()
                return@launch
            }
            val result = AegisApiClient.onboardSenior(
                name = name,
                age = p.getInt("senior_age", 70),
                city = p.getString("senior_city", "") ?: "",
                emergencyPhone = p.getString("senior_phone", "") ?: "",
                coordinatorCode = code,
                watchMac = WatchRepository.savedAddress(this@CallListenerService) ?: "",
                language = LocaleManager.current(this@CallListenerService),
                phone = p.getString("senior_own_phone", "") ?: ""
            )
            val newId = result.getOrNull()?.optJSONObject("senior")?.optString("senior_id").orEmpty()
            val newKey = result.getOrNull()?.optString("device_key").orEmpty()
            if (newId.isNotEmpty() && newKey.isNotEmpty()) {
                Log.i(TAG, "Re-registered senior as $newId")
                AegisApiClient.deviceKey = newKey
                p.edit().putString("senior_id", newId).putString("device_key", newKey).apply()
                attempt = 0
                connect()
            } else {
                scheduleReconnect()
            }
        }
    }

    private fun registerNetworkCallback() {
        try {
            val cm = getSystemService(ConnectivityManager::class.java)
            val cb = object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) {
                    // Network is back (Wi-Fi/mobile switch, airplane mode off): do not wait for the back-off timer
                    scope.launch {
                        if (!destroyed && activeSocket == null) {
                            reconnectJob?.cancel()
                            attempt = 0
                            connect()
                        }
                    }
                }
            }
            cm.registerDefaultNetworkCallback(cb)
            networkCallback = cb
        } catch (e: Exception) {
            Log.w(TAG, "network callback: ${e.message}")
        }
    }

    private fun onSocketMessage(text: String) {
        try {
            val json = JSONObject(text)
            when (json.optString("event")) {
                // the care manager changed the medicine list or contacts: fetch them (and re-arm alarms) now
                "medicines_changed" -> scope.launch { com.aegis.saathi.meds.CareRepo.refreshMedicines(this@CallListenerService) }
                "contacts_changed" -> scope.launch { com.aegis.saathi.meds.CareRepo.refreshContacts(this@CallListenerService) }
            }
            if (json.optString("event") == "emergency") scope.launch { handleEmergency(json) }
            if (json.optString("event") == "INCOMING_CALL") {
                val callId = json.optString("call_id")
                val callerName = LocaleManager.string(this, R.string.inc_name)
                scope.launch { handleIncomingCall(callId, callerName) }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error parsing call event: ${e.message}")
        }
    }

    // ----------------------------------------------------------------------------- watch uploads
    /**
     * Every 15 s, send the latest watch readings so the coordinator sees them. Demo-watch data is sent
     * too but flagged source="demo", so the portal can label it and nobody mistakes it for a real reading.
     */
    private fun startVitalsSync() {
        syncJob?.cancel()
        syncJob = scope.launch(Dispatchers.IO) {
            var lastKey = ""
            var lastSentAt = 0L
            delay(4_000)
            while (isActive) {
                try {
                    val st = WatchRepository.state.value
                    val seniorId = prefs.getString("senior_id", null)
                    if (st.link == WatchLink.CONNECTED && st.lastReadingMs > 0 && seniorId != null) {
                        val key = "${st.heartRate}|${st.spo2}|${st.steps}|${st.battery}"
                        val now = System.currentTimeMillis()
                        if (key != lastKey || now - lastSentAt > 60_000L) {
                            val ok = CallApi.syncVitals(
                                seniorId, st.steps, st.heartRate, st.spo2, st.battery,
                                source = if (st.demo) "demo" else "watch"
                            )
                            if (ok) {
                                lastKey = key
                                lastSentAt = now
                            }
                        }
                    }
                } catch (e: Exception) {
                    Log.w(TAG, "vitals sync: ${e.message}")
                }
                delay(15_000)
            }
        }
    }

    // ------------------------------------------------------------------------------ fall detection
    /** Opt-in. Samples are analysed on the phone and never uploaded; only the senior's answer is. */
    private fun applyFallSetting() {
        if (prefs.getBoolean(PREF_FALL_DETECT, false)) startFallListening() else stopFallListening()
    }

    private fun startFallListening() {
        if (fallListener != null) return
        try {
            val sm = getSystemService(Context.SENSOR_SERVICE) as SensorManager
            val accel = sm.getDefaultSensor(Sensor.TYPE_ACCELEROMETER) ?: return
            val l = object : SensorEventListener {
                override fun onSensorChanged(e: SensorEvent) {
                    try {
                        fallDetector.onSample(e.timestamp / 1_000_000L, e.values[0], e.values[1], e.values[2])
                    } catch (_: Exception) {}
                }

                override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
            }
            // 50 Hz, delivered in batches of up to 0.5 s so the CPU can sleep between them
            val ok = sm.registerListener(l, accel, 20_000, 500_000)
            if (ok) {
                fallDetector.reset()
                fallListener = l
                Log.i(TAG, "Fall detection on")
            }
        } catch (e: Exception) {
            Log.w(TAG, "fall listener: ${e.message}")
        }
    }

    private fun stopFallListening() {
        val l = fallListener ?: return
        try { (getSystemService(Context.SENSOR_SERVICE) as SensorManager).unregisterListener(l) } catch (_: Exception) {}
        fallListener = null
        Log.i(TAG, "Fall detection off")
    }

    private fun onFallDetected(impactG: Float) {
        if (destroyed || prefs.getString("senior_id", null).isNullOrEmpty()) return
        try {
            val intent = Intent(this, FallCheckActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                putExtra(FallCheckActivity.EXTRA_IMPACT_G, impactG)
            }
            val pending = PendingIntent.getActivity(this, 1, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            val notification = NotificationCompat.Builder(this, ALERT_CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_logo)
                .setContentTitle(LocaleManager.string(this, R.string.fall_title))
                .setContentText(LocaleManager.string(this, R.string.fall_msg))
                .setPriority(NotificationCompat.PRIORITY_MAX)
                .setCategory(NotificationCompat.CATEGORY_ALARM)
                .setAutoCancel(true)
                .setContentIntent(pending)
                .setFullScreenIntent(pending, true)
                .build()
            (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).notify(FallCheckActivity.NOTIF_ID, notification)
            // may be refused on Android 10+ while in the background; the notification above still alerts
            try { startActivity(intent) } catch (e: Exception) { Log.w(TAG, "fall startActivity: ${e.message}") }
        } catch (e: Exception) {
            Log.e(TAG, "onFallDetected: ${e.message}")
        }
    }

    // ---------------------------------------------------------------------------- incoming call
    /**
     * Rings like a phone call. A CallStyle notification with Answer / Decline and a full-screen intent: Android opens
     * the ringing screen over the lock screen by itself (an app in the background may not start an activity, so we
     * only do that while one of our screens is already visible). The service rings ([Ringer]) and owns the 30 s
     * timeout, so the hub hears "missed" even if no screen ever opened.
     */
    private fun handleIncomingCall(callId: String, callerName: String) {
        if (callId.isEmpty()) return
        try {
            // keep the CPU awake while the call rings; the full-screen intent wakes the screen itself
            val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
            try { wakeLock?.let { if (it.isHeld) it.release() } } catch (_: Exception) {}
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "aegis:incoming_call").also { it.acquire(RING_MS + 5_000L) }

            val ringIntent = Intent(this, IncomingCallActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
                putExtra("CALL_ID", callId)
                putExtra("CALLER_NAME", callerName)
            }
            val immutable = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            val ringPI = PendingIntent.getActivity(this, 0, ringIntent, immutable)
            val answerPI = PendingIntent.getActivity(
                this, 3,
                Intent(this, CallActivity::class.java).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                    putExtra("CALL_ID", callId)
                    putExtra(CallActivity.EXTRA_ANSWERED_FROM_NOTIFICATION, true)
                },
                immutable
            )
            val declinePI = PendingIntent.getBroadcast(
                this, 4,
                Intent(this, CallActionReceiver::class.java)
                    .setAction(CallActionReceiver.ACTION_DECLINE)
                    .putExtra(CallActionReceiver.EXTRA_CALL_ID, callId),
                immutable
            )
            val saathi = Person.Builder()
                .setName(callerName)
                .setIcon(IconCompat.createWithResource(this, R.drawable.ic_logo))
                .setImportant(true)
                .build()

            val notification = NotificationCompat.Builder(this, CALL_CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_phone)
                .setContentTitle(callerName)
                .setContentText(LocaleManager.string(this, R.string.notif_call_text))
                .setStyle(NotificationCompat.CallStyle.forIncomingCall(saathi, declinePI, answerPI))
                .setPriority(NotificationCompat.PRIORITY_MAX)
                .setCategory(NotificationCompat.CATEGORY_CALL)
                .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                .setOngoing(true)
                .setTimeoutAfter(RING_MS)
                .setContentIntent(ringPI)
                .setFullScreenIntent(ringPI, true)
                .build()
            (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).notify(IncomingCalls.NOTIF_ID, notification)

            Ringer.start(this, callId, RING_MS) { IncomingCalls.missed(this, callId) }

            if (BaseActivity.visibleScreens > 0) {
                try { startActivity(ringIntent) } catch (e: Exception) { Log.w(TAG, "ringing screen: ${e.message}") }
            }
            Log.i(TAG, "Incoming call $callId; full-screen allowed=${canShowFullScreen(this)}")
        } catch (e: Exception) {
            Log.e(TAG, "handleIncomingCall: ${e.message}")
        }
    }

    /** During a call: the foreground notification becomes "Saathi call · Hang up" and the microphone may run with the screen off. */
    private fun showOngoingCall(callId: String) {
        val openPI = PendingIntent.getActivity(
            this, 5,
            Intent(this, CallActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
                putExtra("CALL_ID", callId)
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val hangPI = PendingIntent.getBroadcast(
            this, 6,
            Intent(this, CallActionReceiver::class.java).setAction(CallActionReceiver.ACTION_HANG_UP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val saathi = Person.Builder()
            .setName(LocaleManager.string(this, R.string.inc_name))
            .setIcon(IconCompat.createWithResource(this, R.drawable.ic_logo))
            .build()
        val n = NotificationCompat.Builder(this, ONGOING_CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_phone)
            .setContentTitle(LocaleManager.string(this, R.string.inc_name))
            .setContentText(LocaleManager.string(this, R.string.notif_call_ongoing))
            .setStyle(NotificationCompat.CallStyle.forOngoingCall(saathi, hangPI))
            .setCategory(NotificationCompat.CATEGORY_CALL)
            .setOngoing(true)
            .setUsesChronometer(true)
            .setWhen(System.currentTimeMillis())
            .setContentIntent(openPI)
            .build()
        startForegroundWith(n, withMic = true)
    }

    private fun endOngoingCall() {
        startForegroundWith(guardNotification(), withMic = false)
    }

    /**
     * The hub raised an emergency. While Saathi is on the call and the family is being phoned by the alert agent,
     * the call carries on (Saathi tells them help is coming) and only a notification is posted; otherwise the
     * "Help is coming" screen opens over everything, and dials the family itself when the hub could not.
     */
    private fun handleEmergency(json: JSONObject) {
        try {
            val ai = json.optBoolean("ai_calling", false)
            val dialNow = json.optBoolean("dial_now", false)
            val intent = Intent(this, com.aegis.saathi.ui.EmergencyActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
                putExtra("ai_calling", ai)
                putExtra("dial_now", dialNow)
                putExtra("contact_name", json.optString("contact_name"))
                putExtra("contact_phone", json.optString("contact_phone"))
                putExtra("sos_id", json.optString("sos_id"))
            }
            val pending = PendingIntent.getActivity(this, 7, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            val quiet = ai && !dialNow && com.aegis.saathi.call.ActiveCall.isActive
            val notification = NotificationCompat.Builder(this, ALERT_CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_sos)
                .setContentTitle(LocaleManager.string(this, R.string.emg_title))
                .setContentText(LocaleManager.string(this, R.string.emg_cm_knows))
                .setPriority(NotificationCompat.PRIORITY_MAX)
                .setCategory(NotificationCompat.CATEGORY_ALARM)
                .setAutoCancel(true)
                .setSilent(quiet)
                .setContentIntent(pending)
                .apply { if (!quiet) setFullScreenIntent(pending, true) }
                .build()
            (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).notify(EMERGENCY_NOTIF_ID, notification)
            if (!quiet) try { startActivity(intent) } catch (e: Exception) { Log.w(TAG, "emergency screen: ${e.message}") }
        } catch (e: Exception) {
            Log.e(TAG, "handleEmergency: ${e.message}")
        }
    }

    // ------------------------------------------------------------------------------ notifications
    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        nm.createNotificationChannel(
            NotificationChannel(FOREGROUND_CHANNEL_ID, getString(R.string.notif_ch_guard), NotificationManager.IMPORTANCE_LOW)
                .apply { description = getString(R.string.notif_ch_guard_desc) }
        )

        val audio = AudioAttributes.Builder()
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
            .build()
        // emergencies and fall checks: sound from the channel
        nm.createNotificationChannel(
            NotificationChannel(ALERT_CHANNEL_ID, getString(R.string.notif_ch_alert), NotificationManager.IMPORTANCE_HIGH).apply {
                description = getString(R.string.notif_ch_alert_desc)
                setSound(RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE), audio)
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 1000, 500, 1000, 500, 1000)
                lockscreenVisibility = Notification.VISIBILITY_PUBLIC
            }
        )
        // Saathi's calls: high importance (full-screen, heads-up) but silent, because Ringer rings
        nm.createNotificationChannel(
            NotificationChannel(CALL_CHANNEL_ID, getString(R.string.notif_ch_call), NotificationManager.IMPORTANCE_HIGH).apply {
                description = getString(R.string.notif_ch_call_desc)
                setSound(null, null)
                enableVibration(false)
                lockscreenVisibility = Notification.VISIBILITY_PUBLIC
            }
        )
        nm.createNotificationChannel(
            NotificationChannel(ONGOING_CHANNEL_ID, getString(R.string.notif_ch_ongoing), NotificationManager.IMPORTANCE_DEFAULT).apply {
                setSound(null, null)
                enableVibration(false)
                lockscreenVisibility = Notification.VISIBILITY_PUBLIC
            }
        )
    }

    private fun guardNotification(): Notification =
        NotificationCompat.Builder(this, FOREGROUND_CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_logo)
            .setContentTitle(LocaleManager.string(this, R.string.notif_guard_title))
            .setContentText(LocaleManager.string(this, R.string.notif_guard_text))
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .build()
}
