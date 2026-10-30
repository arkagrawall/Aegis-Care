package com.aegis.saathi.ui

import android.view.View
import android.widget.Button
import android.widget.RadioButton
import android.widget.TextView
import androidx.core.view.AccessibilityDelegateCompat
import androidx.core.view.ViewCompat
import androidx.core.view.accessibility.AccessibilityNodeInfoCompat
import com.aegis.saathi.A11yPrefs

/**
 * Screen-reader helpers. Most of our buttons are styled TextViews / LinearLayouts so they can be big and
 * bilingual; these give them what a real Button has: the "button" role, one clear label and an on/off state.
 */
object A11y {
    /** A press felt in the hand, if the senior wants it. */
    fun tap(v: View) = A11yPrefs.tap(v)

    /** Announced as "<label>, button". Children are folded into one stop. */
    fun button(v: View, label: CharSequence? = null) {
        role(v, Button::class.java.name)
        if (label != null) v.contentDescription = label
    }

    /** A choice among several (text size, language): "<label>, radio button, selected". */
    fun choice(v: View, label: CharSequence, selected: Boolean) {
        role(v, RadioButton::class.java.name, checkable = true, checked = selected)
        v.contentDescription = label
    }

    /** A toggle (speaker, mute): the state is read out with the label, never shown by colour alone. */
    fun toggle(v: View, label: CharSequence, on: Boolean, onText: CharSequence, offText: CharSequence) {
        button(v, label)
        ViewCompat.setStateDescription(v, if (on) onText else offText)
    }

    fun heading(v: TextView) = ViewCompat.setAccessibilityHeading(v, true)

    /**
     * Every tappable card, tile and row on a screen that is not already a real Button gets the button role, so
     * TalkBack says "Taken, button" instead of just "Taken". Views that set their own role (A11y.button / choice /
     * toggle, the SOS button, the language switch) are left alone because they do so after this runs or override it.
     */
    fun markButtons(root: View) {
        fun walk(v: View) {
            val plain = v !is android.widget.Button && v !is android.widget.CompoundButton && v !is android.widget.EditText &&
                v !is android.widget.AdapterView<*> && v !is SosButton && v !is LanguageToggle
            if (plain && v.hasOnClickListeners() && v.isClickable && ViewCompat.getAccessibilityDelegate(v) == null) button(v)
            if (v is android.view.ViewGroup) for (i in 0 until v.childCount) walk(v.getChildAt(i))
        }
        walk(root)
    }

    private fun role(v: View, className: String, checkable: Boolean = false, checked: Boolean = false) {
        v.isFocusable = true
        if (v is android.view.ViewGroup) v.importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_YES
        ViewCompat.setAccessibilityDelegate(v, object : AccessibilityDelegateCompat() {
            override fun onInitializeAccessibilityNodeInfo(host: View, info: AccessibilityNodeInfoCompat) {
                super.onInitializeAccessibilityNodeInfo(host, info)
                info.className = className
                if (checkable) {
                    info.isCheckable = true
                    info.isChecked = checked
                }
            }
        })
    }
}
