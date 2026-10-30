package com.aegis.saathi.ui

import android.Manifest
import android.animation.ObjectAnimator
import android.animation.ValueAnimator
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.os.Build
import android.os.Bundle
import android.view.View
import android.view.inputmethod.InputMethodManager
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.aegis.saathi.LocaleManager
import com.aegis.saathi.R
import com.aegis.saathi.api.AegisApiClient
import com.aegis.saathi.ble.WatchRepository
import com.aegis.saathi.databinding.ActivityOnboardingBinding
import kotlinx.coroutines.launch

/**
 * First-run setup as a 4-step wizard (one question per screen, big inputs):
 *   0 welcome + language -> 1 name & age -> 2 care manager code / city / family phone -> 3 permissions
 * If the server cannot be reached the senior is NOT silently registered; they get Retry / Settings.
 */
class OnboardingActivity : BaseActivity() {

    private lateinit var binding: ActivityOnboardingBinding
    private lateinit var prefs: SharedPreferences
    private var step = 0

    private val steps by lazy { listOf(binding.step0, binding.step1, binding.step2, binding.step3) }
    private val dots by lazy { listOf(binding.dot0, binding.dot1, binding.dot2, binding.dot3) }

    private val permissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
            updatePermStatus()
            // then the two phone settings that let a call ring on a locked phone and keep Saathi listening
            com.aegis.saathi.call.CallReadiness.askMissing(this)
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityOnboardingBinding.inflate(layoutInflater)
        setContentView(binding.root)

        prefs = getSharedPreferences("aegis_senior_prefs", Context.MODE_PRIVATE)

        // Already set up? Go straight to the home screen
        if (prefs.getBoolean("is_onboarded", false)) {
            startActivity(Intent(this, MainActivity::class.java))
            finish()
            return
        }
        // First time: the welcome slides come before the setup questions
        if (!prefs.getBoolean("intro_seen", false)) {
            startActivity(Intent(this, IntroActivity::class.java))
            finish()
            return
        }

        binding.btnMore.setOnClickListener { SettingsMenu.show(this, it) }
        binding.langToggle.onLanguageSelected = { lang -> switchLanguage(lang) }
        binding.tileHi.setOnClickListener { chooseLanguage(LocaleManager.HI) }
        binding.tileEn.setOnClickListener { chooseLanguage(LocaleManager.EN) }
        listOf(binding.btnNext, binding.btnBack, binding.btnGrantPerms, binding.tileHi, binding.tileEn).forEach { it.pressable() }
        binding.btnNext.setOnClickListener { onNext() }
        binding.btnBack.setOnClickListener { if (step > 0) showStep(step - 1) }
        binding.btnGrantPerms.setOnClickListener { requestPermissions() }

        // restore the step after the screen was rebuilt (language change, rotation)
        step = savedInstanceState?.getInt("step", 0) ?: 0
        showStep(step, animate = false)
        updateLanguageTiles()
        updatePermStatus()
        binding.root.alpha = 0f
        binding.root.animate().alpha(1f).setDuration(220).start()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putInt("step", step)
    }

    // ------------------------------------------------------------------------------ language
    private fun chooseLanguage(lang: String) {
        binding.root.tick()
        switchLanguage(lang)
    }

    private fun switchLanguage(lang: String) {
        if (lang == LocaleManager.current(this) && LocaleManager.isChosen(this)) return
        LocaleManager.set(this, lang)
        binding.onbRoot.animate().alpha(0f).setDuration(140).withEndAction { recreate() }.start()
    }

    private fun updateLanguageTiles() {
        val chosenHi = LocaleManager.current(this) == LocaleManager.HI
        binding.tileHi.setBackgroundResource(if (chosenHi) R.drawable.bg_tile_selected else R.drawable.bg_btn_outline)
        binding.tileEn.setBackgroundResource(if (!chosenHi) R.drawable.bg_tile_selected else R.drawable.bg_btn_outline)
        binding.checkHi.visibility = if (chosenHi) View.VISIBLE else View.GONE
        binding.checkEn.visibility = if (!chosenHi) View.VISIBLE else View.GONE
        A11y.choice(binding.tileHi, "हिंदी", chosenHi)
        A11y.choice(binding.tileEn, "English", !chosenHi)
    }

    // ------------------------------------------------------------------------------ steps
    private fun showStep(newStep: Int, animate: Boolean = true) {
        val old = steps[step]
        val forward = newStep >= step
        val target = steps[newStep]
        hideKeyboard()

        if (animate && newStep != step) {
            val dir = if (forward) 1f else -1f
            old.animate().alpha(0f).translationX(-dir * binding.root.dpf(36)).setDuration(140).withEndAction {
                old.visibility = View.GONE
                old.alpha = 1f
                old.translationX = 0f
            }.start()
            target.visibility = View.VISIBLE
            target.alpha = 0f
            target.translationX = dir * binding.root.dpf(36)
            target.animate().alpha(1f).translationX(0f).setStartDelay(110).setDuration(240).start()
        } else {
            steps.forEach { it.visibility = View.GONE }
            target.visibility = View.VISIBLE
        }
        step = newStep

        binding.btnBack.visibility = if (step > 0) View.VISIBLE else View.GONE
        binding.tvNext.text = getString(
            when (step) {
                0 -> R.string.onb_btn_start
                3 -> R.string.onb_btn_finish
                else -> R.string.onb_btn_next
            }
        )
        binding.ivNext.setImageResource(if (step == 3) R.drawable.ic_check else R.drawable.ic_arrow_right)
        updateDots(animate)
    }

    private fun updateDots(animate: Boolean) {
        val active = ContextCompat.getColor(this, R.color.primary)
        val idle = ContextCompat.getColor(this, R.color.line_strong)
        dots.forEachIndexed { i, dot ->
            val width = ((if (i == step) 28 else 8) * resources.displayMetrics.density).toInt()
            dot.backgroundTintList = ColorStateList.valueOf(if (i <= step) active else idle)
            if (animate) {
                ValueAnimator.ofInt(dot.layoutParams.width, width).apply {
                    duration = 220
                    addUpdateListener {
                        dot.layoutParams.width = it.animatedValue as Int
                        dot.requestLayout()
                    }
                    start()
                }
            } else {
                dot.layoutParams.width = width
                dot.requestLayout()
            }
        }
    }

    private fun onNext() {
        binding.btnNext.tick()
        when (step) {
            0 -> showStep(1)
            1 -> {
                val name = binding.etSeniorName.text.toString().trim()
                val age = binding.etSeniorAge.text.toString().toIntOrNull()
                when {
                    name.isEmpty() -> invalid(binding.etSeniorName, R.string.err_name)
                    age == null || age !in 1..120 -> invalid(binding.etSeniorAge, R.string.err_age)
                    else -> showStep(2)
                }
            }
            2 -> {
                binding.tvCoordError.visibility = View.GONE
                if (binding.etCoordCode.text.toString().trim().isEmpty()) invalid(binding.etCoordCode, R.string.err_code)
                else showStep(3)
            }
            else -> {
                if (!binding.cbConsent.isChecked) invalid(binding.cbConsent, R.string.err_consent) else complete()
            }
        }
    }

    private fun invalid(field: View, message: Int) {
        field.requestFocus()
        ObjectAnimator.ofFloat(field, View.TRANSLATION_X, 0f, -16f, 16f, -10f, 10f, 0f).setDuration(350).start()
        Notice.show(this, getString(message), error = true)
    }

    private fun hideKeyboard() {
        val imm = getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager
        imm.hideSoftInputFromWindow(binding.root.windowToken, 0)
    }

    // ------------------------------------------------------------------------- permissions
    private fun requestPermissions() {
        // CALL_PHONE: in an emergency the phone can ring the family itself when Saathi's alert call cannot
        val wanted = mutableListOf(Manifest.permission.RECORD_AUDIO, Manifest.permission.CALL_PHONE)
        if (Build.VERSION.SDK_INT >= 33) wanted.add(Manifest.permission.POST_NOTIFICATIONS)
        permissionLauncher.launch(wanted.toTypedArray())
    }

    private fun updatePermStatus() {
        val mic = ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        binding.tvPermStatus.text = getString(if (mic) R.string.perm_granted else R.string.perm_denied_hint)
        binding.btnGrantPerms.visibility = if (mic) View.GONE else View.VISIBLE
    }

    // ------------------------------------------------------------------------------ finish
    private fun complete() {
        val name = binding.etSeniorName.text.toString().trim()
        val age = binding.etSeniorAge.text.toString().toIntOrNull() ?: 70
        val city = binding.etSeniorCity.text.toString().trim().ifEmpty { "Delhi NCR" }
        val phone = binding.etEmergencyPhone.text.toString().trim().ifEmpty { "+91 98765 43210" }
        val coordCode = binding.etCoordCode.text.toString().trim().uppercase()
        val myPhone = binding.etMyPhone.text.toString().trim()

        binding.btnNext.isEnabled = false
        binding.tvNext.text = getString(R.string.onb_linking)

        lifecycleScope.launch {
            val result = AegisApiClient.onboardSenior(
                name = name, age = age, city = city, emergencyPhone = phone,
                coordinatorCode = coordCode,
                watchMac = WatchRepository.savedAddress(this@OnboardingActivity) ?: "",
                language = LocaleManager.current(this@OnboardingActivity),
                phone = myPhone, consent = binding.cbConsent.isChecked
            )
            result.onSuccess { json ->
                val senior = json.optJSONObject("senior")
                val seniorId = senior?.optString("senior_id").orEmpty()
                if (seniorId.isEmpty()) {
                    failed(getString(R.string.onb_bad_reply))
                    return@onSuccess
                }
                val deviceKey = json.optString("device_key", "")
                if (deviceKey.isEmpty()) {
                    failed(getString(R.string.onb_bad_reply))
                    return@onSuccess
                }
                AegisApiClient.deviceKey = deviceKey
                val coordName = senior?.optString("coordinator_name").orEmpty().ifEmpty { getString(R.string.care_manager_default) }
                prefs.edit().apply {
                    putString("device_key", deviceKey)
                    putString("senior_own_phone", myPhone)
                    putBoolean("is_onboarded", true)
                    putString("senior_id", seniorId)
                    putString("senior_name", name)
                    putInt("senior_age", age)
                    putString("senior_city", city)
                    putString("senior_phone", phone)
                    putString("coordinator_code", coordCode)
                    putString("coordinator_name", coordName)
                    apply()
                }
                Toast.makeText(this@OnboardingActivity, getString(R.string.onb_joined, coordName), Toast.LENGTH_LONG).show()
                startActivity(Intent(this@OnboardingActivity, MainActivity::class.java))
                finish()
                @Suppress("DEPRECATION")
                overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out)
            }.onFailure { err -> failed(err.message.orEmpty()) }
        }
    }

    private fun failed(message: String) {
        binding.btnNext.isEnabled = true
        binding.tvNext.text = getString(R.string.onb_btn_finish)
        if (message.contains("400")) {
            // Server rejected the care-manager code
            showStep(2)
            binding.tvCoordError.text = getString(R.string.err_code_invalid)
            binding.tvCoordError.visibility = View.VISIBLE
            return
        }
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.onb_fail_title))
            .setMessage(getString(R.string.onb_fail_msg, message))
            .setPositiveButton(getString(R.string.common_retry)) { _, _ -> complete() }
            .setNeutralButton(getString(R.string.menu_server)) { _, _ -> startActivity(Intent(this, SettingsActivity::class.java)) }
            .setNegativeButton(getString(R.string.common_cancel), null)
            .show()
    }
}
