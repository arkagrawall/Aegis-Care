package com.aegis.saathi.ui

import com.aegis.saathi.ui.TodayPlanner.Dose
import com.aegis.saathi.ui.TodayPlanner.Input
import com.aegis.saathi.ui.TodayPlanner.Now
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class TodayPlannerTest {

    private fun dose(key: String, hhmm: String, status: String = "due") =
        Dose(key, "Med $key", "1 tablet", false, TodayPlanner.minuteOf(hhmm), status)

    private fun at(hhmm: String, doses: List<Dose>, checkin: Boolean = true, simple: Boolean = false,
                   snoozed: Map<String, Int> = emptyMap()) =
        TodayPlanner.plan(Input(TodayPlanner.minuteOf(hhmm), doses, snoozed, checkin, simple))

    @Test fun doseInItsWindowComesFirst_evenBeforeTheCheckin() {
        val p = at("08:05", listOf(dose("a", "08:00"), dose("b", "20:00")), checkin = false)
        val now = p.now as Now.DoseDue
        assertEquals("a", now.dose.key)
        assertEquals(5, now.minutesLate)
        assertEquals("b", p.comingUp?.key)
    }

    @Test fun offeredFifteenMinutesEarly() {
        val p = at("07:46", listOf(dose("a", "08:00")))
        assertEquals(-14, (p.now as Now.DoseDue).minutesLate)
    }

    @Test fun beforeTheWindowItIsUpcoming() {
        val p = at("07:30", listOf(dose("a", "08:00")))
        val now = p.now as Now.DoseLater
        assertEquals(TodayPlanner.minuteOf("08:00"), now.atMinute)
        assertTrue(!now.snoozed)
    }

    @Test fun hubMarksMissedAfter30Min_butTheSeniorCanStillAnswerUntilTwoHours() {
        assertTrue(at("09:30", listOf(dose("a", "08:00", "missed"))).now is Now.DoseDue)
        assertTrue(at("10:01", listOf(dose("a", "08:00", "missed"))).now is Now.AllDone)
    }

    @Test fun noCheckinYet_andNothingDue_asksHowTheyAre() {
        assertTrue(at("11:00", listOf(dose("a", "20:00")), checkin = false).now is Now.Checkin)
    }

    @Test fun snoozedDoseWaitsUntilItsNewTime() {
        val snooze = mapOf("a" to TodayPlanner.minuteOf("08:20"))
        val waiting = at("08:10", listOf(dose("a", "08:00")), snoozed = snooze).now as Now.DoseLater
        assertTrue(waiting.snoozed)
        assertEquals(TodayPlanner.minuteOf("08:20"), waiting.atMinute)
        assertTrue(at("08:20", listOf(dose("a", "08:00")), snoozed = snooze).now is Now.DoseDue)
    }

    @Test fun answeredDosesAreSkippedAndCounted() {
        val p = at("14:00", listOf(dose("a", "08:00", "taken"), dose("b", "13:50"), dose("c", "20:00", "due")))
        assertEquals("b", (p.now as Now.DoseDue).dose.key)
        assertEquals(1, p.taken)
        assertEquals(3, p.total)
    }

    @Test fun everythingDone() {
        val p = at("21:00", listOf(dose("a", "08:00", "taken"), dose("b", "20:00", "skipped")))
        assertTrue(p.now is Now.AllDone)
        assertNull(p.comingUp)
    }

    @Test fun noMedicineListFallsBackToTheSimpleQuestion() {
        assertTrue(at("09:00", emptyList()).now is Now.SimpleMeds)
        assertTrue(at("09:00", emptyList(), simple = true).now is Now.AllDone)
    }

    @Test fun twoDosesDueTogether_theEarlierFirst_theOtherIsComingUp() {
        val p = at("08:10", listOf(dose("b", "08:05"), dose("a", "08:00")))
        assertEquals("a", (p.now as Now.DoseDue).dose.key)
        assertEquals("b", p.comingUp?.key)
    }

    @Test fun lateNightDoseJustBeforeMidnight() {
        assertTrue(at("23:50", listOf(dose("a", "23:55"))).now is Now.DoseDue)
        // a dose added after its time today ("none") never shows
        assertTrue(at("10:00", listOf(dose("a", "08:00", "none"))).now is Now.AllDone)
    }
}
