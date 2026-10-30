package com.aegis.saathi.ui

import android.content.Context
import android.content.Intent
import android.content.res.ColorStateList
import android.widget.TextView
import androidx.core.content.ContextCompat
import com.aegis.saathi.A11yPrefs
import com.aegis.saathi.R
import com.aegis.saathi.api.ServerConfig
import com.aegis.saathi.ble.WatchLink
import com.aegis.saathi.ble.WatchState
import com.aegis.saathi.call.CallReadiness
import com.aegis.saathi.databinding.PageMeBinding
import com.aegis.saathi.service.CallListenerService

/**
 * The Me tab: language, the senior's accessibility choices (text size, high contrast, read aloud,
 * vibration), fall detection, the missed-call check-in, the watch and the server address.
 * Text size and contrast rebuild the screen so every view picks them up.
 */
class MeTab(private val act: MainActivity, private val b: PageMeBinding) {

    private val prefs = act.getSharedPreferences("aegis_senior_prefs", Context.MODE_PRIVATE)

    init {
        b.langToggleMe.onLanguageSelected = { lang -> act.changeLanguage(lang) }
        b.tvMeName.text = prefs.getString("senior_name", "").orEmpty()

        val sizes = listOf(b.sizeNormal, b.sizeLarge, b.sizeXLarge)
        sizes.forEachIndexed { i, v ->
            v.pressable()
            v.setOnClickListener {
                A11yPrefs.tap(it)
                if (A11yPrefs.textSize(act) != i) {
                    A11yPrefs.setTextSize(act, i)
                    act.rebuild(MainActivity.TAB_ME)
                }
            }
        }
        markSize(sizes, A11yPrefs.textSize(act))

        b.swContrast.isChecked = A11yPrefs.highContrast(act)
        b.swContrast.setOnCheckedChangeListener { v, on ->
            A11yPrefs.tap(v); A11yPrefs.setHighContrast(act, on); act.rebuild(MainActivity.TAB_ME)
        }
        b.swReadAloud.isChecked = A11yPrefs.readAloud(act)
        b.swReadAloud.setOnCheckedChangeListener { v, on -> A11yPrefs.tap(v); A11yPrefs.setReadAloud(act, on); act.refreshReadAloud() }
        b.swHaptics.isChecked = A11yPrefs.haptics(act)
        b.swHaptics.setOnCheckedChangeListener { v, on -> A11yPrefs.setHaptics(act, on); A11yPrefs.tap(v) }

        b.swFall.isChecked = prefs.getBoolean(CallListenerService.PREF_FALL_DETECT, false)
        b.swFall.setOnCheckedChangeListener { v, on ->
            A11yPrefs.tap(v)
            prefs.edit().putBoolean(CallListenerService.PREF_FALL_DETECT, on).apply()
            CallListenerService.refreshFallDetection(act)
            act.toastText(act.getString(if (on) R.string.fall_enabled else R.string.fall_disabled))
        }

        b.tvMissedCallSub.text = act.getString(R.string.me_missed_call_sub)
        b.rowMissedCall.pressable(0.98f)
        b.rowMissedCall.setOnClickListener { A11yPrefs.tap(it); act.missedCallCheckin() }
        b.rowWatch.pressable(0.98f)
        b.rowWatch.setOnClickListener { act.startActivity(Intent(act, WatchActivity::class.java)) }
        b.rowReadings.pressable(0.98f)
        b.rowReadings.setOnClickListener { A11yPrefs.tap(it); act.showReadingsDialog() }
        b.rowIntro.pressable(0.98f)
        b.rowIntro.setOnClickListener { act.startActivity(Intent(act, IntroActivity::class.java).putExtra(IntroActivity.REPLAY, true)) }
        b.rowCallReady.pressable(0.98f)
        b.rowCallReady.setOnClickListener {
            A11yPrefs.tap(it)
            if (!CallReadiness.ringsOnLockScreen(act)) CallReadiness.openLockScreenSetting(act)
            else CallReadiness.askBatteryExemption(act)
        }
        renderCallReadiness()
        b.tvMeServer.text = ServerConfig.saved(act)
        b.rowServer.pressable(0.98f)
        b.rowServer.setOnClickListener { act.startActivity(Intent(act, SettingsActivity::class.java)) }

        b.tvVersion.text = runCatching {
            "Aegis Saathi " + act.packageManager.getPackageInfo(act.packageName, 0).versionName
        }.getOrDefault("Aegis Saathi")
        A11yPrefs.applyContrast(b.root)
    }

    /** "Calls will ring on the lock screen ✓" or, in warning colours, what to tap to fix it. */
    fun renderCallReadiness() {
        val lock = CallReadiness.ringsOnLockScreen(act)
        val ok = lock && CallReadiness.batteryExempt(act)
        b.tvCallReady.text = act.getString(if (lock) R.string.me_calls_lock_ok else R.string.me_calls_lock_off)
        b.tvCallReadySub.text = act.getString(if (ok) R.string.perm_lock_title else R.string.perm_battery_sub)
        b.tvCallReadySub.visibility = if (lock && !ok) android.view.View.VISIBLE else android.view.View.GONE
        b.ivCallReady.setImageResource(if (ok) R.drawable.ic_shield_check else R.drawable.ic_warning)
        b.ivCallReady.imageTintList = ColorStateList.valueOf(ContextCompat.getColor(act, if (ok) R.color.good else R.color.warn))
        b.ivCallReady.setBackgroundResource(if (ok) R.drawable.bg_circle_good_soft else R.drawable.bg_circle_warn_soft)
        b.ivCallReadyArrow.visibility = if (ok) android.view.View.GONE else android.view.View.VISIBLE
        b.rowCallReady.isClickable = !ok
        A11y.button(b.rowCallReady, b.tvCallReady.text)
    }

    private fun markSize(views: List<TextView>, chosen: Int) {
        views.forEachIndexed { i, v ->
            val on = i == chosen
            v.setBackgroundResource(if (on) R.drawable.bg_btn_teal else R.drawable.bg_btn_outline)
            v.setTextColor(ContextCompat.getColor(act, if (on) android.R.color.white else R.color.ink))
            v.isSelected = on
            // "Large text, radio button, selected": a name, not just "A+", and the choice is not colour-only
            A11y.choice(v, act.getString(listOf(R.string.size_normal_a11y, R.string.size_large_a11y, R.string.size_xlarge_a11y)[i]), on)
        }
    }

    fun renderWatch(st: WatchState) {
        b.tvMeWatch.text = when (st.link) {
            WatchLink.CONNECTED -> if (st.demo) act.getString(R.string.watch_demo_on) else act.getString(R.string.watch_card_connected, st.deviceName)
            WatchLink.CONNECTING, WatchLink.RECONNECTING -> act.getString(R.string.watch_card_reconnecting)
            WatchLink.NONE -> act.getString(R.string.watch_card_none)
        }
    }
}
