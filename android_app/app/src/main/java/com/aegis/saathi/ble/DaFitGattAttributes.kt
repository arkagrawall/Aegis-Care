package com.aegis.saathi.ble

import java.util.UUID

/**
 * Bluetooth LE identifiers used when talking to Da Fit / Moyoung bands and generic fitness bands.
 *
 * Standard Bluetooth SIG profiles (heart rate 0x180D, battery 0x180F) are decoded as the primary source.
 * The Moyoung vendor service 0xFEEA is decoded by MoyoungDecoder (experimental, plausibility-checked,
 * raw packets always logged); anything else on vendor services is logged only, never guessed.
 */
object DaFitGattAttributes {
    private fun sig(short: String): UUID = UUID.fromString("0000$short-0000-1000-8000-00805f9b34fb")

    // Vendor services seen on Moyoung / Da Fit bands (data is logged raw, not decoded)
    val MOYOUNG_SERVICE_UUID: UUID = sig("ffd0")
    val MOYOUNG_FEEA_SERVICE_UUID: UUID = sig("feea")
    val MOYOUNG_STEPS: UUID = sig("fee1")      // real-time steps (notify)
    val MOYOUNG_DATA_IN: UUID = sig("fee3")    // framed answers from the watch (notify)

    // Standard Bluetooth SIG services
    val HEART_RATE_SERVICE: UUID = sig("180d")
    val HEART_RATE_MEASUREMENT: UUID = sig("2a37")
    val BATTERY_SERVICE: UUID = sig("180f")
    val BATTERY_LEVEL: UUID = sig("2a19")

    // Generic access / attribute / device information: nothing useful to subscribe to
    val IGNORED_SERVICES: Set<UUID> = setOf(sig("1800"), sig("1801"), sig("180a"))

    // Client Characteristic Configuration Descriptor (enable notifications)
    val CLIENT_CHARACTERISTIC_CONFIG: UUID = sig("2902")

    /** Names that usually belong to fitness bands, used to float likely watches to the top of the scan list. */
    val LIKELY_WATCH_NAME = Regex(
        "(da\\s*fit|dafit|moyoung|crrepa|band|watch|fit|mi\\s*smart|amazfit|smart|gt\\d|id\\d{2,}|f\\d{2,}|p\\d{2,})",
        RegexOption.IGNORE_CASE
    )

    /** Standard Heart Rate Measurement (0x2A37): flags bit0 = 0 -> 8-bit value, 1 -> 16-bit value. */
    fun parseHeartRate(data: ByteArray): Int? {
        if (data.size < 2) return null
        val flags = data[0].toInt() and 0xFF
        val hr = if (flags and 0x01 == 0) {
            data[1].toInt() and 0xFF
        } else {
            if (data.size < 3) return null
            (data[1].toInt() and 0xFF) or ((data[2].toInt() and 0xFF) shl 8)
        }
        return if (hr in 30..230) hr else null
    }
}
