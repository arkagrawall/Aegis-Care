package com.aegis.saathi.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.CountDownTimer
import android.view.WindowManager
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.aegis.saathi.A11yPrefs
import com.aegis.saathi.LocaleManager
import com.aegis.saathi.R
import com.aegis.saathi.call.ActiveCall
import com.aegis.saathi.call.CallApi
import com.aegis.saathi.databinding.ActivityEmergencyBinding
import kotlinx.coroutines.launch

/**
 * "Help is coming." Opens when the hub raises an emergency (the senior said "I am dying", pressed SOS, or fell).
 *
 *  - Saathi's alert agent is phoning the family: the screen says who, and offers to call them directly or 112.
 *  - No alert agent (no Sarvam number yet) or nobody answered: the phone dials the emergency contact itself
 *    after a 10-second countdown the senior can stop with "I'm safe".
 */
class EmergencyActivity : BaseActivity() {

    private lateinit var binding: ActivityEmergencyBinding
    private var timer: CountDownTimer? = null
    private var phone = ""
    private var name = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= 27) { setShowWhenLocked(true); setTurnScreenOn(true) }
        else @Suppress("DEPRECATION") window.addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        binding = ActivityEmergencyBinding.inflate(layoutInflater)
        setContentView(binding.root)
        listOf(binding.btnEmgCallFamily, binding.btnEmg112, binding.btnEmgSafe).forEach { it.pressable() }
        binding.btnEmgCallFamily.setOnClickListener { A11yPrefs.tap(it); dial() }
        binding.btnEmg112.setOnClickListener {
            A11yPrefs.tap(it)
            timer?.cancel()
            ActiveCall.hangUp()
            // Android lets only the dialer place emergency calls: this opens it with 112 ready
            startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:112")))
        }
        binding.btnEmgSafe.setOnClickListener {
            A11yPrefs.tap(it)
            timer?.cancel()
            val id = getSharedPreferences("aegis_senior_prefs", MODE_PRIVATE).getString("senior_id", null)
            if (id != null) lifecycleScope.launch { CallApi.cancelSos(id) }    // stops calls not yet placed
            finish()
        }
        show(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        show(intent)
    }

    private fun show(i: Intent) {
        timer?.cancel()
        phone = i.getStringExtra("contact_phone").orEmpty()
        name = i.getStringExtra("contact_name").orEmpty().ifEmpty { LocaleManager.string(this, R.string.emg_your_family) }
        val aiCalling = i.getBooleanExtra("ai_calling", false) && !i.getBooleanExtra("dial_now", false)
        binding.tvEmgCallFamily.text = getString(R.string.emg_call_person, name)
        binding.btnEmgCallFamily.visibility = if (phone.isEmpty()) android.view.View.GONE else android.view.View.VISIBLE
        when {
            aiCalling -> binding.tvEmgWho.text = getString(R.string.emg_ai_calling, name)
            phone.isEmpty() -> binding.tvEmgWho.text = getString(R.string.emg_no_contact)
            else -> timer = object : CountDownTimer(10_000L, 1_000L) {
                override fun onTick(ms: Long) {
                    binding.tvEmgWho.text = getString(R.string.emg_dialling_in, name, ((ms + 999) / 1000).toInt())
                }
                override fun onFinish() = dial()
            }.start()
        }
    }

    private fun dial() {
        timer?.cancel()
        if (phone.isEmpty()) return
        ActiveCall.hangUp()                              // a Saathi call would hold the microphone and earpiece
        val canCall = ContextCompat.checkSelfPermission(this, Manifest.permission.CALL_PHONE) == PackageManager.PERMISSION_GRANTED
        val uri = Uri.parse("tel:" + phone.filter { it.isDigit() || it == '+' })
        try {
            startActivity(Intent(if (canCall) Intent.ACTION_CALL else Intent.ACTION_DIAL, uri))
        } catch (_: Exception) {
            startActivity(Intent(Intent.ACTION_DIAL, uri))
        }
        binding.tvEmgWho.text = getString(R.string.emg_calling_now, name)
    }

    override fun onDestroy() {
        timer?.cancel()
        super.onDestroy()
    }
}
