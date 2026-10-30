package com.aegis.saathi

import android.content.Context
import android.content.res.Configuration
import android.view.HapticFeedbackConstants
import android.view.View

/**
 * The senior's own accessibility choices, set on the "Me" tab: text size (on top of the phone's own
 * font size), a high-contrast look, reading cards aloud, and a small vibration on every press.
 */
object A11yPrefs {
    private const val PREFS = "aegis_senior_prefs"
    const val SIZE_NORMAL = 0
    const val SIZE_LARGE = 1
    const val SIZE_XLARGE = 2
    private val SCALE = floatArrayOf(1f, 1.15f, 1.3f)

    private fun p(c: Context) = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun textSize(c: Context): Int = p(c).getInt("text_size", SIZE_NORMAL).coerceIn(0, 2)
    fun setTextSize(c: Context, v: Int) = p(c).edit().putInt("text_size", v).apply()

    fun highContrast(c: Context): Boolean = p(c).getBoolean("high_contrast", false)
    fun setHighContrast(c: Context, on: Boolean) = p(c).edit().putBoolean("high_contrast", on).apply()

    fun readAloud(c: Context): Boolean = p(c).getBoolean("read_aloud", true)
    fun setReadAloud(c: Context, on: Boolean) = p(c).edit().putBoolean("read_aloud", on).apply()

    fun haptics(c: Context): Boolean = p(c).getBoolean("haptics", true)
    fun setHaptics(c: Context, on: Boolean) = p(c).edit().putBoolean("haptics", on).apply()

    /** Multiplies the phone's font scale by the chosen text size. */
    fun wrap(base: Context): Context {
        val extra = SCALE[textSize(base)]
        if (extra == 1f) return base
        val config = Configuration(base.resources.configuration)
        config.fontScale = base.resources.configuration.fontScale * extra
        return base.createConfigurationContext(config)
    }

    fun tap(v: View) {
        if (haptics(v.context)) v.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
    }

    /**
     * High contrast without a second set of layouts: soft grey text becomes full ink, card and button
     * outlines become 2dp dark lines, and the pale page background becomes white.
     * Only light screens are touched; the dark call screens already have strong contrast.
     */
    fun applyContrast(root: View) {
        if (!highContrast(root.context)) return
        val ink = 0xFF000000.toInt()
        val res = root.context
        val soft = setOf(
            androidx.core.content.ContextCompat.getColor(res, R.color.ink_soft),
            androidx.core.content.ContextCompat.getColor(res, R.color.ink_faint),
            0xFF8A9893.toInt()   // the old caption grey, in case a view still hard-codes it
        )
        val line = (2 * root.resources.displayMetrics.density).toInt()
        fun walk(v: View) {
            if (v is android.widget.TextView && v.currentTextColor in soft) v.setTextColor(ink)
            (v.background as? android.graphics.drawable.GradientDrawable)?.let { g ->
                val color = g.color?.defaultColor
                // white surfaces (cards, outline buttons) get a dark outline
                if (color == 0xFFFFFFFF.toInt()) { g.mutate(); (g as android.graphics.drawable.GradientDrawable).setStroke(line, 0xFF1A2B28.toInt()) }
            }
            if (v.background is android.graphics.drawable.ColorDrawable &&
                (v.background as android.graphics.drawable.ColorDrawable).color == 0xFFF5F7F4.toInt()) v.setBackgroundColor(0xFFFFFFFF.toInt())
            if (v is android.view.ViewGroup) for (i in 0 until v.childCount) walk(v.getChildAt(i))
        }
        walk(root)
    }
}
