package com.aegis.saathi.ui

import android.annotation.SuppressLint
import android.animation.ObjectAnimator
import android.animation.PropertyValuesHolder
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
import android.view.View
import android.view.animation.AccelerateDecelerateInterpolator
import android.view.animation.DecelerateInterpolator
import android.view.animation.OvershootInterpolator

/** Small shared micro-animations so every screen feels the same: soft, quick, never flashy. */

fun View.dpf(v: Int): Float = v * resources.displayMetrics.density

/** Button "press" feel: shrinks slightly while a finger is down, springs back on release. */
@SuppressLint("ClickableViewAccessibility")
fun View.pressable(scale: Float = 0.95f) {
    setOnTouchListener { v, e ->
        when (e.action) {
            MotionEvent.ACTION_DOWN ->
                v.animate().scaleX(scale).scaleY(scale).setDuration(90).start()
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL ->
                v.animate().scaleX(1f).scaleY(1f).setDuration(160)
                    .setInterpolator(OvershootInterpolator(2.2f)).start()
        }
        false // let the normal click still happen
    }
}

/** Gentle tick felt in the hand when something is tapped (unless "Vibrate on touch" is off on the Me tab). */
fun View.tick() {
    if (com.aegis.saathi.A11yPrefs.haptics(context)) performHapticFeedback(HapticFeedbackConstants.CONTEXT_CLICK)
}

/** Slides up from slightly below while fading in (used for staggered screen entrance). */
fun View.slideUpIn(delayMs: Long = 0) {
    alpha = 0f
    translationY = dpf(28)
    animate().alpha(1f).translationY(0f)
        .setStartDelay(delayMs).setDuration(420)
        .setInterpolator(DecelerateInterpolator(1.6f)).start()
}

/** "Pops" into view with a small overshoot (success checkmarks, confirmations). */
fun View.popIn(delayMs: Long = 0) {
    visibility = View.VISIBLE
    alpha = 0f
    scaleX = 0.6f
    scaleY = 0.6f
    animate().alpha(1f).scaleX(1f).scaleY(1f)
        .setStartDelay(delayMs).setDuration(380)
        .setInterpolator(OvershootInterpolator(1.8f)).start()
}

/** Fades a view out and hides it. */
fun View.fadeOutGone(durationMs: Long = 200, then: (() -> Unit)? = null) {
    animate().alpha(0f).setDuration(durationMs).withEndAction {
        visibility = View.GONE
        alpha = 1f
        then?.invoke()
    }.start()
}

/** Slow breathing scale, used on the voice button while it is listening. Call cancel() to stop. */
fun View.breathe(): ObjectAnimator =
    ObjectAnimator.ofPropertyValuesHolder(
        this,
        PropertyValuesHolder.ofFloat(View.SCALE_X, 1f, 1.04f),
        PropertyValuesHolder.ofFloat(View.SCALE_Y, 1f, 1.04f)
    ).apply {
        duration = 700
        repeatCount = ObjectAnimator.INFINITE
        repeatMode = ObjectAnimator.REVERSE
        interpolator = AccelerateDecelerateInterpolator()
        start()
    }
