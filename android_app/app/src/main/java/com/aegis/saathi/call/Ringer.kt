package com.aegis.saathi.call

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.MediaPlayer
import android.media.RingtoneManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.util.Log

/**
 * The one ringtone + vibration for an incoming Saathi call. The service starts it when the hub signals a call;
 * whoever ends the ringing (Answer, Decline, the notification's buttons, the 30 s timeout) calls [stop].
 * Keeping it here, not in the ringing screen, means it rings even when Android shows only a notification,
 * and never rings twice.
 */
object Ringer {
    private const val TAG = "Ringer"
    private val PATTERN = longArrayOf(0, 900, 600, 900, 600)

    private val main = Handler(Looper.getMainLooper())
    private var player: MediaPlayer? = null
    private var vibrator: Vibrator? = null
    private var timeout: Runnable? = null

    /** The call currently ringing (empty when nothing rings). */
    @Volatile var ringingCallId: String = ""
        private set

    /** Rings for at most [maxMs]; [onTimeout] runs if nobody answered or declined by then. */
    fun start(context: Context, callId: String, maxMs: Long, onTimeout: () -> Unit) {
        stop()
        ringingCallId = callId
        val app = context.applicationContext
        val am = app.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        // respect silent mode, like a phone: vibrate only
        if (am.ringerMode == AudioManager.RINGER_MODE_NORMAL) {
            try {
                player = MediaPlayer().apply {
                    setDataSource(app, RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE))
                    setAudioAttributes(
                        AudioAttributes.Builder()
                            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                            .setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                            .build()
                    )
                    isLooping = true
                    prepare()
                    start()
                }
            } catch (e: Exception) {
                Log.w(TAG, "ringtone: ${e.message}")
                player = null
            }
        }
        if (am.ringerMode != AudioManager.RINGER_MODE_SILENT) {
            try {
                val v = if (Build.VERSION.SDK_INT >= 31) {
                    (app.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager).defaultVibrator
                } else {
                    @Suppress("DEPRECATION")
                    app.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
                }
                v.vibrate(VibrationEffect.createWaveform(PATTERN, 0))
                vibrator = v
            } catch (e: Exception) {
                Log.w(TAG, "vibrate: ${e.message}")
            }
        }
        timeout = Runnable {
            val id = ringingCallId
            stop()
            if (id == callId) onTimeout()
        }.also { main.postDelayed(it, maxMs) }
    }

    fun stop() {
        timeout?.let { main.removeCallbacks(it) }
        timeout = null
        ringingCallId = ""
        try { player?.stop() } catch (_: Exception) {}
        try { player?.release() } catch (_: Exception) {}
        player = null
        try { vibrator?.cancel() } catch (_: Exception) {}
        vibrator = null
    }
}
