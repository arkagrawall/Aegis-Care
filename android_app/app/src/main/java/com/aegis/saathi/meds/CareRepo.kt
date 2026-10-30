package com.aegis.saathi.meds

import android.content.Context
import android.util.Log
import com.aegis.saathi.api.AegisApiClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * Medicines and family contacts set by the care manager. Both are cached on the phone, so the
 * Medicines and Family tabs and the dose alarms keep working without a connection.
 */
object CareRepo {
    private const val TAG = "CareRepo"
    private const val PREFS = "aegis_senior_prefs"

    data class Dose(val medId: String, val name: String, val doseText: String, val withFood: Boolean,
                    val time: String, val status: String)
    data class Medicine(val id: String, val name: String, val doseText: String, val times: List<String>, val withFood: Boolean)
    data class Contact(val id: String, val name: String, val relation: String, val phone: String, val isEmergency: Boolean)
    data class MedsState(val medicines: List<Medicine> = emptyList(), val today: List<Dose> = emptyList(),
                         val week: List<Pair<String, String>> = emptyList(), val loaded: Boolean = false)
    data class ContactsState(val careName: String = "", val carePhone: String = "",
                             val contacts: List<Contact> = emptyList(), val loaded: Boolean = false)

    private val _meds = MutableStateFlow(MedsState())
    val meds: StateFlow<MedsState> = _meds
    private val _contacts = MutableStateFlow(ContactsState())
    val contacts: StateFlow<ContactsState> = _contacts

    /** Fires when something time-related happens outside the screen (an alarm rang), so Today re-decides at once. */
    private val _pulse = MutableSharedFlow<Unit>(extraBufferCapacity = 4)
    val pulse: SharedFlow<Unit> = _pulse
    fun nudge() { _pulse.tryEmit(Unit) }

    /** Phone clock corrected by the hub's clock, when the two differ by more than two minutes. */
    @Volatile private var clockOffsetMs = 0L
    fun now(): Long = System.currentTimeMillis() + clockOffsetMs

    private fun today(): String = java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.US).format(java.util.Date(now()))

    /** "Remind me in 15 minutes": remembered per dose for today, so the home card can say "Reminding you at 8:15". */
    fun snooze(c: Context, key: String, untilMinute: Int) {
        val p = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val day = today()
        val keep = p.getStringSet("dose_snoozes", emptySet())!!.filter { it.startsWith("$day|") && !it.startsWith("$day|$key|") }
        p.edit().putStringSet("dose_snoozes", (keep + "$day|$key|$untilMinute").toSet()).apply()
        nudge()
    }

    fun snoozes(c: Context): Map<String, Int> {
        val day = today()
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getStringSet("dose_snoozes", emptySet())!!
            .mapNotNull { e -> e.split("|").takeIf { it.size == 3 && it[0] == day }?.let { it[1] to (it[2].toIntOrNull() ?: 0) } }
            .toMap()
    }

    /** Shows an answer straight away, before (or without) the server confirming it. */
    fun markLocal(medId: String, time: String, status: String) {
        _meds.value = _meds.value.copy(today = _meds.value.today.map {
            if (it.medId == medId && it.time == time) it.copy(status = status) else it
        })
    }

    private fun seniorId(c: Context) = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("senior_id", "") ?: ""

    // ------------------------------------------------------------------ http
    private suspend fun get(path: String): JSONObject? = withContext(Dispatchers.IO) {
        try {
            val conn = URL(AegisApiClient.baseUrl + path).openConnection() as HttpURLConnection
            AegisApiClient.authorize(conn)
            conn.connectTimeout = 6000
            conn.readTimeout = 8000
            if (conn.responseCode != 200) { conn.disconnect(); return@withContext null }
            val body = conn.inputStream.bufferedReader().readText()
            conn.disconnect()
            JSONObject(body)
        } catch (e: Exception) {
            Log.w(TAG, "GET $path: ${e.message}")
            null
        }
    }

    private suspend fun post(path: String, body: JSONObject): Boolean = withContext(Dispatchers.IO) {
        try {
            val conn = URL(AegisApiClient.baseUrl + path).openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            AegisApiClient.authorize(conn)
            conn.connectTimeout = 6000
            conn.readTimeout = 8000
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json")
            conn.outputStream.use { it.write(body.toString().toByteArray()) }
            val ok = conn.responseCode == 200
            conn.disconnect()
            ok
        } catch (e: Exception) {
            Log.w(TAG, "POST $path: ${e.message}")
            false
        }
    }

    // ------------------------------------------------------------------ medicines
    /** Loads the cached copy (instant), then the server's; re-arms the dose alarms whenever the list changes. */
    suspend fun refreshMedicines(c: Context) {
        val prefs = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (!_meds.value.loaded) prefs.getString("meds_cache", null)?.let { runCatching { _meds.value = parseMeds(JSONObject(it)) } }
        val sid = seniorId(c)
        if (sid.isEmpty()) return
        // an answer given while offline is sent first
        prefs.getString("pending_dose", null)?.split("|")?.takeIf { it.size == 3 }?.let { (m, t, st) ->
            if (post("/api/senior/medicines/dose", JSONObject().put("senior_id", sid).put("med_id", m).put("time", t).put("status", st)))
                prefs.edit().remove("pending_dose").apply()
        }
        val j = get("/api/senior/medicines?senior_id=" + URLEncoder.encode(sid, "UTF-8")) ?: return
        prefs.edit().putString("meds_cache", j.toString()).apply()
        j.optDouble("server_time", 0.0).takeIf { it > 0 }?.let {
            val diff = (it * 1000).toLong() - System.currentTimeMillis()
            clockOffsetMs = if (kotlin.math.abs(diff) > 120_000) diff else 0L
        }
        _meds.value = parseMeds(j)
        DoseAlarms.armAll(c, _meds.value.medicines)
    }

    /** Taken / skipped / later. The answer shows at once; without a connection it is kept and sent on the next refresh. */
    suspend fun answerDose(c: Context, medId: String, time: String, status: String): Boolean {
        if (status != "later") markLocal(medId, time, status)
        val ok = post("/api/senior/medicines/dose", JSONObject()
            .put("senior_id", seniorId(c)).put("med_id", medId).put("time", time).put("status", status))
        if (!ok && status != "later") {
            c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString("pending_dose", "$medId|$time|$status").apply()
        }
        if (ok && status != "later") refreshMedicines(c)
        return ok
    }

    fun cachedMedicines(c: Context): List<Medicine> =
        c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("meds_cache", null)
            ?.let { runCatching { parseMeds(JSONObject(it)).medicines }.getOrNull() } ?: emptyList()

    private fun parseMeds(j: JSONObject): MedsState {
        val meds = j.optJSONArray("medicines").objects().map { m ->
            Medicine(m.optString("id"), m.optString("name"), m.optString("dose_text"),
                m.optJSONArray("times").strings(), m.optBoolean("with_food"))
        }
        val today = j.optJSONArray("today").objects().map { d ->
            Dose(d.optString("med_id"), d.optString("name"), d.optString("dose_text"), d.optBoolean("with_food"),
                d.optString("time"), d.optString("status"))
        }
        val week = j.optJSONArray("week").objects().map { it.optString("date") to it.optString("state") }
        return MedsState(meds, today, week, loaded = true)
    }

    // ------------------------------------------------------------------ contacts
    suspend fun refreshContacts(c: Context) {
        val prefs = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (!_contacts.value.loaded) prefs.getString("contacts_cache", null)?.let { runCatching { _contacts.value = parseContacts(JSONObject(it)) } }
        val sid = seniorId(c)
        if (sid.isEmpty()) return
        val j = get("/api/senior/contacts?senior_id=" + URLEncoder.encode(sid, "UTF-8")) ?: return
        prefs.edit().putString("contacts_cache", j.toString()).apply()
        _contacts.value = parseContacts(j)
    }

    private fun parseContacts(j: JSONObject): ContactsState {
        val cm = j.optJSONObject("care_manager") ?: JSONObject()
        val list = j.optJSONArray("contacts").objects().map {
            Contact(it.optString("id"), it.optString("name"), it.optString("relation"), it.optString("phone"), it.optBoolean("is_emergency"))
        }
        return ContactsState(cm.optString("name"), cm.optString("phone"), list, loaded = true)
    }

    private fun JSONArray?.objects(): List<JSONObject> =
        if (this == null) emptyList() else (0 until length()).mapNotNull { optJSONObject(it) }

    private fun JSONArray?.strings(): List<String> =
        if (this == null) emptyList() else (0 until length()).map { optString(it) }
}
