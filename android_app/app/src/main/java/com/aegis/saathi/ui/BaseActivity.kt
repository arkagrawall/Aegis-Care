package com.aegis.saathi.ui

import android.content.Context
import android.content.res.Configuration
import android.graphics.Color
import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.aegis.saathi.A11yPrefs
import com.aegis.saathi.LocaleManager

/**
 * Every screen extends this so the Hindi/English choice and the text size apply everywhere, and so
 * no screen draws under the status bar or the gesture bar (Android 15 draws every app edge to edge).
 */
open class BaseActivity : AppCompatActivity() {

    companion object {
        /** How many of our screens are visible: the call service only opens a screen itself while one is. */
        @Volatile var visibleScreens = 0
            private set
    }

    override fun onStart() {
        super.onStart()
        visibleScreens++
    }

    override fun onStop() {
        visibleScreens = maxOf(0, visibleScreens - 1)
        super.onStop()
    }

    override fun attachBaseContext(newBase: Context) {
        super.attachBaseContext(A11yPrefs.wrap(LocaleManager.wrap(newBase)))
    }

    // AppCompat re-applies its own configuration after attachBaseContext and would drop our locale
    override fun applyOverrideConfiguration(overrideConfiguration: Configuration?) {
        if (overrideConfiguration != null) {
            val uiMode = overrideConfiguration.uiMode
            overrideConfiguration.setTo(baseContext.resources.configuration)
            overrideConfiguration.uiMode = uiMode
        }
        super.applyOverrideConfiguration(overrideConfiguration)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        // bar icons follow the theme: dark icons on the light screens, light icons on the dark call screens
        val a = theme.obtainStyledAttributes(intArrayOf(android.R.attr.windowLightStatusBar))
        val lightBars = a.getBoolean(0, true)
        a.recycle()
        val style = if (lightBars) SystemBarStyle.light(Color.TRANSPARENT, Color.TRANSPARENT)
                    else SystemBarStyle.dark(Color.TRANSPARENT)
        enableEdgeToEdge(statusBarStyle = style, navigationBarStyle = style)
        super.onCreate(savedInstanceState)
    }

    override fun onPostCreate(savedInstanceState: Bundle?) {
        super.onPostCreate(savedInstanceState)
        // click listeners are set by now: give tappable cards and tiles the button role for TalkBack
        findViewById<ViewGroup>(android.R.id.content)?.let { A11y.markButtons(it) }
    }

    /**
     * Screens that place their own bars (the home screen's bottom navigation) return false and
     * call [padForSystemBars] on the right views themselves.
     */
    protected open val padRootForSystemBars: Boolean = true

    override fun onContentChanged() {
        super.onContentChanged()
        val root = findViewById<ViewGroup>(android.R.id.content)?.getChildAt(0) ?: return
        A11yPrefs.applyContrast(root)
        if (padRootForSystemBars) padForSystemBars(root, top = true, bottom = true)
    }

    /** Adds the status bar / gesture bar / keyboard height to the view's own padding, kept up to date. */
    fun padForSystemBars(view: View, top: Boolean, bottom: Boolean, sides: Boolean = true) {
        val base = intArrayOf(view.paddingLeft, view.paddingTop, view.paddingRight, view.paddingBottom)
        ViewCompat.setOnApplyWindowInsetsListener(view) { v, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            val ime = insets.getInsets(WindowInsetsCompat.Type.ime())
            v.setPadding(
                base[0] + if (sides) bars.left else 0,
                base[1] + if (top) bars.top else 0,
                base[2] + if (sides) bars.right else 0,
                base[3] + if (bottom) maxOf(bars.bottom, ime.bottom) else 0,
            )
            insets
        }
        ViewCompat.requestApplyInsets(view)
    }
}
