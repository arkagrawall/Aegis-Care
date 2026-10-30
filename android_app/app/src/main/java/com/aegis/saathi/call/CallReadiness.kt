package com.aegis.saathi.call

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import android.util.Log
import androidx.core.app.NotificationManagerCompat
import com.aegis.saathi.service.CallListenerService

/**
 * Can Saathi's call actually reach the senior? Two phone settings decide it, beyond the normal permissions:
 *  - full-screen calls (Android 14+ lets people switch them off): without it a locked phone only shows a notification,
 *  - battery optimisation: some phones (Motorola, Xiaomi, ...) close the call listener to save battery.
 */
object CallReadiness {
    private const val TAG = "CallReadiness"

    fun ringsOnLockScreen(c: Context): Boolean =
        NotificationManagerCompat.from(c).areNotificationsEnabled() && CallListenerService.canShowFullScreen(c)

    fun batteryExempt(c: Context): Boolean =
        (c.getSystemService(Context.POWER_SERVICE) as PowerManager).isIgnoringBatteryOptimizations(c.packageName)

    /** Opens the one settings page that fixes lock-screen ringing on this phone. */
    fun openLockScreenSetting(a: Activity) {
        val pkg = Uri.parse("package:${a.packageName}")
        val intent = when {
            !NotificationManagerCompat.from(a).areNotificationsEnabled() ->
                Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, a.packageName)
            Build.VERSION.SDK_INT >= 34 -> Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT, pkg)
            else -> Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, a.packageName)
        }
        open(a, intent)
    }

    /** The system's own "Allow Saathi to run in the background?" dialog. */
    @SuppressLint("BatteryLife")   // a calling app is an allowed use of this request
    fun askBatteryExemption(a: Activity) {
        if (batteryExempt(a)) return
        open(a, Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:${a.packageName}")))
    }

    /** After setup's permissions: ask for whichever of the two is still missing, one at a time. */
    fun askMissing(a: Activity) {
        when {
            !ringsOnLockScreen(a) -> openLockScreenSetting(a)
            !batteryExempt(a) -> askBatteryExemption(a)
        }
    }

    private fun open(a: Activity, intent: Intent) {
        try {
            a.startActivity(intent)
        } catch (e: Exception) {
            Log.w(TAG, "settings: ${e.message}")
            try {
                a.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${a.packageName}")))
            } catch (_: Exception) {}
        }
    }
}
