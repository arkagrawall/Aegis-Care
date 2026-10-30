package com.aegis.saathi.call

import android.content.Context
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.os.Build
import android.os.PowerManager
import android.util.Log

/**
 * Makes the AI call behave like a normal phone call:
 *  - the voice plays from the EARPIECE (held to the ear), or a wired / Bluetooth headset when one is connected,
 *  - the speakerphone is a choice the senior makes with the speaker button,
 *  - the phone's call-mode echo cancellation is on, so Saathi can keep listening while she talks,
 *  - the screen switches off when the phone is held against the ear (proximity), like any call.
 */
class CallAudio(context: Context) {

    private companion object { const val TAG = "CallAudio" }

    private val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private val power = context.getSystemService(Context.POWER_SERVICE) as PowerManager
    private var proximity: PowerManager.WakeLock? = null
    private var oldMode = AudioManager.MODE_NORMAL

    var speakerOn = false
        private set

    fun start() {
        oldMode = am.mode
        am.mode = AudioManager.MODE_IN_COMMUNICATION
        val supported = power.isWakeLockLevelSupported(PowerManager.PROXIMITY_SCREEN_OFF_WAKE_LOCK)
        if (supported) {
            try {
                proximity = power.newWakeLock(PowerManager.PROXIMITY_SCREEN_OFF_WAKE_LOCK, "aegis:call-proximity").apply {
                    setReferenceCounted(false)
                }
            } catch (e: Exception) {
                Log.w(TAG, "proximity wake lock: ${e.message}")
            }
        }
        route(speaker = false)
        // the call screen's ProximityGuard covers phones where this does nothing
        Log.i(TAG, "proximity wake lock supported=$supported held=${proximity?.isHeld == true}")
    }

    /** Switches between the earpiece (or headset) and the loudspeaker. */
    fun setSpeaker(on: Boolean) = route(on)

    private fun route(speaker: Boolean) {
        speakerOn = speaker
        if (Build.VERSION.SDK_INT >= 31) {
            val devices = am.availableCommunicationDevices
            val want = if (speaker) {
                devices.firstOrNull { it.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER }
            } else {
                // a headset the senior is wearing beats the earpiece
                devices.firstOrNull { it.type == AudioDeviceInfo.TYPE_WIRED_HEADSET || it.type == AudioDeviceInfo.TYPE_WIRED_HEADPHONES }
                    ?: devices.firstOrNull { it.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO || it.type == AudioDeviceInfo.TYPE_BLE_HEADSET }
                    ?: devices.firstOrNull { it.type == AudioDeviceInfo.TYPE_BUILTIN_EARPIECE }
            }
            if (want != null) am.setCommunicationDevice(want) else am.clearCommunicationDevice()
        } else {
            @Suppress("DEPRECATION")
            am.isSpeakerphoneOn = speaker
        }
        // the screen should only go dark against the ear, not while using the speaker
        if (speaker) proximity?.let { if (it.isHeld) it.release() }
        else proximity?.let { if (!it.isHeld) it.acquire(30 * 60 * 1000L) }
    }

    fun stop() {
        try {
            if (Build.VERSION.SDK_INT >= 31) am.clearCommunicationDevice()
            else @Suppress("DEPRECATION") { am.isSpeakerphoneOn = false }
            am.mode = oldMode
        } catch (_: Exception) {}
        proximity?.let { if (it.isHeld) it.release() }
        proximity = null
    }
}
