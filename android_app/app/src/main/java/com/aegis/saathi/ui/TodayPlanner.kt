package com.aegis.saathi.ui

/**
 * Decides the one thing the Today screen shows right now, from today's doses, the check-in and the clock.
 * Pure logic (no Android), so every case is unit-tested in TodayPlannerTest.
 *
 * Order: a dose that is due or late > "How are you today?" > the simple medicine question (no list set)
 *        > the next dose later today (or a snoozed one) > all done.
 */
object TodayPlanner {

    /** A dose is offered from 15 minutes before its time ... */
    const val EARLY_MIN = 15
    /** ... until 2 hours after it; later than that it counts as missed and is left to the care manager. */
    const val LATE_MIN = 120

    data class Dose(val key: String, val name: String, val doseText: String, val withFood: Boolean,
                    val minuteOfDay: Int, val status: String)

    data class Input(
        val nowMinute: Int,                    // minutes since midnight, on the corrected clock
        val doses: List<Dose>,                 // today's doses from the care manager's list (may be empty)
        val snoozedUntil: Map<String, Int>,    // dose key -> minute of day it was snoozed to
        val checkinDone: Boolean,
        val simpleMedsDone: Boolean,           // the one-tap "did you take your medicine" (only used without a list)
    )

    sealed class Now {
        data class DoseDue(val dose: Dose, val minutesLate: Int) : Now()          // negative = a little early
        object Checkin : Now()
        object SimpleMeds : Now()
        data class DoseLater(val dose: Dose, val atMinute: Int, val snoozed: Boolean) : Now()
        object AllDone : Now()
    }

    data class Plan(val now: Now, val comingUp: Dose?, val comingUpAt: Int, val taken: Int, val total: Int)

    private fun open(d: Dose) = d.status == "due" || d.status == "missed"

    fun plan(i: Input): Plan {
        val openDoses = i.doses.filter(::open).sortedBy { it.minuteOfDay }
        fun snoozeOf(d: Dose) = i.snoozedUntil[d.key]?.takeIf { it > i.nowMinute }
        val due = openDoses.filter { d ->
            snoozeOf(d) == null && i.nowMinute >= d.minuteOfDay - EARLY_MIN && i.nowMinute <= d.minuteOfDay + LATE_MIN
        }
        // later today: not yet in its window, or snoozed; sorted by when it will next need attention
        val later = openDoses.filter { d -> d !in due && (snoozeOf(d) != null || i.nowMinute < d.minuteOfDay - EARLY_MIN) }
            .map { d -> d to (snoozeOf(d) ?: d.minuteOfDay) }
            .sortedBy { it.second }

        val now: Now = when {
            due.isNotEmpty() -> due.first().let { Now.DoseDue(it, i.nowMinute - it.minuteOfDay) }
            !i.checkinDone -> Now.Checkin
            i.doses.isEmpty() && !i.simpleMedsDone -> Now.SimpleMeds
            later.isNotEmpty() -> later.first().let { (d, at) -> Now.DoseLater(d, at, snoozeOf(d) != null) }
            else -> Now.AllDone
        }
        // the line under the card: what comes after the thing shown now
        val shown = (now as? Now.DoseDue)?.dose ?: (now as? Now.DoseLater)?.dose
        val next = (due.drop(if (now is Now.DoseDue) 1 else 0).map { it to it.minuteOfDay } + later)
            .firstOrNull { it.first != shown }
        val counted = i.doses.filter { it.status != "none" }
        return Plan(now, next?.first, next?.second ?: -1, counted.count { it.status == "taken" }, counted.size)
    }

    fun minuteOf(hhmm: String): Int = runCatching {
        val (h, m) = hhmm.split(":").map { it.toInt() }
        h * 60 + m
    }.getOrDefault(0)
}
