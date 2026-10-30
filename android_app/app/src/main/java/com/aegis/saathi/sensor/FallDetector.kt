package com.aegis.saathi.sensor

import kotlin.math.sqrt

/**
 * Phone-accelerometer fall detector. Pure Kotlin (no Android types) so the exact same code is
 * exercised by tools/FallDetectorSim.kt on simulated motion.
 *
 * A fall candidate needs all three, in order:
 *   1. an IMPACT: a hard spike (>= 3.0 g), or a firm spike (>= 2.3 g) that follows a short free-fall /
 *      weightless dip (<= 0.7 g) in the last 1.2 s,
 *   2. then ~0.7 s of settling,
 *   3. then 2.5 s of STILLNESS: gravity only (mean 0.8 - 1.25 g) with almost no variation.
 * Walking, stairs, jogging, a stumble that is recovered, a bump in a vehicle or sitting down fail step 3
 * (they keep moving) or never reach step 1.
 *
 * It is a TRIGGER, not a verdict. A detected fall always opens a confirmation screen for the senior
 * ("Are you OK?"). Dropping the phone or tossing it on a sofa can also look like this; that is why
 * nothing is sent to the care team until the senior answers, or fails to answer, on the phone.
 * Everything runs on the device; only the outcome of the confirmation is ever uploaded.
 */
class FallDetector(private val onFall: (impactG: Float) -> Unit) {

    companion object {
        const val GRAVITY = 9.80665f
        const val FIRM_IMPACT_G = 2.3f
        const val HARD_IMPACT_G = 3.0f
        const val WEIGHTLESS_G = 0.7f
        const val WEIGHTLESS_TO_IMPACT_MS = 1200L
        const val SETTLE_MS = 700L
        const val STILL_WINDOW_MS = 2500L
        const val STILL_STD_G = 0.2f
        const val STILL_MEAN_MIN = 0.8f
        const val STILL_MEAN_MAX = 1.25f
        const val COOLDOWN_MS = 60_000L
        const val GIVE_UP_MS = 7_000L
    }

    private var lastWeightlessAt = Long.MIN_VALUE / 2
    private var impactAt = -1L
    private var impactG = 0f
    private var cooldownUntil = Long.MIN_VALUE
    private var n = 0
    private var sum = 0.0
    private var sumSq = 0.0

    /** Feed accelerometer samples in time order. [tMs] is any monotonic millisecond clock. */
    fun onSample(tMs: Long, ax: Float, ay: Float, az: Float) {
        if (tMs < cooldownUntil) return
        val g = sqrt(ax * ax + ay * ay + az * az) / GRAVITY

        if (impactAt < 0) {
            if (g <= WEIGHTLESS_G) lastWeightlessAt = tMs
            val hard = g >= HARD_IMPACT_G
            val firm = g >= FIRM_IMPACT_G && tMs - lastWeightlessAt <= WEIGHTLESS_TO_IMPACT_MS
            if (hard || firm) {
                impactAt = tMs
                impactG = g
                n = 0; sum = 0.0; sumSq = 0.0
            }
            return
        }

        val dt = tMs - impactAt
        if (dt < SETTLE_MS) return
        n++
        sum += g
        sumSq += g.toDouble() * g
        if (dt >= SETTLE_MS + STILL_WINDOW_MS) {
            val mean = sum / n
            val variance = (sumSq / n - mean * mean).coerceAtLeast(0.0)
            val std = sqrt(variance)
            val peak = impactG
            reset()
            if (mean in STILL_MEAN_MIN.toDouble()..STILL_MEAN_MAX.toDouble() && std < STILL_STD_G) {
                cooldownUntil = tMs + COOLDOWN_MS
                onFall(peak)
            }
        } else if (dt > GIVE_UP_MS) {
            reset()
        }
    }

    fun reset() {
        impactAt = -1L
        impactG = 0f
        n = 0; sum = 0.0; sumSq = 0.0
    }
}
