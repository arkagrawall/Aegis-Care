package com.aegis.saathi.api

import android.content.Context
import java.net.URL

/**
 * Persists the Coordinator Hub address so it can be changed from the in-app Settings
 * screen (e.g. a new tunnel URL) without rebuilding the APK.
 */
object ServerConfig {
    const val DEFAULT_URL = "http://10.0.2.2:8000" // Android Studio emulator -> host machine
    private const val PREFS = "aegis_senior_prefs"
    private const val KEY_URL = "server_url"

    fun saved(context: Context): String =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_URL, null)
            ?: DEFAULT_URL

    /** Loads the saved URL into AegisApiClient. Called from AegisApp.onCreate. */
    fun load(context: Context) {
        AegisApiClient.baseUrl = saved(context)
    }

    fun save(context: Context, url: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(KEY_URL, url).apply()
        AegisApiClient.baseUrl = url
    }

    fun reset(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().remove(KEY_URL).apply()
        AegisApiClient.baseUrl = DEFAULT_URL
    }

    /**
     * Turns what the user typed/pasted into "scheme://host[:port]" or returns null if unusable.
     * - "abc.trycloudflare.com"        -> https://abc.trycloudflare.com
     * - "192.168.1.5:8000"             -> http://192.168.1.5:8000 (local addresses stay http)
     * - "wss://abc.ngrok-free.app/x/"  -> https://abc.ngrok-free.app (ws -> http, path dropped)
     */
    fun normalize(input: String): String? {
        var s = input.trim()
        if (s.isEmpty()) return null
        s = when {
            s.startsWith("wss://", true) -> "https://" + s.substring(6)
            s.startsWith("ws://", true) -> "http://" + s.substring(5)
            else -> s
        }
        if (!s.contains("://")) {
            val host = s.substringBefore('/').substringBefore(':')
            val local = host == "localhost" || host.matches(Regex("""\d{1,3}(\.\d{1,3}){3}"""))
            s = (if (local) "http://" else "https://") + s
        }
        return try {
            val u = URL(s)
            if (u.host.isNullOrEmpty() || (u.protocol != "http" && u.protocol != "https")) return null
            val port = if (u.port != -1) ":${u.port}" else ""
            "${u.protocol}://${u.host}$port"
        } catch (e: Exception) {
            null
        }
    }
}
