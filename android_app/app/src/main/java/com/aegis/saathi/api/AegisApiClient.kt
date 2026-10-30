package com.aegis.saathi.api

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

object AegisApiClient {
    private const val TAG = "AegisApiClient"

    // Default to 10.0.2.2 for Android Emulator, or override with local IP on Wi-Fi
    var baseUrl = "http://10.0.2.2:8000"

    /** Per-senior key issued by the server at registration; sent with every request. */
    @Volatile
    var deviceKey: String = ""

    fun authorize(conn: HttpURLConnection) {
        if (deviceKey.isNotEmpty()) conn.setRequestProperty("X-Device-Key", deviceKey)
    }

    suspend fun onboardSenior(
        name: String,
        age: Int,
        city: String,
        emergencyPhone: String,
        coordinatorCode: String,
        watchMac: String,
        language: String = "hi",
        phone: String = "",
        consent: Boolean = true
    ): Result<JSONObject> = withContext(Dispatchers.IO) {
        try {
            val url = URL("$baseUrl/api/senior/onboard")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            authorize(conn)
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            conn.connectTimeout = 5000
            conn.readTimeout = 5000

            val json = JSONObject().apply {
                put("name", name)
                put("age", age)
                put("city", city)
                put("emergency_contact", emergencyPhone)
                put("coordinator_code", coordinatorCode)
                put("watch_mac", watchMac)
                put("language", language)
                put("phone", phone)
                put("consent", consent)
                put("watch_model", "Da Fit / Moyoung Watch")
                put("initial_steps", 1650)
                put("initial_hr", 72)
                put("initial_spo2", 98.0)
            }

            val writer = OutputStreamWriter(conn.outputStream)
            writer.write(json.toString())
            writer.flush()
            writer.close()

            val responseCode = conn.responseCode
            if (responseCode == 200) {
                val reader = BufferedReader(InputStreamReader(conn.inputStream))
                val sb = StringBuilder()
                var line: String?
                while (reader.readLine().also { line = it } != null) {
                    sb.append(line)
                }
                reader.close()
                Result.success(JSONObject(sb.toString()))
            } else {
                Result.failure(Exception("HTTP $responseCode from server"))
            }
        } catch (e: Exception) {
            Log.e(TAG, "Onboard error", e)
            Result.failure(e)
        }
    }

    suspend fun syncVitals(
        seniorId: String,
        steps: Int,
        hr: Int,
        spo2: Double,
        battery: Int
    ): Boolean = withContext(Dispatchers.IO) {
        var attempts = 0
        var success = false
        while (attempts < 2 && !success) {
            attempts++
            try {
                val url = URL("$baseUrl/api/senior/vitals")
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                authorize(conn)
                conn.setRequestProperty("Content-Type", "application/json")
                conn.doOutput = true
                conn.connectTimeout = 5000
                conn.readTimeout = 5000

                val json = JSONObject().apply {
                    put("senior_id", seniorId)
                    put("steps", steps)
                    put("heart_rate", hr)
                    put("spo2", spo2)
                    put("battery", battery)
                }

                val writer = OutputStreamWriter(conn.outputStream)
                writer.write(json.toString())
                writer.flush()
                writer.close()
                success = (conn.responseCode == 200)
            } catch (e: Exception) {
                Log.e(TAG, "Vitals sync attempt $attempts failed", e)
            }
        }
        success
    }

    suspend fun submitCheckin(
        seniorId: String,
        checkinType: String,
        status: String,
        voiceText: String? = null
    ): Boolean = withContext(Dispatchers.IO) {
        var attempts = 0
        var success = false
        while (attempts < 2 && !success) {
            attempts++
            try {
                val url = URL("$baseUrl/api/senior/checkin")
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                authorize(conn)
                conn.setRequestProperty("Content-Type", "application/json")
                conn.doOutput = true
                conn.connectTimeout = 5000
                conn.readTimeout = 5000

                val json = JSONObject().apply {
                    put("senior_id", seniorId)
                    put("checkin_type", checkinType)
                    put("status", status)
                    if (voiceText != null) put("voice_text", voiceText)
                }

                val writer = OutputStreamWriter(conn.outputStream)
                writer.write(json.toString())
                writer.flush()
                writer.close()
                success = (conn.responseCode == 200)
            } catch (e: Exception) {
                Log.e(TAG, "Checkin submit attempt $attempts failed", e)
            }
        }
        success
    }

    suspend fun submitMedication(
        seniorId: String,
        action: String
    ): Boolean = withContext(Dispatchers.IO) {
        var attempts = 0
        var success = false
        while (attempts < 2 && !success) {
            attempts++
            try {
                val url = URL("$baseUrl/api/senior/medication")
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                authorize(conn)
                conn.setRequestProperty("Content-Type", "application/json")
                conn.doOutput = true
                conn.connectTimeout = 5000
                conn.readTimeout = 5000

                val json = JSONObject().apply {
                    put("senior_id", seniorId)
                    put("action", action)
                    put("med_name", "Morning Blood Pressure Tablet")
                }

                val writer = OutputStreamWriter(conn.outputStream)
                writer.write(json.toString())
                writer.flush()
                writer.close()
                success = (conn.responseCode == 200)
            } catch (e: Exception) {
                Log.e(TAG, "Medication submit attempt $attempts failed", e)
            }
        }
        success
    }

    suspend fun triggerSos(seniorId: String, lat: Double? = null, lon: Double? = null): Boolean = withContext(Dispatchers.IO) {
        try {
            val url = URL("$baseUrl/api/senior/sos")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            authorize(conn)
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            conn.connectTimeout = 5000
            conn.readTimeout = 5000

            val json = JSONObject().apply {
                put("senior_id", seniorId)
                if (lat != null && lon != null) { put("latitude", lat); put("longitude", lon) }
            }

            val writer = OutputStreamWriter(conn.outputStream)
            writer.write(json.toString())
            writer.flush()
            writer.close()
            conn.responseCode == 200
        } catch (e: Exception) {
            Log.e(TAG, "SOS trigger error", e)
            false
        }
    }
}
