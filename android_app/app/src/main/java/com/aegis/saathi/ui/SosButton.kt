package com.aegis.saathi.ui

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Typeface
import android.util.AttributeSet
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
import android.view.View
import android.view.animation.LinearInterpolator
import androidx.core.content.res.ResourcesCompat
import androidx.core.view.ViewCompat
import com.aegis.saathi.R

/**
 * Round emergency button. It does nothing on a tap or a brush: the finger must stay on it for the
 * full hold time while a white ring fills around it. Letting go early (or sliding off) resets it.
 * After the hold, the screen still shows a cancellable countdown before anything is sent.
 */
class SosButton @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : View(context, attrs) {

    /** Called once the ring is full. */
    var onHoldComplete: (() -> Unit)? = null

    /** Called when the hold begins / is abandoned (for hints). */
    var onHoldStateChanged: ((holding: Boolean) -> Unit)? = null

    private val holdMs = 3000L
    private val d = resources.displayMetrics.density
    private var progress = 0f
    private var animator: ValueAnimator? = null
    private var completed = false

    private val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = ResourcesCompat.getColor(resources, R.color.sos, null)
        setShadowLayer(10 * d, 0f, 3 * d, 0x55000000)
    }
    private val track = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = 4 * d
        color = 0x55FFFFFF
    }
    private val arc = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = 4 * d
        strokeCap = Paint.Cap.ROUND
        color = Color.WHITE
    }
    private val label = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE
        textAlign = Paint.Align.CENTER
        textSize = 21f * d
        typeface = ResourcesCompat.getFont(context, R.font.mukta_bold) ?: Typeface.DEFAULT_BOLD
    }
    private val rect = RectF()

    init {
        setLayerType(LAYER_TYPE_SOFTWARE, null) // needed for the soft shadow
        isClickable = true
        isFocusable = true
        contentDescription = context.getString(R.string.sos_tip)
        // TalkBack can't "hold": a double-tap (and the "Send SOS" action) starts the same cancellable countdown
        ViewCompat.addAccessibilityAction(this, context.getString(R.string.sos_a11y_action)) { _, _ ->
            onHoldComplete?.invoke(); true
        }
    }

    override fun performAccessibilityAction(action: Int, arguments: android.os.Bundle?): Boolean {
        val am = context.getSystemService(Context.ACCESSIBILITY_SERVICE) as android.view.accessibility.AccessibilityManager
        if (action == android.view.accessibility.AccessibilityNodeInfo.ACTION_CLICK && am.isTouchExplorationEnabled) {
            onHoldComplete?.invoke()
            return true
        }
        return super.performAccessibilityAction(action, arguments)
    }

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        setMeasuredDimension((76 * d).toInt(), (76 * d).toInt())
    }

    override fun onDraw(canvas: Canvas) {
        val cx = width / 2f
        val cy = height / 2f
        val r = width / 2f - 6 * d
        canvas.drawCircle(cx, cy, r, fill)
        val ring = r - 5 * d
        rect.set(cx - ring, cy - ring, cx + ring, cy + ring)
        canvas.drawArc(rect, 0f, 360f, false, track)
        if (progress > 0f) canvas.drawArc(rect, -90f, 360f * progress, false, arc)
        val baseline = cy - (label.descent() + label.ascent()) / 2
        canvas.drawText("SOS", cx, baseline, label)
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                begin()
                return true
            }
            MotionEvent.ACTION_MOVE -> {
                // sliding off the button abandons the hold
                if (event.x < 0 || event.y < 0 || event.x > width || event.y > height) abandon()
                return true
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                abandon()
                performClick()
                return true
            }
        }
        return super.onTouchEvent(event)
    }

    override fun performClick(): Boolean {
        super.performClick()
        return true
    }

    private fun begin() {
        completed = false
        if (com.aegis.saathi.A11yPrefs.haptics(context)) performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
        onHoldStateChanged?.invoke(true)
        animator?.cancel()
        animate().scaleX(1.06f).scaleY(1.06f).setDuration(160).start()
        animator = ValueAnimator.ofFloat(progress, 1f).apply {
            duration = (holdMs * (1f - progress)).toLong().coerceAtLeast(1L)
            interpolator = LinearInterpolator()
            addUpdateListener {
                progress = it.animatedValue as Float
                invalidate()
                if (progress >= 1f && !completed) {
                    completed = true
                    if (com.aegis.saathi.A11yPrefs.haptics(context)) performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
                    resetVisual()
                    onHoldComplete?.invoke()
                }
            }
            start()
        }
    }

    private fun abandon() {
        if (completed) return
        if (animator?.isRunning == true || progress > 0f) {
            onHoldStateChanged?.invoke(false)
        }
        animator?.cancel()
        resetVisual()
    }

    private fun resetVisual() {
        animator?.cancel()
        animate().scaleX(1f).scaleY(1f).setDuration(160).start()
        ValueAnimator.ofFloat(progress, 0f).apply {
            duration = 220
            addUpdateListener { progress = it.animatedValue as Float; invalidate() }
            start()
        }
    }

    override fun onDetachedFromWindow() {
        animator?.cancel()
        super.onDetachedFromWindow()
    }
}
