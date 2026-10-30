package com.aegis.saathi.meds

import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import com.aegis.saathi.LocaleManager
import com.aegis.saathi.R
import com.aegis.saathi.ui.DoseReminderActivity
import java.util.Calendar

/**
 * One alarm per medicine time, every day. The alarm rings like a phone call and opens the
 * full-screen dose reminder, even when the phone is locked; then the same time tomorrow is armed.
 */
object DoseAlarms {
    private const val TAG = "DoseAlarms"
    const val CHANNEL = "aegis_dose_channel"
    const val NOTIF_ID = 4711
    private const val PREFS = "aegis_senior_prefs"

    private fun code(medId: String, time: String) = (medId + "@" + time).hashCode()

    private fun pending(c: Context, medId: String, time: String, name: String, doseText: String, flags: Int): PendingIntent? =
        PendingIntent.getBroadcast(
            c, code(medId, time),
            Intent(c, DoseAlarmReceiver::class.java)
                .putExtra("med_id", medId).putExtra("time", time).putExtra("name", name).putExtra("dose_text", doseText),
            flags or PendingIntent.FLAG_IMMUTABLE
        )

    /** Next moment this HH:MM happens (today if still ahead, otherwise tomorrow), or `after` + snooze. */
    private fun nextAt(time: String, afterMs: Long = System.currentTimeMillis()): Long {
        val (h, m) = time.split(":").map { it.toInt() }
        val cal = Calendar.getInstance().apply {
            timeInMillis = afterMs
            set(Calendar.HOUR_OF_DAY, h); set(Calendar.MINUTE, m); set(Calendar.SECOND, 0); set(Calendar.MILLISECOND, 0)
        }
        if (cal.timeInMillis <= afterMs) cal.add(Calendar.DAY_OF_YEAR, 1)
        return cal.timeInMillis
    }

    private fun set(c: Context, atMs: Long, pi: PendingIntent) {
        val am = c.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        try {
            if (Build.VERSION.SDK_INT < 31 || am.canScheduleExactAlarms()) {
                am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, atMs, pi)
            } else {
                am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, atMs, pi)   // may ring a few minutes late
            }
        } catch (e: SecurityException) {
            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, atMs, pi)
        }
    }

    /** Replaces every alarm with one per (medicine, time) in the current list. */
    fun armAll(c: Context, meds: List<CareRepo.Medicine>) {
        val prefs = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val am = c.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        prefs.getStringSet("dose_alarms", emptySet())!!.forEach { key ->
            val (id, t) = key.split("|", limit = 2).let { it[0] to it.getOrElse(1) { "" } }
            pending(c, id, t, "", "", PendingIntent.FLAG_NO_CREATE)?.let { am.cancel(it) }
        }
        val armed = mutableSetOf<String>()
        for (m in meds) for (t in m.times) {
            val pi = pending(c, m.id, t, m.name, m.doseText, PendingIntent.FLAG_UPDATE_CURRENT) ?: continue
            set(c, nextAt(t), pi)
            armed += m.id + "|" + t
        }
        prefs.edit().putStringSet("dose_alarms", armed).apply()
        Log.i(TAG, "armed ${armed.size} dose alarms")
    }

    /** "Remind me in 15 minutes". */
    fun snooze(c: Context, medId: String, time: String, name: String, doseText: String, minutes: Int = 15) {
        // a separate request code so tomorrow's regular alarm is not replaced
        val pi = PendingIntent.getBroadcast(
            c, code(medId, time) + 1,
            Intent(c, DoseAlarmReceiver::class.java)
                .putExtra("med_id", medId).putExtra("time", time).putExtra("name", name).putExtra("dose_text", doseText)
                .putExtra("snoozed", true),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        set(c, System.currentTimeMillis() + minutes * 60_000L, pi)
    }

    fun ensureChannel(c: Context) {
        if (Build.VERSION.SDK_INT < 26) return
        val nm = c.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (nm.getNotificationChannel(CHANNEL) != null) return
        val audio = AudioAttributes.Builder()
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .setUsage(AudioAttributes.USAGE_ALARM)
            .build()
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL, LocaleManager.string(c, R.string.notif_ch_dose), NotificationManager.IMPORTANCE_HIGH).apply {
                description = LocaleManager.string(c, R.string.notif_ch_dose_desc)
                setSound(RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM), audio)
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 800, 400, 800)
                lockscreenVisibility = Notification.VISIBILITY_PUBLIC
            }
        )
    }

    /** Called when an alarm fires: rings and opens the dose screen, and arms the same time tomorrow. */
    fun fire(c: Context, i: Intent) {
        val medId = i.getStringExtra("med_id") ?: return
        val time = i.getStringExtra("time") ?: return
        val name = i.getStringExtra("name").orEmpty()
        val doseText = i.getStringExtra("dose_text").orEmpty()
        if (!i.getBooleanExtra("snoozed", false)) {
            pending(c, medId, time, name, doseText, PendingIntent.FLAG_UPDATE_CURRENT)?.let { set(c, nextAt(time, System.currentTimeMillis() + 60_000), it) }
        }
        ensureChannel(c)
        CareRepo.nudge()
        val open = Intent(c, DoseReminderActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtras(i)
        }
        val pi = PendingIntent.getActivity(c, NOTIF_ID, open, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val n = NotificationCompat.Builder(c, CHANNEL)
            .setSmallIcon(R.drawable.ic_pill)
            .setContentTitle(LocaleManager.string(c, R.string.dose_notif_title, name))
            .setContentText(doseText.ifEmpty { LocaleManager.string(c, R.string.dose_notif_text) })
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setAutoCancel(true)
            .setContentIntent(pi)
            .setFullScreenIntent(pi, true)
            .setTimeoutAfter(30 * 60_000L)
            .build()
        (c.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).notify(NOTIF_ID, n)
        try { c.startActivity(open) } catch (e: Exception) { Log.w(TAG, "startActivity: ${e.message}") }
    }
}

class DoseAlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) = DoseAlarms.fire(context, intent)
}

/** Alarms do not survive a restart of the phone or an app update; set them again from the cached list. */
class DoseBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        DoseAlarms.armAll(context, CareRepo.cachedMedicines(context))
    }
}
