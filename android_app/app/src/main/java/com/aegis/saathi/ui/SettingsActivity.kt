package com.aegis.saathi.ui

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.aegis.saathi.LocaleManager
import com.aegis.saathi.R
import com.aegis.saathi.api.ServerConfig
import com.aegis.saathi.call.CallApi
import com.aegis.saathi.databinding.ActivitySettingsBinding
import com.aegis.saathi.service.CallListenerService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

class SettingsActivity : BaseActivity() {

    private lateinit var binding: ActivitySettingsBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySettingsBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.etServerUrl.setText(ServerConfig.saved(this))
        binding.tvCurrentUrl.text = getString(R.string.settings_current, ServerConfig.saved(this))

        binding.tvBack.setOnClickListener { finish() }
        binding.langToggle.onLanguageSelected = { lang ->
            LocaleManager.set(this, lang)
            val id = getSharedPreferences("aegis_senior_prefs", Context.MODE_PRIVATE).getString("senior_id", "") ?: ""
            if (id.isNotEmpty()) lifecycleScope.launch { CallApi.setLanguage(id, lang) }
            binding.settingsRoot.animate().alpha(0f).setDuration(140).withEndAction { recreate() }.start()
        }
        listOf(binding.btnTestConnection, binding.btnSaveUrl, binding.btnReregister).forEach { it.pressable() }

        binding.btnTestConnection.setOnClickListener {
            val url = normalizedInputOrWarn() ?: return@setOnClickListener
            testConnection(url)
        }

        binding.btnSaveUrl.setOnClickListener {
            val url = normalizedInputOrWarn() ?: return@setOnClickListener
            ServerConfig.save(this, url)
            binding.etServerUrl.setText(url)
            binding.tvCurrentUrl.text = getString(R.string.settings_current, url)
            reconnectCallService()
            setStatus(getString(R.string.settings_saved, url), R.color.good)
        }

        binding.btnResetUrl.setOnClickListener {
            ServerConfig.reset(this)
            binding.etServerUrl.setText(ServerConfig.DEFAULT_URL)
            binding.tvCurrentUrl.text = getString(R.string.settings_current, ServerConfig.DEFAULT_URL)
            reconnectCallService()
            setStatus(getString(R.string.settings_saved, ServerConfig.DEFAULT_URL), R.color.good)
        }

        binding.btnReregister.setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle(getString(R.string.settings_rereg_title))
                .setMessage(getString(R.string.settings_rereg_confirm))
                .setPositiveButton(getString(R.string.settings_rereg_yes)) { _, _ -> reregister() }
                .setNegativeButton(getString(R.string.common_cancel), null)
                .show()
        }
    }

    private fun normalizedInputOrWarn(): String? {
        val url = ServerConfig.normalize(binding.etServerUrl.text?.toString().orEmpty())
        if (url == null) setStatus(getString(R.string.settings_invalid), R.color.bad)
        return url
    }

    private fun testConnection(url: String) {
        setStatus(getString(R.string.settings_testing, url), R.color.ink_soft)
        binding.btnTestConnection.isEnabled = false
        lifecycleScope.launch {
            val code = withContext(Dispatchers.IO) {
                try {
                    val conn = URL("$url/api/health").openConnection() as HttpURLConnection
                    conn.connectTimeout = 6000
                    conn.readTimeout = 6000
                    val c = conn.responseCode
                    conn.disconnect()
                    Result.success(c)
                } catch (e: Exception) {
                    Result.failure(e)
                }
            }
            binding.btnTestConnection.isEnabled = true
            code.onSuccess { c ->
                if (c == 200) setStatus(getString(R.string.settings_ok, url), R.color.good)
                else setStatus(getString(R.string.settings_http, c), R.color.bad)
            }.onFailure { e ->
                setStatus(getString(R.string.settings_cant, e.message ?: e.javaClass.simpleName), R.color.bad)
            }
        }
    }

    /** Tell the running service to use the new address (it keeps running; only the socket is rebuilt). */
    private fun reconnectCallService() {
        val prefs = getSharedPreferences("aegis_senior_prefs", Context.MODE_PRIVATE)
        if (!prefs.getString("senior_id", null).isNullOrEmpty()) CallListenerService.reconnect(this)
    }

    private fun reregister() {
        stopService(Intent(this, CallListenerService::class.java))
        com.aegis.saathi.api.AegisApiClient.deviceKey = ""
        getSharedPreferences("aegis_senior_prefs", Context.MODE_PRIVATE).edit().apply {
            remove("is_onboarded")
            remove("senior_id")
            remove("senior_name")
            remove("senior_age")
            remove("senior_city")
            remove("senior_phone")
            remove("senior_own_phone")
            remove("device_key")
            remove("coordinator_code")
            remove("coordinator_name")
            remove("checkin_date")
            remove("meds_date")
            apply()
        }
        startActivity(Intent(this, OnboardingActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        })
        Notice.show(this, getString(R.string.settings_cleared))
    }

    private fun setStatus(message: String, colorRes: Int) {
        binding.tvStatus.text = message
        binding.tvStatus.setTextColor(ContextCompat.getColor(this, colorRes))
    }
}
