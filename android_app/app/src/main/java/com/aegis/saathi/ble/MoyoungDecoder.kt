package com.aegis.saathi.ble

/**
 * EXPERIMENTAL decoder for the vendor protocol of Moyoung / Da Fit bands (service 0xFEEA).
 *
 * Source of the format: the publicly documented reverse engineering in the Gadgetbridge project
 * (MoyoungConstants / MoyoungPacketIn), re-implemented here from that description. Not tested on a
 * physical band yet, so it is deliberately cautious:
 *   - a frame must start FE EA and its declared length must equal the bytes received, otherwise it is dropped,
 *   - every decoded value must be physiologically plausible, otherwise it is dropped (never clamped or guessed),
 *   - the app logs the raw packet next to anything decoded, so a wrong decode can be spotted and fixed.
 *
 * Frame:  FE EA | len_hi | len_lo | command | payload...
 *   len_hi = 0x10 for a 20-byte MTU (then high part is 0), else 0x20 + (length >> 8); length covers the whole frame.
 * Steps (characteristic FEE1, and command 0x33 answers): distance, steps, calories as three 24-bit little-endian numbers.
 * Heart rate answer: command 0x6D, payload[0] = bpm.  Blood oxygen answer: command 0x6B, payload[0] = percent.
 */
object MoyoungDecoder {
    const val CMD_SYNC_STEPS = 0x33
    const val CMD_HEART_RATE = 0x6D
    const val CMD_BLOOD_OXYGEN = 0x6B

    data class Frame(val command: Int, val payload: ByteArray)
    data class Steps(val steps: Int, val distanceM: Int, val calories: Int)

    /** Total length declared by the first fragment of a frame, or -1 when the header is not a Moyoung frame. */
    fun declaredLength(first: ByteArray): Int {
        if (first.size < 4) return -1
        if ((first[0].toInt() and 0xFF) != 0xFE || (first[1].toInt() and 0xFF) != 0xEA) return -1
        val hi = first[2].toInt() and 0xFF
        val lenHi = when {
            hi == 0x10 -> 0
            hi < 0x20 -> return -1
            else -> hi - 0x20
        }
        return (lenHi shl 8) or (first[3].toInt() and 0xFF)
    }

    /** Collects notification fragments into whole frames (a frame can arrive in several BLE packets). */
    class Reassembler {
        private var buf = ByteArray(0)
        private var want = -1

        fun feed(fragment: ByteArray): Frame? {
            if (want < 0) {
                val len = declaredLength(fragment)
                if (len < 5) return null
                want = len
                buf = ByteArray(0)
            }
            buf += fragment
            if (buf.size < want) return null
            val whole = buf.copyOf(want)
            want = -1
            buf = ByteArray(0)
            return Frame(whole[4].toInt() and 0xFF, whole.copyOfRange(5, whole.size))
        }

        fun reset() { want = -1; buf = ByteArray(0) }
    }

    private fun u24(b: ByteArray, at: Int): Int =
        (b[at].toInt() and 0xFF) or ((b[at + 1].toInt() and 0xFF) shl 8) or ((b[at + 2].toInt() and 0xFF) shl 16)

    /** Distance, steps, calories (3 x uint24). Null if the size is wrong or the numbers are implausible for one day. */
    fun parseSteps(payload: ByteArray): Steps? {
        if (payload.size < 9) return null
        val distance = u24(payload, 0)
        val steps = u24(payload, 3)
        val calories = u24(payload, 6)
        if (steps !in 0..80_000) return null
        if (distance > 120_000 || calories > 20_000) return null
        return Steps(steps, distance, calories)
    }

    fun parseHeartRate(payload: ByteArray): Int? {
        if (payload.isEmpty()) return null
        val v = payload[0].toInt() and 0xFF
        return if (v in 30..230) v else null   // 0 = "no reading yet" and is dropped
    }

    fun parseSpo2(payload: ByteArray): Int? {
        if (payload.isEmpty()) return null
        val v = payload[0].toInt() and 0xFF
        return if (v in 70..100) v else null
    }
}
