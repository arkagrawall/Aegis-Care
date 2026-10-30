package com.aegis.saathi.ui

import android.Manifest
import android.animation.Animator
import android.animation.AnimatorListenerAdapter
import android.animation.ObjectAnimator
import android.animation.ValueAnimator
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.os.Build
import android.os.Bundle
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
import android.view.View
import android.widget.ImageView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.aegis.saathi.A11yPrefs
import com.aegis.saathi.LocaleManager
import com.aegis.saathi.meds.CareRepo
import com.aegis.saathi.R
import com.aegis.saathi.api.AegisApiClient
import com.aegis.saathi.ble.WatchLink
import com.aegis.saathi.ble.WatchManager
import com.aegis.saathi.ble.WatchRepository
import com.aegis.saathi.ble.WatchState
import com.aegis.saathi.call.AudioRecorderVad
import com.aegis.saathi.call.CallApi
import com.aegis.saathi.databinding.ActivityMainBinding
import com.aegis.saathi.service.CallListenerService
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlin.math.abs
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale

/**
 * Senior home screen with four tabs at the bottom (Today, Medicines, Family, Me) and the
 * hold-to-call SOS button on top of every tab. Today is one column with big targets:
 *   1. How are you today?  2. Medicine  3. Speak to tell us  4. Watch status  5. Readings
 */
class MainActivity : BaseActivity() {

    companion object {
        const val TAB_TODAY = 0
        const val TAB_MEDS = 1
        const val TAB_FAMILY = 2
        const val TAB_ME = 3
    }

    // the bottom bar and the pages handle the status / gesture bars themselves
    override val padRootForSystemBars = false

    private lateinit var medsTab: MedsTab
    private lateinit var familyTab: FamilyTab
    private lateinit var meTab: MeTab
    private var currentTab = TAB_TODAY

    private lateinit var binding: ActivityMainBinding
    private lateinit var prefs: SharedPreferences

    private var seniorId = ""
    private var seniorName = ""
    private var coordName = ""

    private var checkinLocked = false
    private var medsLocked = false

    private val recorder = AudioRecorderVad()
    private val notePlayer by lazy { com.aegis.saathi.call.SpeechPlayer(this, callChannel = false) }
    private var voiceJob: Job? = null
    private var voiceBreathing: ObjectAnimator? = null

    private var sosCountJob: Job? = null
    private var sosState = 0   // 0 idle, 1 counting down, 2 sent

    private val notificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    private val micPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) startVoiceNote() else toast(R.string.mic_permission)
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        prefs = getSharedPreferences("aegis_senior_prefs", Context.MODE_PRIVATE)
        seniorId = prefs.getString("senior_id", "") ?: ""
        seniorName = prefs.getString("senior_name", "") ?: ""
        coordName = prefs.getString("coordinator_name", "") ?: ""

        setupInsets()
        setupUI()
        setupListeners()
        restoreDailyState()
        observeWatch()
        setupTabs(savedInstanceState?.getInt("tab") ?: prefs.getInt("reopen_tab", TAB_TODAY).also {
            prefs.edit().remove("reopen_tab").apply()
        })
        observeCare()
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                while (isActive) { setupUI(); renderNow(); delay(30_000) }
            }
        }
        lifecycleScope.launch { CareRepo.pulse.collect { renderNow() } }

        if (savedInstanceState == null) {
            playEntranceAnimation()
        } else {
            // rebuilt after a language change: simple fade-in instead of the full entrance
            binding.root.alpha = 0f
            binding.root.animate().alpha(1f).setDuration(220).start()
        }

        // Android 13+: without this the incoming-call notification is not shown
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }

        // Background call listener + watch connection (also nudged again whenever the screen is shown)
        CallListenerService.start(this)
        WatchManager.get(this).start()
    }

    /** The phone's clock, date or time zone changed (or midnight passed): re-decide and fetch today's doses. */
    private val clockReceiver = object : android.content.BroadcastReceiver() {
        override fun onReceive(c: Context, i: Intent) {
            renderNow()
            lifecycleScope.launch { CareRepo.refreshMedicines(this@MainActivity) }
        }
    }

    override fun onStop() {
        runCatching { unregisterReceiver(clockReceiver) }
        super.onStop()
    }

    override fun onStart() {
        super.onStart()
        ContextCompat.registerReceiver(this, clockReceiver, android.content.IntentFilter().apply {
            addAction(Intent.ACTION_DATE_CHANGED); addAction(Intent.ACTION_TIME_CHANGED); addAction(Intent.ACTION_TIMEZONE_CHANGED)
        }, ContextCompat.RECEIVER_NOT_EXPORTED)
        CallListenerService.start(this)
        if (::meTab.isInitialized) meTab.renderCallReadiness()   // back from the settings page it opened
        lifecycleScope.launch { CareRepo.refreshMedicines(this@MainActivity) }
        lifecycleScope.launch { CareRepo.refreshContacts(this@MainActivity) }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putInt("tab", currentTab)
    }

    // ------------------------------------------------------------------------------ bars and tabs
    /** Pages start below the status bar; the bottom bar sits above the gesture bar; the SOS overlay avoids both. */
    private fun setupInsets() {
        padForSystemBars(binding.pageHost, top = true, bottom = false)
        padForSystemBars(binding.bottomNav, top = false, bottom = true)
        padForSystemBars(binding.sosOverlay, top = true, bottom = true)
    }

    private fun setupTabs(start: Int) {
        medsTab = MedsTab(this, binding.pageMeds)
        familyTab = FamilyTab(this, binding.pageFamily)
        meTab = MeTab(this, binding.pageMe)
        binding.bottomNav.setOnItemSelectedListener { item ->
            A11yPrefs.tap(binding.bottomNav)
            showTab(when (item.itemId) {
                R.id.tabMeds -> TAB_MEDS
                R.id.tabFamily -> TAB_FAMILY
                R.id.tabMe -> TAB_ME
                else -> TAB_TODAY
            })
            true
        }
        binding.bottomNav.setOnItemReselectedListener { pageOf(currentTab).smoothScrollTo(0, 0) }
        binding.bottomNav.selectedItemId = listOf(R.id.tabToday, R.id.tabMeds, R.id.tabFamily, R.id.tabMe)[start]
        showTab(start)
    }

    private fun pageOf(tab: Int): android.widget.ScrollView = when (tab) {
        TAB_MEDS -> binding.pageMeds.root
        TAB_FAMILY -> binding.pageFamily.root
        TAB_ME -> binding.pageMe.root
        else -> binding.scrollMain
    }

    fun showTab(tab: Int) {
        if (tab == currentTab && pageOf(tab).visibility == View.VISIBLE) return
        val old = pageOf(currentTab)
        val new = pageOf(tab)
        currentTab = tab
        if (old !== new) old.visibility = View.GONE
        new.alpha = 0f
        new.visibility = View.VISIBLE
        new.animate().alpha(1f).setDuration(160).start()
    }

    /** Text size and contrast apply to every view, so the screen is rebuilt on the same tab. */
    fun rebuild(tab: Int) {
        prefs.edit().putInt("reopen_tab", tab).apply()
        binding.root.animate().alpha(0f).setDuration(140).withEndAction { recreate() }.start()
    }

    fun refreshReadAloud() {
        binding.btnMore.visibility = if (A11yPrefs.readAloud(this)) View.VISIBLE else View.GONE
    }

    private fun observeCare() {
        lifecycleScope.launch { CareRepo.meds.collect { medsTab.render(it); renderNow() } }
        lifecycleScope.launch { CareRepo.contacts.collect { familyTab.render(it, prefs.getBoolean("family_on", false)) } }
    }

    // ------------------------------------------------------------------------------ setup
    private fun setupUI() {
        val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        val hello = getString(
            when {
                hour < 12 -> R.string.greet_morning
                hour < 17 -> R.string.greet_afternoon
                else -> R.string.greet_evening
            }
        )
        binding.tvSeniorGreeting.text = getString(R.string.home_greeting, hello, seniorName)
        binding.tvSubGreeting.text = SimpleDateFormat("EEEE, d MMMM", LocaleManager.locale(this)).format(Date())
        binding.tvCoordinatorAssigned.text = getString(R.string.care_manager, coordName)
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun setupListeners() {
        // Language switch + menu
        binding.langToggle.onLanguageSelected = { lang -> changeLanguage(lang) }
        binding.btnMore.setImageResource(R.drawable.ic_speaker)
        binding.btnMore.contentDescription = getString(R.string.read_aloud)
        binding.btnMore.setOnClickListener { A11yPrefs.tap(it); readTodayAloud() }
        refreshReadAloud()

        // 1. How are you today?
        listOf(binding.optFine, binding.optWeak, binding.optBad).forEach { it.pressable(0.94f) }
        binding.optFine.setOnClickListener { onCheckinTapped("good", it) }
        binding.optWeak.setOnClickListener { onCheckinTapped("weak", it) }
        binding.optBad.setOnClickListener { onCheckinTapped("bad", it) }

        // 2. Medicine
        listOf(binding.btnMedTaken, binding.btnMedLater, binding.btnMedSkipped).forEach { it.pressable() }
        binding.btnMedTaken.setOnClickListener { onMedTapped("taken", it) }
        binding.btnMedLater.setOnClickListener { onMedTapped("later", it) }
        binding.btnMedSkipped.setOnClickListener { onMedTapped("skipped", it) }

        binding.tvComingUp.setOnClickListener { showTab(TAB_MEDS); binding.bottomNav.selectedItemId = R.id.tabMeds }
        binding.chipDoses.setOnClickListener { binding.bottomNav.selectedItemId = R.id.tabMeds }
        binding.chipSteps.setOnClickListener { openWatch() }
        listOf(binding.chipDoses, binding.chipSteps).forEach { it.pressable(0.96f) }

        // 3. Speak to tell us
        binding.btnVoice.pressable()
        binding.btnVoice.setOnClickListener { onVoiceTapped() }

        // 4. Watch
        binding.cardWatch.pressable(0.98f)
        binding.cardWatch.setOnClickListener { openWatch() }
        binding.btnWatch.setOnClickListener { openWatch() }

        // 5. Readings (BP / sugar / weight)
        binding.btnAddReadings.pressable()
        binding.btnAddReadings.setOnClickListener { showReadingsDialog() }
        showLastReadings()

        // Emergency: press and hold, then a cancellable countdown
        setupSos()
    }

    private fun openWatch() {
        startActivity(Intent(this, WatchActivity::class.java))
    }

    fun changeLanguage(lang: String) {
        if (lang == LocaleManager.current(this)) return
        LocaleManager.set(this, lang)
        prefs.edit().putInt("reopen_tab", currentTab).apply()
        val id = seniorId
        if (id.isNotEmpty()) lifecycleScope.launch { CallApi.setLanguage(id, lang) }
        // fade out, rebuild in the new language, fade in
        binding.root.animate().alpha(0f).setDuration(140).withEndAction { recreate() }.start()
    }

    private fun playEntranceAnimation() {
        listOf(binding.headerRow, binding.cardCheckin, binding.cardMeds, binding.btnVoice, binding.todayStrip)
            .forEachIndexed { i, v -> v.slideUpIn(i * 70L) }
        binding.sosDock.slideUpIn(380)
    }

    // ------------------------------------------------------------------------------ watch
    private fun observeWatch() {
        lifecycleScope.launch { WatchRepository.state.collect { renderWatch(it); if (::meTab.isInitialized) meTab.renderWatch(it) } }
    }

    private fun renderWatch(st: WatchState) {
        val dash = "–"
        when (st.link) {
            WatchLink.CONNECTED -> {
                binding.tvWatchStatus.text = if (st.demo) getString(R.string.watch_demo_on)
                else getString(R.string.watch_card_connected, st.deviceName)
                binding.btnWatch.text = getString(R.string.watch_card_manage)
            }
            WatchLink.CONNECTING, WatchLink.RECONNECTING -> {
                binding.tvWatchStatus.text = getString(R.string.watch_card_reconnecting)
                binding.btnWatch.text = getString(R.string.watch_card_manage)
            }
            WatchLink.NONE -> {
                binding.tvWatchStatus.text = getString(R.string.watch_card_none)
                binding.btnWatch.text = getString(R.string.watch_card_cta)
            }
        }
        val live = st.link == WatchLink.CONNECTED
        watchLinked = live
        lastSteps = st.steps
        if (::binding.isInitialized && shownDay.isNotEmpty()) plan?.let { renderStrip(it, prefs.getString("checkin_date", "") == today()) }
        binding.tvLiveSteps.text = if (live) st.steps?.let { String.format(LocaleManager.locale(this), "%,d", it) } ?: dash else dash
        binding.tvLiveHr.text = if (live) st.heartRate?.toString() ?: dash else dash
        binding.tvLiveSpo2.text = if (live) st.spo2?.let { "${it.toInt()}%" } ?: dash else dash
        binding.tvWatchBattery.text = if (live) st.battery?.let { "$it%" } ?: dash else dash
    }

    // ------------------------------------------------------------------------ daily state
    private fun today(): String = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())

    private fun restoreDailyState() {
        if (prefs.getString("checkin_date", "") == today()) {
            showCheckinDone(prefs.getString("checkin_status", "good") ?: "good", animate = false)
        }

    }

    // ------------------------------------------------------------------------ 1. check-in
    private fun onCheckinTapped(status: String, tapped: View) {
        if (checkinLocked) return
        checkinLocked = true
        tapped.tick()

        // Highlight the chosen face, dim the others
        listOf(binding.optFine, binding.optWeak, binding.optBad).forEach { v ->
            if (v === tapped) v.animate().scaleX(1.06f).scaleY(1.06f).setDuration(180).start()
            else v.animate().alpha(0.35f).setDuration(180).start()
        }

        val note = getString(
            when (status) {
                "good" -> R.string.checkin_note_good
                "weak" -> R.string.checkin_note_weak
                else -> R.string.checkin_note_bad
            }
        )
        lifecycleScope.launch {
            val ok = AegisApiClient.submitCheckin(seniorId, "one_tap", status, note)
            if (!ok) {
                toast(R.string.err_network)
                listOf(binding.optFine, binding.optWeak, binding.optBad).forEach {
                    it.animate().scaleX(1f).scaleY(1f).alpha(1f).setDuration(200).start()
                }
                checkinLocked = false
                return@launch
            }
            prefs.edit().putString("checkin_date", today()).putString("checkin_status", status).apply()
            delay(450)
            showCheckinDone(status, animate = true)
        }
    }

    private fun showCheckinDone(status: String, animate: Boolean) {
        checkinLocked = true
        val (icon, color, text) = when (status) {
            "good" -> Triple(R.drawable.ic_face_happy, R.color.good, R.string.checkin_done_good)
            "weak" -> Triple(R.drawable.ic_face_neutral, R.color.warn, R.string.checkin_done_weak)
            else -> Triple(R.drawable.ic_face_sad, R.color.bad, R.string.checkin_done_bad)
        }
        binding.tvCheckinTitle.text = getString(R.string.checkin_done_title)
        binding.ivCheckinDone.setImageResource(icon)
        binding.ivCheckinDone.imageTintList = ColorStateList.valueOf(ContextCompat.getColor(this, color))
        binding.tvCheckinDoneText.text = getString(text)
        binding.tvCheckinDoneText.setTextColor(ContextCompat.getColor(this, color))
        if (animate) {
            // say thank you for a moment, then move on to what comes next
            checkinThanksUntil = System.currentTimeMillis() + 2500
            binding.checkinOptions.fadeOutGone(220) { binding.checkinDone.popIn() }
            binding.root.postDelayed({ renderNow() }, 2600)
        } else {
            binding.checkinOptions.visibility = View.GONE
            binding.checkinDone.visibility = View.VISIBLE
        }
    }

    // ------------------------------------------------------------------------ 2. right now
    /*
     * Today shows one thing at a time, chosen by TodayPlanner: a dose that is due, the check-in, the next dose
     * later today, or "all done". It re-decides every 30 seconds, when the medicine list changes, when an alarm
     * rings, after every answer and at midnight, so the senior never has to open the Medicines tab.
     */
    private var plan: TodayPlanner.Plan? = null
    private var shownDay = ""
    /** After a check-in the card stays a moment so the senior sees it was received. */
    private var checkinThanksUntil = 0L
    private var lastSteps: Int? = null
    private var watchLinked = false

    private fun nowMinute(): Int {
        val c = Calendar.getInstance().apply { timeInMillis = CareRepo.now() }
        return c.get(Calendar.HOUR_OF_DAY) * 60 + c.get(Calendar.MINUTE)
    }

    private fun clockText(minute: Int) = MedsTab.clock(String.format(Locale.US, "%02d:%02d", minute / 60 % 24, minute % 60))

    private fun duration(min: Int): String {
        val m = abs(min)
        return when {
            m < 60 -> getString(R.string.dur_min, maxOf(m, 1))
            m % 60 == 0 -> getString(R.string.dur_h, m / 60)
            else -> getString(R.string.dur_h_min, m / 60, m % 60)
        }
    }

    /** A new day (or the app opened on one): the check-in opens again and today's doses are fetched. */
    private fun newDay() {
        if (shownDay.isNotEmpty()) {
            checkinLocked = false
            binding.tvCheckinTitle.setText(R.string.checkin_title)
            binding.checkinDone.visibility = View.GONE
            binding.checkinOptions.visibility = View.VISIBLE
            listOf(binding.optFine, binding.optWeak, binding.optBad).forEach { it.alpha = 1f; it.scaleX = 1f; it.scaleY = 1f }
            lifecycleScope.launch { CareRepo.refreshMedicines(this@MainActivity) }
        }
        shownDay = today()
    }

    private fun renderNow() {
        if (shownDay != today()) newDay()
        val st = CareRepo.meds.value
        val doses = if (st.medicines.isEmpty()) emptyList() else st.today.map {
            TodayPlanner.Dose(it.medId + "@" + it.time, it.name, it.doseText, it.withFood, TodayPlanner.minuteOf(it.time), it.status)
        }
        val checkinDone = prefs.getString("checkin_date", "") == today()
        val p = TodayPlanner.plan(TodayPlanner.Input(nowMinute(), doses, CareRepo.snoozes(this), checkinDone,
            prefs.getString("meds_date", "") == today()))
        plan = p
        val now = p.now
        val thanks = System.currentTimeMillis() < checkinThanksUntil
        val showCheckin = now is TodayPlanner.Now.Checkin || thanks
        val showMeds = !thanks && (now is TodayPlanner.Now.DoseDue || now is TodayPlanner.Now.DoseLater || now is TodayPlanner.Now.SimpleMeds)
        val showDone = !thanks && now is TodayPlanner.Now.AllDone
        binding.cardCheckin.visibility = if (showCheckin) View.VISIBLE else View.GONE
        binding.cardMeds.visibility = if (showMeds) View.VISIBLE else View.GONE
        if (showMeds) renderMedsCard(now)
        if (showDone && binding.allDone.root.visibility != View.VISIBLE) {
            binding.allDone.ivEmpty.setImageResource(R.drawable.ill_all_done)
            binding.allDone.tvEmptyTitle.setText(R.string.all_done_title)
            binding.allDone.tvEmptyBody.setText(R.string.all_done_body)
        }
        binding.allDone.root.visibility = if (showDone) View.VISIBLE else View.GONE

        val next = p.comingUp
        binding.tvComingUp.visibility = if (next != null && !showDone) View.VISIBLE else View.GONE
        if (next != null) binding.tvComingUp.text = getString(R.string.coming_up, clockText(p.comingUpAt), next.name)
        renderStrip(p, checkinDone)
    }

    private fun renderMedsCard(now: TodayPlanner.Now) {
        fun takenButton(primary: Boolean, label: Int) {
            binding.btnMedTaken.setBackgroundResource(if (primary) R.drawable.bg_btn_good else R.drawable.bg_btn_outline)
            binding.tvMedTakenLabel.setText(label)
            val c = ContextCompat.getColor(this, if (primary) android.R.color.white else R.color.primary_dark)
            binding.tvMedTakenLabel.setTextColor(c)
            (binding.btnMedTaken.getChildAt(0) as? ImageView)?.imageTintList = ColorStateList.valueOf(c)
        }
        fun detail(d: TodayPlanner.Dose) = listOf(d.doseText, if (d.withFood) getString(R.string.meds_with_food) else "")
            .filter { it.isNotBlank() }.joinToString(" · ")
        medsLocked = false
        binding.medsDone.visibility = View.GONE
        binding.medsActions.visibility = View.VISIBLE
        val whenText: String?
        when (now) {
            is TodayPlanner.Now.DoseDue -> {
                binding.tvMedsTitle.text = getString(R.string.now_dose_title, now.dose.name)
                binding.tvMedsSub.text = detail(now.dose)
                whenText = if (now.minutesLate > 0) getString(R.string.now_late, duration(now.minutesLate))
                           else getString(R.string.now_due_at, clockText(now.dose.minuteOfDay))
                takenButton(true, R.string.dose_taken_big)
                binding.medsMoreRow.visibility = View.VISIBLE
            }
            is TodayPlanner.Now.DoseLater -> {
                binding.tvMedsTitle.text = getString(R.string.now_next_title, clockText(now.atMinute))
                binding.tvMedsSub.text = listOf(now.dose.name, detail(now.dose)).filter { it.isNotBlank() }.joinToString(" · ")
                whenText = if (now.snoozed) getString(R.string.now_remind_at, clockText(now.atMinute))
                           else getString(R.string.now_in, duration(now.atMinute - nowMinute()))
                takenButton(false, R.string.now_took_early)
                binding.medsMoreRow.visibility = View.GONE
            }
            else -> {   // no list from the care manager: the simple one-tap question
                binding.tvMedsTitle.setText(R.string.meds_title)
                binding.tvMedsSub.setText(R.string.meds_name)
                whenText = null
                takenButton(true, R.string.meds_taken)
                binding.medsMoreRow.visibility = View.VISIBLE
            }
        }
        binding.tvMedsSub.visibility = if (binding.tvMedsSub.text.isNullOrBlank()) View.GONE else View.VISIBLE
        binding.tvMedsWhen.visibility = if (whenText == null) View.GONE else View.VISIBLE
        binding.tvMedsWhen.text = whenText ?: ""
        binding.tvMedsWhen.setTextColor(ContextCompat.getColor(this,
            if (now is TodayPlanner.Now.DoseDue && now.minutesLate > 30) R.color.bad else R.color.primary_dark))
    }

    /** Three small status chips: check-in, medicines, steps. Each has an icon and words. */
    private fun renderStrip(p: TodayPlanner.Plan, checkinDone: Boolean) {
        val status = prefs.getString("checkin_status", "good") ?: "good"
        val (face, feel) = when (status) {
            "good" -> R.drawable.ic_face_happy to R.string.chip_feel_good
            "weak" -> R.drawable.ic_face_neutral to R.string.chip_feel_weak
            else -> R.drawable.ic_face_sad to R.string.chip_feel_bad
        }
        chip(binding.chipCheckin, if (checkinDone) face else R.drawable.ic_clock,
            getString(R.string.chip_checkin), getString(if (checkinDone) feel else R.string.chip_not_yet))
        val medsValue = when {
            p.total > 0 -> getString(R.string.chip_meds_value, p.taken, p.total)
            prefs.getString("meds_date", "") == today() -> getString(R.string.chip_done)
            else -> getString(R.string.chip_not_yet)
        }
        chip(binding.chipDoses, R.drawable.ic_pill, getString(R.string.chip_meds), medsValue)
        val steps = lastSteps
        if (watchLinked && steps != null) chip(binding.chipSteps, R.drawable.ic_steps, getString(R.string.chip_steps),
            String.format(LocaleManager.locale(this), "%,d", steps))
        else chip(binding.chipSteps, R.drawable.ic_watch, getString(R.string.chip_watch), getString(R.string.chip_no_watch))
    }

    private fun chip(v: android.widget.TextView, icon: Int, label: String, value: String) {
        v.text = android.text.SpannableStringBuilder(label + "\n").apply {
            val start = length
            append(value)
            setSpan(android.text.style.StyleSpan(android.graphics.Typeface.BOLD), start, length, 0)
            setSpan(android.text.style.RelativeSizeSpan(1.15f), start, length, 0)
        }
        v.setCompoundDrawablesRelativeWithIntrinsicBounds(0, icon, 0, 0)
        v.contentDescription = "$label: $value"
    }

    private fun onMedTapped(action: String, tapped: View) {
        if (medsLocked) return
        tapped.tick()
        A11yPrefs.tap(tapped)
        val now = plan?.now
        val dose = (now as? TodayPlanner.Now.DoseDue)?.dose ?: (now as? TodayPlanner.Now.DoseLater)?.dose
        if (dose != null) {
            val medId = dose.key.substringBefore("@")
            val time = dose.key.substringAfter("@")
            if (action == "later") {
                CareRepo.snooze(this, dose.key, nowMinute() + 15)
                com.aegis.saathi.meds.DoseAlarms.snooze(this, medId, time, dose.name, dose.doseText)
                toast(R.string.dose_snoozed)
            } else {
                lifecycleScope.launch { CareRepo.answerDose(this@MainActivity, medId, time, action) }
                toastText(getString(if (action == "taken") R.string.dose_thanks else R.string.dose_skipped_note))
            }
            // the card moves on to whatever comes next
            binding.cardMeds.animate().alpha(0f).translationX(-40f).setDuration(160).withEndAction {
                renderNow()
                binding.cardMeds.translationX = 40f
                binding.cardMeds.animate().alpha(1f).translationX(0f).setDuration(200).start()
            }.start()
            return
        }
        // no list from the care manager: the simple one-tap answer
        if (action == "later") {
            lifecycleScope.launch { AegisApiClient.submitMedication(seniorId, "later") }
            toast(R.string.meds_later_toast)
            return
        }
        medsLocked = true
        lifecycleScope.launch {
            val ok = AegisApiClient.submitMedication(seniorId, action)
            if (!ok) {
                toast(R.string.err_network)
                medsLocked = false
                return@launch
            }
            prefs.edit().putString("meds_date", today()).putString("meds_action", action).apply()
            toastText(getString(if (action == "taken") R.string.meds_done_taken else R.string.meds_done_skipped))
            renderNow()
        }
    }

    // ------------------------------------------------------------------------ 3. voice note
    private fun onVoiceTapped() {
        if (voiceJob?.isActive == true) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            micPermission.launch(Manifest.permission.RECORD_AUDIO)
            return
        }
        startVoiceNote()
    }

    private fun startVoiceNote() {
        voiceJob = lifecycleScope.launch {
            setVoiceUi(getString(R.string.voice_listening), getString(R.string.voice_listening_hint), listening = true)
            val r = recorder.recordUtterance(noSpeechTimeoutMs = 8000) { lvl ->
                binding.btnVoice.post {
                    binding.ivVoiceIcon.scaleX = 1f + 0.3f * lvl
                    binding.ivVoiceIcon.scaleY = 1f + 0.3f * lvl
                }
            }
            val wav = r.wav
            when {
                r.micError -> {
                    setVoiceUi(getString(R.string.voice_title), getString(R.string.voice_mic_off), listening = false)
                }
                wav == null -> {
                    setVoiceUi(getString(R.string.voice_title), getString(R.string.voice_none), listening = false)
                }
                else -> {
                    setVoiceUi(getString(R.string.voice_sending), getString(R.string.voice_wait), listening = false)
                    CallApi.voiceNote(seniorId, wav).onSuccess { json ->
                        val heard = json.optString("heard", "")
                        val status = json.optString("status", "good")
                        if (json.optString("action") == "dial" && json.optString("phone").isNotBlank()) {
                            // "call my son": Saathi says whom she is calling and opens the dialer with the number
                            val reply = json.optString("reply", "")
                            setVoiceUi(getString(R.string.voice_saathi), reply, listening = false)
                            notePlayer.speak(reply, json.optString("audio_url", "").ifEmpty { null })
                            familyTab.dial(json.optString("phone"))
                            setVoiceUi(getString(R.string.voice_title), getString(R.string.voice_hint), listening = false)
                            return@onSuccess
                        }
                        if (heard.isBlank()) {
                            setVoiceUi(getString(R.string.voice_title), getString(R.string.voice_unclear), listening = false)
                        } else {
                            setVoiceUi(getString(R.string.voice_title), getString(R.string.voice_heard, heard), listening = false)
                            if (!checkinLocked) {
                                prefs.edit().putString("checkin_date", today()).putString("checkin_status", status).apply()
                                showCheckinDone(status, animate = true)
                            }
                            // Saathi answers out loud, and if something is wrong she starts a conversation right away
                            val reply = json.optString("reply", "")
                            if (reply.isNotBlank()) {
                                setVoiceUi(getString(R.string.voice_saathi), reply, listening = false)
                                notePlayer.speak(reply, json.optString("audio_url", "").ifEmpty { null })
                            }
                            val callId = json.optString("call_id", "")
                            if (json.optBoolean("start_call", false) && callId.isNotEmpty()) {
                                startActivity(Intent(this@MainActivity, CallActivity::class.java).putExtra("CALL_ID", callId))
                            }
                            if (reply.isNotBlank()) setVoiceUi(getString(R.string.voice_title), getString(R.string.voice_hint), listening = false)
                        }
                    }.onFailure {
                        setVoiceUi(getString(R.string.voice_title), getString(R.string.voice_failed), listening = false)
                    }
                }
            }
        }
    }

    private fun setVoiceUi(label: String, hint: String, listening: Boolean) {
        binding.tvVoiceLabel.text = label
        binding.tvVoiceHint.text = hint
        // TalkBack hears "Listening…", "Sending…" and what Saathi understood, not a fixed "Tell us by voice"
        binding.btnVoice.contentDescription = if (hint.isBlank()) label else "$label. $hint"
        binding.btnVoice.announceForAccessibility(binding.btnVoice.contentDescription)
        voiceBreathing?.cancel()
        binding.ivVoiceIcon.scaleX = 1f
        binding.ivVoiceIcon.scaleY = 1f
        binding.btnVoice.scaleX = 1f
        binding.btnVoice.scaleY = 1f
        if (listening) {
            binding.btnVoice.tick()
            voiceBreathing = binding.btnVoice.breathe()
        }
    }

    private fun toggleFallDetection() {
        val enable = !prefs.getBoolean(CallListenerService.PREF_FALL_DETECT, false)
        prefs.edit().putBoolean(CallListenerService.PREF_FALL_DETECT, enable).apply()
        CallListenerService.refreshFallDetection(this)
        toast(if (enable) R.string.fall_enabled else R.string.fall_disabled)
    }

    // ------------------------------------------------------------------------ family sharing (the senior decides)
    fun showFamilyDialog() {
        val on = prefs.getBoolean("family_on", false)
        val code = prefs.getString("family_code", "") ?: ""
        val builder = androidx.appcompat.app.AlertDialog.Builder(this).setTitle(getString(R.string.family_title))
        if (on && code.isNotEmpty()) {
            builder.setMessage(getString(R.string.family_on_msg, code, AegisApiClient.baseUrl))
                .setPositiveButton(getString(R.string.common_ok), null)
                .setNegativeButton(getString(R.string.family_stop)) { _, _ -> setFamilySharing(false) }
        } else {
            builder.setMessage(getString(R.string.family_off_msg))
                .setPositiveButton(getString(R.string.family_allow)) { _, _ -> setFamilySharing(true) }
                .setNegativeButton(getString(R.string.common_cancel), null)
        }
        builder.show()
    }

    private fun setFamilySharing(enable: Boolean) {
        lifecycleScope.launch {
            val code = CallApi.familyConsent(enable)
            if (code == null) {
                toast(R.string.err_network)
                return@launch
            }
            prefs.edit().putBoolean("family_on", enable).putString("family_code", code).apply()
            familyTab.render(CareRepo.contacts.value, enable)
            if (enable) showFamilyDialog() else toast(R.string.family_stopped)
        }
    }

    // ------------------------------------------------------------------------ menu item
    fun missedCallCheckin() {
        lifecycleScope.launch {
            AegisApiClient.submitCheckin(seniorId, "missed_call", "good", getString(R.string.checkin_note_good))
            toast(R.string.missed_call_done)
        }
    }

    // ------------------------------------------------------------------------ readings
    fun showReadingsDialog() {
        val v = layoutInflater.inflate(R.layout.dialog_readings, null)
        val sys = v.findViewById<android.widget.EditText>(R.id.etBpSys)
        val dia = v.findViewById<android.widget.EditText>(R.id.etBpDia)
        val sugar = v.findViewById<android.widget.EditText>(R.id.etSugar)
        val weight = v.findViewById<android.widget.EditText>(R.id.etWeight)
        androidx.appcompat.app.AlertDialog.Builder(this)
            .setView(v)
            .setPositiveButton(getString(R.string.readings_save)) { _, _ ->
                val bpS = sys.text.toString().toIntOrNull()
                val bpD = dia.text.toString().toIntOrNull()
                val sg = sugar.text.toString().toDoubleOrNull()
                val wt = weight.text.toString().toDoubleOrNull()
                val hasBp = bpS != null && bpD != null
                if (!hasBp && sg == null && wt == null) {
                    toast(R.string.readings_empty)
                    return@setPositiveButton
                }
                lifecycleScope.launch {
                    val ok = CallApi.syncVitals(
                        seniorId, null, null, null, null,
                        bpSys = if (hasBp) bpS else null, bpDia = if (hasBp) bpD else null,
                        sugar = sg, weight = wt, source = "manual"
                    )
                    if (ok) {
                        val parts = listOfNotNull(
                            if (hasBp) "$bpS/$bpD" else null,
                            sg?.let { "${it.toInt()} mg/dL" },
                            wt?.let { "$it kg" }
                        )
                        prefs.edit().putString("last_readings", parts.joinToString("  ·  ")).apply()
                        showLastReadings()
                        toast(R.string.readings_saved)
                    } else {
                        toast(R.string.err_network)
                    }
                }
            }
            .setNegativeButton(getString(R.string.common_cancel), null)
            .show()
    }

    private fun showLastReadings() {
        val last = prefs.getString("last_readings", "").orEmpty()
        binding.tvReadingsLast.text = if (last.isEmpty()) getString(R.string.readings_sub) else getString(R.string.readings_last, last)
        binding.pageMe.tvMeReadings.text = binding.tvReadingsLast.text
    }

    // ------------------------------------------------------------------------ SOS
    // Three safeguards against false alarms: (1) 3-second hold on a small button, (2) a 5-second
    // countdown with a big Cancel, (3) a 30-second "pressed by mistake" undo after it is sent.
    // The server also merges repeated presses into one event.
    private fun setupSos() {
        binding.sosButton.onHoldStateChanged = { holding ->
            binding.tvSosHint.text = getString(if (holding) R.string.sos_holding else R.string.sos_hold_hint)
        }
        binding.sosButton.onHoldComplete = { beginSosCountdown() }
        binding.btnSosCancel.pressable()
        binding.btnSosCancel.setOnClickListener { cancelSosCountdown() }
        binding.btnSosClose.setOnClickListener { hideSosOverlay() }
        binding.btnSosUndo.setOnClickListener { undoSos() }
    }

    private fun showSosOverlay() {
        binding.sosOverlay.alpha = 0f
        binding.sosOverlay.visibility = View.VISIBLE
        binding.sosOverlay.animate().alpha(1f).setDuration(180).start()
    }

    private fun hideSosOverlay() {
        sosState = 0
        binding.sosOverlay.animate().alpha(0f).setDuration(180).withEndAction {
            binding.sosOverlay.visibility = View.GONE
            binding.btnSosCancel.visibility = View.VISIBLE
            binding.btnSosUndo.visibility = View.GONE
            binding.btnSosClose.visibility = View.GONE
            binding.sosCountWrap.visibility = View.VISIBLE
            binding.ivSosIcon.setImageResource(R.drawable.ic_sos)
            binding.tvSosTitle.text = getString(R.string.sos_count_title)
            binding.tvSosSub.text = getString(R.string.sos_count_sub)
        }.start()
        binding.tvSosHint.text = getString(R.string.sos_hold_hint)
    }

    private fun beginSosCountdown() {
        if (sosState != 0) return
        sosState = 1
        showSosOverlay()
        sosCountJob?.cancel()
        sosCountJob = lifecycleScope.launch {
            for (n in 5 downTo 1) {
                binding.tvSosCount.text = n.toString()
                binding.sosCountWrap.scaleX = 1.18f
                binding.sosCountWrap.scaleY = 1.18f
                binding.sosCountWrap.animate().scaleX(1f).scaleY(1f).setDuration(420).start()
                binding.sosOverlay.performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK)
                delay(1000)
            }
            sendSos()
        }
    }

    private fun cancelSosCountdown() {
        sosCountJob?.cancel()
        hideSosOverlay()
    }

    private fun sendSos() {
        sosState = 2
        binding.sosOverlay.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
        binding.ivSosIcon.setImageResource(R.drawable.ic_check)
        binding.tvSosTitle.text = getString(R.string.sos_sent_title)
        binding.tvSosSub.text = getString(R.string.sos_sent_sub)
        binding.sosCountWrap.visibility = View.GONE
        binding.btnSosCancel.visibility = View.GONE
        binding.btnSosClose.visibility = View.VISIBLE
        binding.btnSosUndo.visibility = View.VISIBLE
        sosCountJob = lifecycleScope.launch {
            val ok = AegisApiClient.triggerSos(seniorId)
            if (!ok) binding.tvSosSub.text = getString(R.string.sos_failed)
            launch {
                SosLocation.current(this@MainActivity)?.let { AegisApiClient.triggerSos(seniorId, it.latitude, it.longitude) }
            }
            delay(30_000)               // the undo window is 30 seconds on the phone (2 minutes on the server)
            binding.btnSosUndo.visibility = View.GONE
        }
    }

    private fun undoSos() {
        binding.btnSosUndo.visibility = View.GONE
        lifecycleScope.launch {
            CallApi.cancelSos(seniorId)
            binding.tvSosTitle.text = getString(R.string.sos_cancelled)
            binding.tvSosSub.text = ""
            binding.ivSosIcon.setImageResource(R.drawable.ic_check)
        }
    }

    // ------------------------------------------------------------------------ misc
    private fun toast(res: Int) = Notice.show(this, getString(res), error = res == R.string.err_network)
    fun toastText(text: String) = Notice.show(this, text)

    // ------------------------------------------------------------------------ read aloud
    private val reader by lazy { com.aegis.saathi.call.SpeechPlayer(this, callChannel = false) }

    /** Reads Today in Saathi's voice: the greeting, what the "right now" card says, and what comes next. */
    private fun readTodayAloud() {
        val parts = mutableListOf<CharSequence>(binding.tvSeniorGreeting.text)
        when {
            binding.cardMeds.visibility == View.VISIBLE -> parts += listOf(binding.tvMedsTitle.text, binding.tvMedsSub.text, binding.tvMedsWhen.text)
            binding.cardCheckin.visibility == View.VISIBLE -> parts += binding.tvCheckinTitle.text
            binding.allDone.root.visibility == View.VISIBLE -> parts += listOf(binding.allDone.tvEmptyTitle.text, binding.allDone.tvEmptyBody.text)
        }
        if (binding.tvComingUp.visibility == View.VISIBLE) parts += binding.tvComingUp.text
        val text = parts.map { it.toString().trim().trimEnd('.', '।') }.filter { it.isNotEmpty() }.joinToString(". ")
        lifecycleScope.launch { reader.say(text, english = LocaleManager.current(this@MainActivity) == LocaleManager.EN) }
    }

    override fun onDestroy() {
        notePlayer.release()
        reader.release()
        super.onDestroy()
        voiceBreathing?.cancel()
        sosCountJob?.cancel()
    }
}
