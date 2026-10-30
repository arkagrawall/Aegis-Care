package com.aegis.saathi.ui

import android.content.res.ColorStateList
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.aegis.saathi.A11yPrefs
import com.aegis.saathi.LocaleManager
import com.aegis.saathi.R
import com.aegis.saathi.databinding.ItemDoseBinding
import com.aegis.saathi.databinding.PageMedsBinding
import com.aegis.saathi.meds.CareRepo
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Locale

/** The Medicines tab: today's doses in time order with a big Taken button each, the week, and the full list. */
class MedsTab(private val act: MainActivity, private val b: PageMedsBinding) {
    private val lang get() = com.aegis.saathi.LocaleManager.current(act)


    fun render(st: CareRepo.MedsState) {
        val inflater = LayoutInflater.from(act)
        b.dosesList.removeAllViews()
        b.medsEmpty.root.visibility = if (st.loaded && st.medicines.isEmpty()) View.VISIBLE else View.GONE
        b.medsEmpty.ivEmpty.setImageResource(R.drawable.ill_meds_empty)
        b.medsEmpty.tvEmptyTitle.setText(R.string.meds_empty_title)
        b.medsEmpty.tvEmptyBody.setText(R.string.meds_none_yet)
        b.tvMedsAllTitle.visibility = if (st.medicines.isEmpty()) View.GONE else View.VISIBLE
        b.medsAll.visibility = b.tvMedsAllTitle.visibility
        b.medsWeek.visibility = if (st.week.isEmpty() || st.medicines.isEmpty()) View.GONE else View.VISIBLE

        for (d in st.today) {
            val row = ItemDoseBinding.inflate(inflater, b.dosesList, false)
            row.tvDoseTime.text = clock(d.time, lang)
            row.tvDoseName.text = d.name
            row.tvDoseText.text = listOf(d.doseText, if (d.withFood) act.getString(R.string.meds_with_food) else "")
                .filter { it.isNotEmpty() }.joinToString(" · ")
            row.tvDoseText.visibility = if (row.tvDoseText.text.isEmpty()) View.GONE else View.VISIBLE
            val done = d.status in listOf("taken", "skipped", "missed", "none")
            row.doseActions.visibility = if (done) View.GONE else View.VISIBLE
            if (done) {
                val (icon, color, text) = when (d.status) {
                    "taken" -> Triple(R.drawable.ic_check, R.color.good, R.string.dose_state_taken)
                    "skipped" -> Triple(R.drawable.ic_warning, R.color.warn, R.string.dose_state_skipped)
                    else -> Triple(R.drawable.ic_clock, R.color.bad, R.string.dose_state_missed)
                }
                row.ivDoseState.visibility = View.VISIBLE
                row.ivDoseState.setImageResource(icon)
                row.ivDoseState.imageTintList = ColorStateList.valueOf(ContextCompat.getColor(act, color))
                row.tvDoseState.visibility = View.VISIBLE
                row.tvDoseState.text = act.getString(text)
                row.tvDoseState.setTextColor(ContextCompat.getColor(act, color))
            }
            row.btnDoseTaken.pressable()
            row.btnDoseSkip.pressable()
            row.btnDoseTaken.setOnClickListener { A11yPrefs.tap(it); answer(d, "taken") }
            row.btnDoseSkip.setOnClickListener { A11yPrefs.tap(it); answer(d, "skipped") }
            row.root.contentDescription = "${clock(d.time, lang)}, ${d.name}. ${row.tvDoseText.text}. ${row.tvDoseState.text}"
            b.dosesList.addView(row.root)
        }

        b.medsAll.removeAllViews()
        st.medicines.forEachIndexed { i, m ->
            val t = TextView(act, null, 0, R.style.T_Body).apply {
                text = act.getString(R.string.meds_line, m.name, m.doseText.ifEmpty { "–" }, m.times.joinToString(", ") { clock(it, lang) })
                setTextColor(ContextCompat.getColor(act, R.color.ink))
                setPadding(0, 14, 0, 14)
            }
            if (i > 0) b.medsAll.addView(View(act).apply {
                setBackgroundColor(ContextCompat.getColor(act, R.color.line))
                layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 2)
            })
            b.medsAll.addView(t)
        }

        renderWeek(st.week)
        A11yPrefs.applyContrast(b.root)
    }

    /** Seven days as dots: green all taken, amber some, red missed, grey nothing due. */
    private fun renderWeek(week: List<Pair<String, String>>) {
        b.medsWeek.removeAllViews()
        val inFmt = SimpleDateFormat("yyyy-MM-dd", Locale.US)
        val dayFmt = SimpleDateFormat("EEE", LocaleManager.locale(act))
        week.forEachIndexed { i, (date, state) ->
            val col = LinearLayout(act).apply {
                orientation = LinearLayout.VERTICAL
                gravity = Gravity.CENTER_HORIZONTAL
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            }
            val (color, word) = when (state) {
                "taken" -> R.color.good to R.string.week_taken
                "some" -> R.color.warn to R.string.week_some
                "missed" -> R.color.bad to R.string.week_missed
                "due" -> R.color.primary to R.string.week_due
                else -> R.color.line to R.string.week_none
            }
            val dot = View(act).apply {
                background = ContextCompat.getDrawable(act, R.drawable.bg_dot)?.mutate()
                backgroundTintList = ColorStateList.valueOf(ContextCompat.getColor(act, color))
                val px = (16 * act.resources.displayMetrics.density).toInt()
                layoutParams = LinearLayout.LayoutParams(px, px).apply { bottomMargin = px / 2 }
            }
            val label = TextView(act, null, 0, R.style.T_Caption).apply {
                text = if (i == week.lastIndex) act.getString(R.string.today_short)
                       else runCatching { dayFmt.format(inFmt.parse(date)!!) }.getOrDefault("")
                setTextColor(ContextCompat.getColor(act, R.color.ink_soft))
            }
            col.addView(dot); col.addView(label)
            col.contentDescription = "${label.text}: ${act.getString(word)}"
            col.importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_YES
            b.medsWeek.addView(col)
        }
    }

    private fun answer(d: CareRepo.Dose, status: String) {
        act.lifecycleScope.launch {
            val ok = CareRepo.answerDose(act, d.medId, d.time, status)
            Notice.show(act, act.getString(if (!ok) R.string.err_network else if (status == "taken") R.string.dose_thanks else R.string.dose_skipped_note),
                error = !ok)
        }
    }

    companion object {
        /** "20:00" -> "8:00 PM" in English, "रात 8:00" in Hindi (the way it is said, not AM/PM). */
        fun clock(hhmm: String, lang: String = com.aegis.saathi.LocaleManager.EN): String = runCatching {
            val d = SimpleDateFormat("HH:mm", Locale.US).parse(hhmm)!!
            if (lang != com.aegis.saathi.LocaleManager.HI) return@runCatching SimpleDateFormat("h:mm a", Locale.US).format(d)
            val h = hhmm.substringBefore(':').toInt()
            val part = when (h) { in 4..11 -> "सुबह"; in 12..15 -> "दोपहर"; in 16..19 -> "शाम"; else -> "रात" }
            part + " " + SimpleDateFormat("h:mm", Locale.US).format(d)
        }.getOrDefault(hhmm)
    }
}
