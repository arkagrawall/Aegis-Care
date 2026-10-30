package com.aegis.saathi.ui

import android.app.NotificationManager
import android.content.Context
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import android.widget.Toast
import androidx.lifecycle.lifecycleScope
import com.aegis.saathi.A11yPrefs
import com.aegis.saathi.LocaleManager
import com.aegis.saathi.R
import com.aegis.saathi.call.SpeechPlayer
import com.aegis.saathi.databinding.ActivityDoseReminderBinding
import com.aegis.saathi.meds.CareRepo
import com.aegis.saathi.meds.DoseAlarms
import kotlinx.coroutines.launch

/**
 * "Time for your BP tablet": opens over the lock screen when a dose alarm rings, says it out loud,
 * and takes one tap: Taken, Remind me in 15 minutes, or Skip. Only the care manager's own words are shown.
 */
class DoseReminderActivity : BaseActivity() {

    private lateinit var binding: ActivityDoseReminderBinding
    private val player by lazy { SpeechPlayer(this, callChannel = false) }
    private var medId = ""
    private var time = ""
    private var name = ""
    private var doseText = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= 27) { setShowWhenLocked(true); setTurnScreenOn(true) }
        else @Suppress("DEPRECATION") window.addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        binding = ActivityDoseReminderBinding.inflate(layoutInflater)
        setContentView(binding.root)

        medId = intent.getStringExtra("med_id").orEmpty()
        time = intent.getStringExtra("time").orEmpty()
        name = intent.getStringExtra("name").orEmpty()
        doseText = intent.getStringExtra("dose_text").orEmpty()

        binding.tvDoseClock.text = time
        binding.tvDoseMedName.text = name
        binding.tvDoseMedText.text = doseText
        binding.tvDoseMedText.visibility = if (doseText.isEmpty()) android.view.View.GONE else android.view.View.VISIBLE

        listOf(binding.btnReminderTaken, binding.btnReminderLater, binding.btnReminderSkip, binding.btnDoseSpeak).forEach { it.pressable() }
        binding.btnReminderTaken.setOnClickListener { A11yPrefs.tap(it); answer("taken") }
        binding.btnReminderSkip.setOnClickListener { A11yPrefs.tap(it); answer("skipped") }
        binding.btnReminderLater.setOnClickListener {
            A11yPrefs.tap(it)
            DoseAlarms.snooze(this, medId, time, name, doseText)
            val now = java.util.Calendar.getInstance().apply { timeInMillis = CareRepo.now() }
            CareRepo.snooze(this, "$medId@$time", now.get(java.util.Calendar.HOUR_OF_DAY) * 60 + now.get(java.util.Calendar.MINUTE) + 15)
            lifecycleScope.launch { CareRepo.answerDose(this@DoseReminderActivity, medId, time, "later") }
            Toast.makeText(this, getString(R.string.dose_snoozed), Toast.LENGTH_LONG).show()
            close()
        }
        binding.btnDoseSpeak.setOnClickListener { speak() }
        binding.ivDosePill.popIn()
        if (savedInstanceState == null) speak()
    }

    private fun speak() {
        val seniorName = getSharedPreferences("aegis_senior_prefs", Context.MODE_PRIVATE).getString("senior_name", "").orEmpty()
        val first = seniorName.trim().split(" ").firstOrNull().orEmpty()
        val line = getString(R.string.dose_spoken, first, name) + if (doseText.isNotEmpty()) " $doseText." else ""
        lifecycleScope.launch { player.say(line, english = LocaleManager.current(this@DoseReminderActivity) == LocaleManager.EN) }
    }

    private fun answer(status: String) {
        binding.btnReminderTaken.isEnabled = false
        binding.btnReminderSkip.isEnabled = false
        lifecycleScope.launch {
            CareRepo.answerDose(this@DoseReminderActivity, medId, time, status)   // queued if offline
            Toast.makeText(this@DoseReminderActivity,
                getString(if (status == "taken") R.string.dose_thanks else R.string.dose_skipped_note), Toast.LENGTH_LONG).show()
            close()
        }
    }

    private fun close() {
        (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).cancel(DoseAlarms.NOTIF_ID)
        player.stop()
        finish()
    }

    override fun onDestroy() {
        player.release()
        super.onDestroy()
    }
}
