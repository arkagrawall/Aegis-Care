package com.aegis.saathi.call

import com.aegis.saathi.api.AegisApiClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/** REST calls for the live AI conversation (server: /api/calls/{id}/start|turn|audio|end). */
object CallApi {

    data class Turn(
        val heard: String,
        val reply: String,
        val audioUrl: String?,
        val isCompleted: Boolean,
        val emergency: Boolean,
        /** Spoken reply (MP3) delivered inline by the streaming channel; null = fetch it from [audioUrl]. */
        val audio: ByteArray? = null,
        /** "sarvam" = the hub runs this call on a Sarvam voice agent over /ws/calls/{id}/live; else "local". */
        val engine: String = "local"
    )

    /** Absolute URL for a server-relative path (or already-absolute URL). */
    /** Media players cannot send headers, so audio URLs carry the device key as a query parameter. */
    private fun withToken(url: String): String =
        if (AegisApiClient.deviceKey.isEmpty()) url
        else url + (if (url.contains("?")) "&" else "?") + "token=" + URLEncoder.encode(AegisApiClient.deviceKey, "UTF-8")

    fun absolute(pathOrUrl: String): String =
        withToken(if (pathOrUrl.startsWith("http")) pathOrUrl else AegisApiClient.baseUrl + pathOrUrl)

    /** Saathi's own voice: Swara for Hindi, Neerja for English. */
    fun ttsUrl(text: String, english: Boolean = false): String =
        withToken(AegisApiClient.baseUrl + "/api/calls/voice-audio?text=" +
            URLEncoder.encode(text.take(350), "UTF-8") + "&voice=" + if (english) "en-IN-NeerjaNeural" else "hi-IN-SwaraNeural")

    fun parseTurn(j: JSONObject) = parse(j)

    private fun parse(j: JSONObject) = Turn(
        heard = j.optString("heard", ""),
        reply = j.optString("reply", ""),
        audioUrl = j.optString("audio_url", "").ifEmpty { null },
        isCompleted = j.optBoolean("is_completed", false),
        emergency = j.optBoolean("emergency", false),
        engine = j.optString("engine", "local")
    )

    private suspend fun post(
        path: String,
        body: ByteArray,
        contentType: String,
        readTimeoutMs: Int
    ): Result<Turn> = withContext(Dispatchers.IO) {
        try {
            val conn = URL(AegisApiClient.baseUrl + path).openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            AegisApiClient.authorize(conn)
            conn.connectTimeout = 6000
            conn.readTimeout = readTimeoutMs
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", contentType)
            conn.setFixedLengthStreamingMode(body.size)
            conn.outputStream.use { it.write(body) }
            val code = conn.responseCode
            val text = (if (code in 200..299) conn.inputStream else conn.errorStream)
                ?.bufferedReader()?.use { it.readText() } ?: ""
            conn.disconnect()
            if (code in 200..299) Result.success(parse(JSONObject(text)))
            else Result.failure(Exception("HTTP $code $text"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /** [engine] "local" asks for the hub's own voice even when Sarvam is set up (used after a Sarvam failure). */
    suspend fun start(callId: String, engine: String = ""): Result<Turn> =
        post("/api/calls/$callId/start" + (if (engine.isNotEmpty()) "?engine=$engine" else ""),
            "{}".toByteArray(), "application/json", 10000)

    suspend fun sendText(callId: String, text: String, silence: Boolean = false): Result<Turn> {
        val body = JSONObject().put("text", text).put("silence", silence).toString().toByteArray()
        return post("/api/calls/$callId/turn", body, "application/json", 15000)
    }

    /** WAV bytes (16 kHz mono PCM16) -> server speech-to-text -> agent reply. */
    suspend fun sendAudio(callId: String, wav: ByteArray): Result<Turn> =
        post("/api/calls/$callId/audio", wav, "audio/wav", 30000)

    /** Home-screen "speak to tell us": WAV -> server speech-to-text -> check-in. Returns {heard,status,symptoms}. */
    suspend fun voiceNote(seniorId: String, wav: ByteArray): Result<JSONObject> = withContext(Dispatchers.IO) {
        try {
            val conn = URL(AegisApiClient.baseUrl + "/api/senior/voice-note?senior_id=" +
                URLEncoder.encode(seniorId, "UTF-8")).openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            AegisApiClient.authorize(conn)
            conn.connectTimeout = 6000
            conn.readTimeout = 30000
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "audio/wav")
            conn.setFixedLengthStreamingMode(wav.size)
            conn.outputStream.use { it.write(wav) }
            val code = conn.responseCode
            val text = (if (code in 200..299) conn.inputStream else conn.errorStream)
                ?.bufferedReader()?.use { it.readText() } ?: ""
            conn.disconnect()
            if (code in 200..299) Result.success(JSONObject(text)) else Result.failure(Exception("HTTP $code $text"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private suspend fun postJson(path: String, body: JSONObject): Boolean = withContext(Dispatchers.IO) {
        try {
            val bytes = body.toString().toByteArray()
            val conn = URL(AegisApiClient.baseUrl + path).openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            AegisApiClient.authorize(conn)
            conn.connectTimeout = 6000
            conn.readTimeout = 10000
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json")
            conn.setFixedLengthStreamingMode(bytes.size)
            conn.outputStream.use { it.write(bytes) }
            val ok = conn.responseCode in 200..299
            conn.disconnect()
            ok
        } catch (e: Exception) {
            false
        }
    }

    /** Family sharing: the senior decides. Returns the family code when switched on, "" when off, null on error. */
    suspend fun familyConsent(consent: Boolean): String? = withContext(Dispatchers.IO) {
        try {
            val bytes = JSONObject().put("consent", consent).toString().toByteArray()
            val conn = URL(AegisApiClient.baseUrl + "/api/senior/family-consent").openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            AegisApiClient.authorize(conn)
            conn.connectTimeout = 6000
            conn.readTimeout = 10000
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json")
            conn.setFixedLengthStreamingMode(bytes.size)
            conn.outputStream.use { it.write(bytes) }
            val code = conn.responseCode
            val text = (if (code in 200..299) conn.inputStream else conn.errorStream)?.bufferedReader()?.use { it.readText() } ?: ""
            conn.disconnect()
            if (code in 200..299) JSONObject(text).optString("family_code", "") else null
        } catch (e: Exception) {
            null
        }
    }

    /** Tells the server which language future AI calls to this senior should use ("hi" | "en"). */
    suspend fun setLanguage(seniorId: String, lang: String): Boolean =
        postJson("/api/senior/language", JSONObject().put("senior_id", seniorId).put("language", lang))

    /** Uploads only the readings that really exist (null = not measured, so not sent). [source]: watch | demo | manual. */
    suspend fun syncVitals(
        seniorId: String, steps: Int?, heartRate: Int?, spo2: Double?, battery: Int?,
        bpSys: Int? = null, bpDia: Int? = null, sugar: Double? = null, weight: Double? = null,
        source: String = "watch"
    ): Boolean {
        val body = JSONObject().put("senior_id", seniorId).put("source", source)
        steps?.let { body.put("steps", it) }
        heartRate?.let { body.put("heart_rate", it) }
        spo2?.let { body.put("spo2", it) }
        battery?.let { body.put("battery", it) }
        bpSys?.let { body.put("bp_sys", it) }
        bpDia?.let { body.put("bp_dia", it) }
        sugar?.let { body.put("sugar", it) }
        weight?.let { body.put("weight", it) }
        return postJson("/api/senior/vitals", body)
    }

    /** Outcome of the "Did you fall?" screen: false_alarm | ok_but_fell | need_help | no_response. */
    suspend fun reportFall(seniorId: String, outcome: String, impactG: Float): Boolean {
        val body = JSONObject().put("senior_id", seniorId).put("outcome", outcome).put("impact_g", impactG.toDouble())
        // an emergency outcome is worth a second try on a flaky network
        return postJson("/api/senior/fall", body) || (outcome in listOf("need_help", "no_response") && postJson("/api/senior/fall", body))
    }

    /** "I pressed SOS by mistake": allowed for a short time after sending. */
    suspend fun cancelSos(seniorId: String): Boolean =
        postJson("/api/senior/sos/cancel", JSONObject().put("senior_id", seniorId))

    /** Hang-up: the server saves whatever was said so far. */
    suspend fun end(callId: String) {
        post("/api/calls/$callId/end", "{}".toByteArray(), "application/json", 8000)
    }
}
