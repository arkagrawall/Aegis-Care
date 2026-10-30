package com.aegis.saathi

import android.app.Application
import android.content.Context
import com.aegis.saathi.api.ServerConfig

class AegisApp : Application() {

    override fun attachBaseContext(base: Context) {
        super.attachBaseContext(LocaleManager.wrap(base))
    }

    override fun onCreate() {
        super.onCreate()
        // Runs on every process start (activities AND the background call service)
        ServerConfig.load(this)
        com.aegis.saathi.api.AegisApiClient.deviceKey =
            getSharedPreferences("aegis_senior_prefs", MODE_PRIVATE).getString("device_key", "") ?: ""
    }
}
