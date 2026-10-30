package com.aegis.saathi.ble

import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

enum class WatchLink { NONE, CONNECTING, CONNECTED, RECONNECTING }

data class ScanDevice(
    val name: String,
    val address: String,
    val rssi: Int,
    val likelyWatch: Boolean
)

data class WatchState(
    val link: WatchLink = WatchLink.NONE,
    val scanning: Boolean = false,
    val deviceName: String = "",
    val address: String = "",
    /** True while the built-in demo generator (emulators / testing) is running. */
    val demo: Boolean = false,
    val heartRate: Int? = null,
    val spo2: Double? = null,
    val steps: Int? = null,
    val battery: Int? = null,
    val lastReadingMs: Long = 0L,
    val error: String = ""
)

/**
 * Single source of truth for the watch: the connection (owned by [WatchManager], kept alive by the
 * background service) writes here; the home screen, watch screen and the vitals uploader read.
 */
object WatchRepository {
    private const val PREFS = "aegis_senior_prefs"
    private const val KEY_ADDR = "watch_address"
    private const val KEY_NAME = "watch_name"

    private val _state = MutableStateFlow(WatchState())
    val state: StateFlow<WatchState> = _state.asStateFlow()

    private val _devices = MutableStateFlow<List<ScanDevice>>(emptyList())
    val devices: StateFlow<List<ScanDevice>> = _devices.asStateFlow()

    private val _raw = MutableStateFlow<List<String>>(emptyList())
    val raw: StateFlow<List<String>> = _raw.asStateFlow()

    fun update(change: (WatchState) -> WatchState) = _state.update(change)

    fun setDevices(list: List<ScanDevice>) {
        _devices.value = list
    }

    /** Keeps the last 80 lines of what the watch said, for diagnosing watches we cannot decode yet. */
    fun log(line: String) {
        val stamp = SimpleDateFormat("HH:mm:ss", Locale.US).format(Date())
        _raw.update { (it + "$stamp  $line").takeLast(80) }
    }

    fun clearLog() {
        _raw.value = emptyList()
    }

    fun savedAddress(context: Context): String? =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_ADDR, null)

    fun savedName(context: Context): String =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_NAME, "") ?: ""

    fun saveDevice(context: Context, name: String, address: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_ADDR, address).putString(KEY_NAME, name).apply()
    }

    fun forget(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .remove(KEY_ADDR).remove(KEY_NAME).apply()
    }
}
