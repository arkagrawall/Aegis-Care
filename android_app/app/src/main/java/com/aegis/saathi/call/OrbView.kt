package com.aegis.saathi.call

import android.animation.ArgbEvaluator
import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RadialGradient
import android.graphics.RectF
import android.graphics.Shader
import android.util.AttributeSet
import android.view.View
import android.view.animation.LinearInterpolator
import kotlin.math.PI
import kotlin.math.min
import kotlin.math.sin

/**
 * The call "face": a soft glowing orb that shows what the call is doing without any text.
 *  - CONNECTING  : slow grey-blue breathing
 *  - AI_SPEAKING : teal, rhythmic pulse with ripples going outwards
 *  - LISTENING   : blue, reacts to the senior's voice level (bigger when they talk)
 *  - THINKING    : amber with a rotating arc
 *  - ENDED       : calm green
 */
class OrbView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : View(context, attrs) {

    private var phase = Phase.CONNECTING
    private var level = 0f
    private var smoothLevel = 0f
    private var t = 0f // 0..1 looping clock

    private var color = colorFor(Phase.CONNECTING)
    private var colorAnimator: ValueAnimator? = null

    private val corePaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val haloPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE }
    private val arcPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
    }
    private val arcRect = RectF()

    private val clock = ValueAnimator.ofFloat(0f, 1f).apply {
        duration = 2400
        repeatCount = ValueAnimator.INFINITE
        interpolator = LinearInterpolator()
        addUpdateListener {
            t = it.animatedFraction
            invalidate()
        }
    }

    private fun colorFor(p: Phase): Int = when (p) {
        Phase.CONNECTING -> 0xFF64748B.toInt()
        Phase.AI_SPEAKING -> 0xFF14B8A6.toInt()
        Phase.LISTENING -> 0xFF38BDF8.toInt()
        Phase.THINKING -> 0xFFF59E0B.toInt()
        Phase.ENDED -> 0xFF22C55E.toInt()
    }

    fun setPhase(newPhase: Phase) {
        if (newPhase == phase) return
        phase = newPhase
        val from = color
        val to = colorFor(newPhase)
        colorAnimator?.cancel()
        colorAnimator = ValueAnimator.ofObject(ArgbEvaluator(), from, to).apply {
            duration = 350
            addUpdateListener { color = it.animatedValue as Int }
            start()
        }
    }

    fun setLevel(newLevel: Float) {
        level = newLevel.coerceIn(0f, 1f)
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        if (!clock.isStarted) clock.start()
    }

    override fun onDetachedFromWindow() {
        clock.cancel()
        colorAnimator?.cancel()
        super.onDetachedFromWindow()
    }

    private fun withAlpha(c: Int, a: Float): Int =
        Color.argb((a.coerceIn(0f, 1f) * 255).toInt(), Color.red(c), Color.green(c), Color.blue(c))

    private fun lighten(c: Int, f: Float): Int = Color.rgb(
        (Color.red(c) + (255 - Color.red(c)) * f).toInt(),
        (Color.green(c) + (255 - Color.green(c)) * f).toInt(),
        (Color.blue(c) + (255 - Color.blue(c)) * f).toInt()
    )

    override fun onDraw(canvas: Canvas) {
        val cx = width / 2f
        val cy = height / 2f
        val base = min(width, height) * 0.26f

        // Ease the mic level so the orb doesn't jitter
        smoothLevel += (level - smoothLevel) * 0.25f

        val wave = sin(2.0 * PI * t).toFloat()
        val core = when (phase) {
            Phase.AI_SPEAKING -> base * (1f + 0.05f * wave + 0.03f * sin(4.0 * PI * t).toFloat())
            Phase.LISTENING -> base * (1f + 0.02f * wave + 0.40f * smoothLevel)
            Phase.THINKING -> base * (0.96f + 0.02f * wave)
            Phase.ENDED -> base
            Phase.CONNECTING -> base * (0.95f + 0.04f * wave)
        }

        // Soft ripples going outwards (speaking / listening)
        val rippling = phase == Phase.AI_SPEAKING || phase == Phase.LISTENING
        if (rippling) {
            for (i in 0 until 3) {
                val p = (t + i / 3f) % 1f
                val r = core * (1.05f + 0.85f * p)
                haloPaint.strokeWidth = base * 0.06f
                haloPaint.color = withAlpha(color, (1f - p) * (0.35f + 0.4f * smoothLevel))
                canvas.drawCircle(cx, cy, r, haloPaint)
            }
        }

        // Glow
        corePaint.shader = RadialGradient(
            cx, cy, core * 1.7f,
            intArrayOf(withAlpha(color, 0.45f), withAlpha(color, 0f)),
            floatArrayOf(0.35f, 1f), Shader.TileMode.CLAMP
        )
        canvas.drawCircle(cx, cy, core * 1.7f, corePaint)

        // Core
        corePaint.shader = RadialGradient(
            cx - core * 0.3f, cy - core * 0.35f, core * 1.3f,
            intArrayOf(lighten(color, 0.55f), color),
            floatArrayOf(0f, 1f), Shader.TileMode.CLAMP
        )
        canvas.drawCircle(cx, cy, core, corePaint)

        // Thinking: rotating arc around the core
        if (phase == Phase.THINKING) {
            arcPaint.strokeWidth = base * 0.09f
            arcPaint.color = withAlpha(Color.WHITE, 0.9f)
            val r = core * 1.25f
            arcRect.set(cx - r, cy - r, cx + r, cy + r)
            canvas.drawArc(arcRect, t * 360f, 100f, false, arcPaint)
            canvas.drawArc(arcRect, t * 360f + 180f, 100f, false, arcPaint)
        }
    }
}
