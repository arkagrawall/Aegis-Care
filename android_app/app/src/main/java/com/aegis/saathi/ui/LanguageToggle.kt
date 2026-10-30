package com.aegis.saathi.ui

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Typeface
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.View
import android.view.animation.DecelerateInterpolator
import androidx.core.content.res.ResourcesCompat
import com.aegis.saathi.LocaleManager
import com.aegis.saathi.R

/**
 * Small "हिं | EN" switch that lives at the top of every main screen.
 * The white thumb glides to the chosen side; the labels are the same in both languages so the
 * senior can always find their language again.
 */
class LanguageToggle @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : View(context, attrs) {

    /** Called after the thumb has moved, with "hi" or "en". */
    var onLanguageSelected: ((String) -> Unit)? = null

    private var selected = LocaleManager.current(context)
    private var pos = if (selected == LocaleManager.EN) 1f else 0f

    private val d = resources.displayMetrics.density
    private val track = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = ContextColor(R.color.line_strong) }
    private val thumb = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.WHITE }
    private val thumbEdge = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = d
        color = ContextColor(R.color.line)
    }
    private val label = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        textAlign = Paint.Align.CENTER
        textSize = 17f * d
        typeface = ResourcesCompat.getFont(context, R.font.mukta_semibold) ?: Typeface.DEFAULT_BOLD
    }
    private val rect = RectF()

    private fun ContextColor(res: Int): Int = ResourcesCompat.getColor(resources, res, null)

    init {
        isClickable = true
        isFocusable = true
        contentDescription = context.getString(R.string.lang_toggle_desc)
        // TalkBack: "Change language, हिंदी" ... double-tap switches to the other language
        androidx.core.view.ViewCompat.setStateDescription(this, if (selected == LocaleManager.EN) "English" else "हिंदी")
    }

    // 104 x 52 dp: each half is a comfortable target for a senior's finger
    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        setMeasuredDimension((104 * d).toInt(), (52 * d).toInt())
    }

    override fun onDraw(canvas: Canvas) {
        val w = width.toFloat()
        val h = height.toFloat()
        rect.set(0f, 0f, w, h)
        canvas.drawRoundRect(rect, h / 2, h / 2, track)

        val pad = 3 * d
        val thumbW = (w - 2 * pad) / 2
        val left = pad + pos * thumbW
        rect.set(left, pad, left + thumbW, h - pad)
        canvas.drawRoundRect(rect, (h - 2 * pad) / 2, (h - 2 * pad) / 2, thumb)
        canvas.drawRoundRect(rect, (h - 2 * pad) / 2, (h - 2 * pad) / 2, thumbEdge)

        val baseline = h / 2 - (label.descent() + label.ascent()) / 2
        label.color = lerp(ContextColor(R.color.ink), ContextColor(R.color.ink_faint), pos)
        canvas.drawText("हिं", pad + thumbW / 2, baseline, label)
        label.color = lerp(ContextColor(R.color.ink_faint), ContextColor(R.color.ink), pos)
        canvas.drawText("EN", pad + thumbW * 1.5f, baseline, label)
    }

    private fun lerp(a: Int, b: Int, t: Float): Int = Color.rgb(
        (Color.red(a) + (Color.red(b) - Color.red(a)) * t).toInt(),
        (Color.green(a) + (Color.green(b) - Color.green(a)) * t).toInt(),
        (Color.blue(a) + (Color.blue(b) - Color.blue(a)) * t).toInt()
    )

    override fun onTouchEvent(event: MotionEvent): Boolean {
        when (event.action) {
            MotionEvent.ACTION_DOWN -> return true
            MotionEvent.ACTION_UP -> {
                val lang = if (event.x < width / 2f) LocaleManager.HI else LocaleManager.EN
                if (lang != selected) {
                    tick()
                    select(lang)
                } else {
                    performClick()
                }
                return true
            }
        }
        return super.onTouchEvent(event)
    }

    /** A click without a touch position (TalkBack, a keyboard, switch access) switches to the other language. */
    override fun performClick(): Boolean {
        super.performClick()
        return true
    }

    override fun performAccessibilityAction(action: Int, arguments: android.os.Bundle?): Boolean {
        if (action == android.view.accessibility.AccessibilityNodeInfo.ACTION_CLICK) {
            select(if (selected == LocaleManager.EN) LocaleManager.HI else LocaleManager.EN)
            return true
        }
        return super.performAccessibilityAction(action, arguments)
    }

    private fun select(lang: String) {
        selected = lang
        ValueAnimator.ofFloat(pos, if (lang == LocaleManager.EN) 1f else 0f).apply {
            duration = 220
            interpolator = DecelerateInterpolator()
            addUpdateListener {
                pos = it.animatedValue as Float
                invalidate()
            }
            start()
        }
        // let the thumb finish gliding before the screen is rebuilt in the new language
        postDelayed({ onLanguageSelected?.invoke(lang) }, 240)
    }
}
