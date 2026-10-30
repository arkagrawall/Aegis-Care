package com.aegis.saathi.call

import android.app.Activity
import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.util.Log
import android.view.View
import android.view.WindowManager
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat

/**
 * Darkens the call screen while the phone is held to the ear, on every phone. Android's proximity wake lock
 * ([CallAudio]) switches the panel off where the phone supports it; some phones don't, or let "keep screen on"
 * win. This listens to the proximity sensor itself and, when near, covers the screen with a black layer that
 * swallows touches (so a cheek can't hang up), drops the brightness to the minimum and hides the system bars.
 */
class ProximityGuard(private val activity: Activity, private val cover: View) : SensorEventListener {

    private val sm = activity.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val sensor: Sensor? = sm.getDefaultSensor(Sensor.TYPE_PROXIMITY)
    private var listening = false
    private var near = false

    /** False while the speaker is on: the senior is looking at the screen, not holding it to the ear. */
    var enabled = true
        set(value) {
            field = value
            if (!value) apply(false)
        }

    val available: Boolean get() = sensor != null

    init {
        cover.setOnTouchListener { _, _ -> true }    // swallow every touch while covered
        cover.importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS
    }

    fun start() {
        val s = sensor ?: run { Log.i(TAG, "no proximity sensor"); return }
        if (!listening) listening = sm.registerListener(this, s, SensorManager.SENSOR_DELAY_NORMAL)
        Log.i(TAG, "proximity sensor listening=$listening range=${s.maximumRange}")
    }

    fun stop() {
        if (listening) sm.unregisterListener(this)
        listening = false
        apply(false)
    }

    override fun onSensorChanged(e: SensorEvent) {
        val range = sensor?.maximumRange ?: 5f
        // most sensors report 0 (near) or their max range (far); a few report centimetres
        val isNear = e.values[0] < minOf(range, 5f)
        apply(isNear && enabled)
    }

    override fun onAccuracyChanged(s: Sensor?, accuracy: Int) {}

    private fun apply(n: Boolean) {
        if (n == near) return
        near = n
        val w = activity.window
        cover.visibility = if (n) View.VISIBLE else View.GONE
        w.attributes = w.attributes.apply {
            screenBrightness = if (n) 0.01f else WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE
        }
        // "keep the screen on" only while it is being looked at; at the ear it must not fight the proximity lock
        if (n) w.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        else w.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        val bars = WindowCompat.getInsetsController(w, w.decorView)
        if (n) {
            bars.systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            bars.hide(WindowInsetsCompat.Type.systemBars())
        } else {
            bars.show(WindowInsetsCompat.Type.systemBars())
        }
    }

    private companion object { const val TAG = "ProximityGuard" }
}
