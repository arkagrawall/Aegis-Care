package com.aegis.saathi.ui

import android.app.Activity
import android.util.TypedValue
import android.view.View
import android.widget.TextView
import androidx.core.content.ContextCompat
import com.aegis.saathi.R
import com.google.android.material.snackbar.Snackbar

/**
 * Confirmations and problems, in place of Android's small grey toasts (which vanish before many seniors have read
 * them): a large bar at the bottom of the screen, 20sp text, kept for 5 s, read out by TalkBack. Errors stay until
 * the senior taps "OK".
 */
object Notice {
    fun show(a: Activity, text: CharSequence, error: Boolean = false) {
        if (a.isFinishing) return
        val root = a.findViewById<View>(android.R.id.content) ?: return
        val bar = Snackbar.make(root, text, if (error) Snackbar.LENGTH_INDEFINITE else 5000)
        val v = bar.view
        v.setBackgroundColor(ContextCompat.getColor(a, if (error) R.color.bad else R.color.ink))
        v.findViewById<TextView>(com.google.android.material.R.id.snackbar_text)?.apply {
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 20f)
            maxLines = 6
            setTextColor(ContextCompat.getColor(a, R.color.surface))
        }
        v.findViewById<TextView>(com.google.android.material.R.id.snackbar_action)?.setTextSize(TypedValue.COMPLEX_UNIT_SP, 20f)
        if (error) bar.setAction(R.string.ok) { bar.dismiss() }
        bar.setActionTextColor(ContextCompat.getColor(a, R.color.accent))
        bar.show()
        v.announceForAccessibility(text)
    }
}
