package com.aegis.saathi.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.media.AudioManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.view.WindowManager
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.aegis.saathi.R
import com.aegis.saathi.call.ActiveCall
import com.aegis.saathi.call.CallUiState
import com.aegis.saathi.call.IncomingCalls
import com.aegis.saathi.call.Phase
import com.aegis.saathi.call.ProximityGuard
import com.aegis.saathi.call.VoiceCallController
import com.aegis.saathi.databinding.ActivityCallBinding
import com.aegis.saathi.service.CallListenerService
import kotlinx.coroutines.launch

/**
 * The Saathi call. Hands-free: Saathi speaks, the microphone opens by itself, the senior just talks.
 * Built for seniors: one clear status line, Saathi's words in large type, three large labelled controls
 * (Speaker, Mute, Type) and a full-width End call. Works over the lock screen; at the ear the screen goes dark
 * ([ProximityGuard] plus the proximity wake lock in CallAudio) and the call keeps running with the screen off
 * (the call service holds the microphone foreground type and shows "Saathi call · Hang up").
 */
class CallActivity : BaseActivity() {

    companion object {
        /** Set when the senior pressed Answer on the call notification instead of the ringing screen. */
        const val EXTRA_ANSWERED_FROM_NOTIFICATION = "ANSWERED_FROM_NOTIFICATION"
    }

    private lateinit var binding: ActivityCallBinding
    private var controller: VoiceCallController? = null
    private var proximity: ProximityGuard? = null
    private var callId = ""
    private var started = false
    private var finishedNormally = false
    private var hungUp = false

    private val handler = Handler(Looper.getMainLooper())
    private var secondsElapsed = 0
    private val timerTick = object : Runnable {
        override fun run() {
            secondsElapsed++
            binding.tvTimer.text = clock(secondsElapsed)
            handler.postDelayed(this, 1000)
        }
    }

    private val micPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted -> startCall(granted) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setShowWhenLocked(true)
        setTurnScreenOn(true)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)   // ProximityGuard drops it at the ear
        volumeControlStream = AudioManager.STREAM_VOICE_CALL // volume keys change the call volume, like a phone call

        binding = ActivityCallBinding.inflate(layoutInflater)
        setContentView(binding.root)

        callId = intent.getStringExtra("CALL_ID") ?: ""
        if (callId.isEmpty()) {
            finish()
            return
        }
        // answered from the notification: the ringing stops and the hub is told, like the ringing screen does
        if (intent.getBooleanExtra(EXTRA_ANSWERED_FROM_NOTIFICATION, false)) IncomingCalls.accepted(this, callId)

        proximity = ProximityGuard(this, binding.earCover)
        setupControls()

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            // back must not end a call by accident: it only closes the keyboard row
            override fun handleOnBackPressed() {
                if (binding.typeRow.visibility == View.VISIBLE) binding.typeRow.visibility = View.GONE
            }
        })

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            startCall(true)
        } else {
            micPermission.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    /** Tapping "Saathi call" in the notification brings the running call back; it does not start a second one. */
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (intent.getBooleanExtra(EXTRA_ANSWERED_FROM_NOTIFICATION, false)) {
            IncomingCalls.accepted(this, intent.getStringExtra("CALL_ID").orEmpty())
        }
    }

    private fun startCall(micGranted: Boolean) {
        if (started) return
        started = true
        if (!micGranted) {
            // No microphone: the call still works by typing
            binding.typeRow.visibility = View.VISIBLE
        }
        val c = VoiceCallController(applicationContext, callId, micGranted)
        controller = c
        ActiveCall.onHangUp = { hangUp() }
        CallListenerService.callStarted(this, callId)
        c.start(lifecycleScope)
        lifecycleScope.launch { c.state.collect { render(it) } }
        handler.postDelayed(timerTick, 1000)
        proximity?.start()
    }

    // ------------------------------------------------------------------------------ rendering
    private var lastPhase: Phase? = null

    private fun render(s: CallUiState) {
        binding.orbView.setPhase(s.phase)
        binding.orbView.setLevel(if (s.muted) 0f else s.level)

        if (s.phase != lastPhase) {
            lastPhase = s.phase
            val (text, icon, tint) = when (s.phase) {
                Phase.CONNECTING -> Triple(R.string.call_connecting, R.drawable.ic_phone, R.color.call_ink_soft)
                Phase.AI_SPEAKING -> Triple(R.string.call_speaking, R.drawable.ic_wave, R.color.call_accent)
                Phase.LISTENING -> Triple(R.string.call_listening, R.drawable.ic_mic, R.color.call_listen)
                Phase.THINKING -> Triple(R.string.call_thinking, R.drawable.ic_clock, R.color.call_ink_soft)
                Phase.ENDED -> Triple(if (s.finishedNormally) R.string.call_ended_ok else R.string.call_ended, R.drawable.ic_check, R.color.call_ink)
            }
            setTextAnimated(binding.tvPhase, getString(text))
            binding.ivPhase.setImageResource(icon)
            binding.ivPhase.imageTintList = ColorStateList.valueOf(ContextCompat.getColor(this, tint))
        }

        controlState(binding.btnSpeaker, binding.speakerCircle, binding.ivSpeaker, binding.tvSpeaker,
            on = s.speakerOn, label = R.string.call_speaker)
        proximity?.enabled = !s.speakerOn
        controlState(binding.btnMute, binding.muteCircle, binding.ivMute, binding.tvMute,
            on = s.muted, label = R.string.call_mute)
        binding.ivMute.setImageResource(if (s.muted) R.drawable.ic_mic_off else R.drawable.ic_mic)
        binding.tvMute.text = getString(if (s.muted) R.string.call_muted else R.string.call_mute)

        setTextAnimated(binding.tvAiLine, s.aiLine)
        binding.tvHeardLine.visibility = if (s.heardLine.isBlank()) View.GONE else View.VISIBLE
        setTextAnimated(binding.tvHeardLine, if (s.heardLine.isBlank()) "" else getString(R.string.call_you_said, s.heardLine))

        val note = when {
            s.note.isNotBlank() -> s.note
            s.muted -> getString(R.string.call_note_muted)
            s.weakNetwork -> getString(R.string.call_note_weak)
            else -> ""
        }
        binding.tvNote.text = note
        binding.tvNote.visibility = if (note.isBlank()) View.GONE else View.VISIBLE

        if (s.phase == Phase.ENDED) {
            finishedNormally = s.finishedNormally
            showEnded(s.finishedNormally, s.note)
        }
    }

    /** A toggle shows its state three ways: a light filled circle, the label, and (for TalkBack) "on" / "off". */
    @Suppress("UNUSED_PARAMETER")
    private fun controlState(button: View, circle: FrameLayout, icon: ImageView, text: TextView, on: Boolean, label: Int) {
        circle.setBackgroundResource(if (on) R.drawable.bg_call_round_on else R.drawable.bg_call_round)
        icon.imageTintList = ColorStateList.valueOf(ContextCompat.getColor(this, if (on) R.color.call_btn_on_ink else R.color.call_ink))
        A11y.toggle(button, getString(label), on, getString(R.string.a11y_on), getString(R.string.a11y_off))
    }

    private var endShown = false

    private fun showEnded(ok: Boolean, note: String) {
        if (endShown) return
        endShown = true
        handler.removeCallbacks(timerTick)
        proximity?.stop()
        binding.tvEndTitle.text = getString(if (ok) R.string.call_end_title_ok else R.string.call_ended)
        binding.tvEndSub.text = when {
            note.isNotBlank() -> note
            ok -> getString(R.string.call_end_sub, clock(secondsElapsed))
            else -> clock(secondsElapsed)
        }
        binding.endPanel.alpha = 0f
        binding.endPanel.visibility = View.VISIBLE
        binding.endPanel.animate().alpha(1f).setDuration(250).start()
        handler.postDelayed({ closeScreen() }, if (ok) 3000L else 4000L)
    }

    private fun clock(sec: Int) = String.format(java.util.Locale.US, "%02d:%02d", sec / 60, sec % 60)

    /** Cross-fades a TextView to new text (no-op if unchanged). */
    private val textTargets = HashMap<TextView, String>()

    private fun setTextAnimated(tv: TextView, text: String) {
        val current = textTargets[tv] ?: tv.text.toString()
        if (current == text) return
        textTargets[tv] = text
        tv.animate().cancel()
        tv.animate().alpha(0f).setDuration(110).withEndAction {
            tv.text = textTargets[tv] ?: text
            tv.animate().alpha(1f).setDuration(220).start()
        }.start()
    }

    // -------------------------------------------------------------------------------- controls
    private fun setupControls() {
        binding.btnHangUp.pressable(0.97f)
        A11y.button(binding.btnHangUp, getString(R.string.call_hangup))
        binding.btnHangUp.setOnClickListener { A11y.tap(it); hangUp() }

        // Earpiece by default (hold it like a phone); speaker when they'd rather not
        binding.btnSpeaker.setOnClickListener {
            A11y.tap(it)
            val c = controller ?: return@setOnClickListener
            c.setSpeaker(!c.state.value.speakerOn)
        }
        binding.btnMute.setOnClickListener {
            A11y.tap(it)
            val c = controller ?: return@setOnClickListener
            c.setMute(!c.state.value.muted)
        }
        A11y.button(binding.btnTypeToggle, getString(R.string.call_type_toggle))
        binding.btnTypeToggle.setOnClickListener {
            A11y.tap(it)
            val show = binding.typeRow.visibility != View.VISIBLE
            binding.typeRow.visibility = if (show) View.VISIBLE else View.GONE
            if (show) binding.etTyped.requestFocus()
        }
        A11y.button(binding.btnSendTyped, getString(R.string.call_send))
        binding.btnSendTyped.setOnClickListener { sendTyped() }
        binding.etTyped.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_SEND) { sendTyped(); true } else false
        }
    }

    private fun sendTyped() {
        val text = binding.etTyped.text.toString()
        if (text.isBlank()) return
        controller?.submitTyped(text)
        binding.etTyped.setText("")
        val imm = getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager
        imm.hideSoftInputFromWindow(binding.etTyped.windowToken, 0)
    }

    private fun hangUp() {
        if (hungUp) return
        hungUp = true
        controller?.hangUp()
        showEnded(false, "")
    }

    private fun closeScreen() {
        if (isFinishing) return
        finish()
        @Suppress("DEPRECATION")
        overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out)
    }

    override fun onDestroy() {
        ActiveCall.onHangUp = null
        handler.removeCallbacksAndMessages(null)
        proximity?.stop()
        if (started) CallListenerService.callEnded(this)
        // Left the screen without hanging up (e.g. swiped away): still save the call
        if (!hungUp && !finishedNormally) controller?.hangUp()
        super.onDestroy()
    }
}
