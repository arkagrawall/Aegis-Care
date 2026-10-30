package com.aegis.saathi.ui

import android.animation.Animator
import android.animation.ObjectAnimator
import android.animation.PropertyValuesHolder
import android.animation.ValueAnimator
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.view.animation.DecelerateInterpolator
import androidx.activity.OnBackPressedCallback
import com.aegis.saathi.R
import com.aegis.saathi.call.IncomingCalls
import com.aegis.saathi.call.Ringer
import com.aegis.saathi.databinding.ActivityIncomingCallBinding

/**
 * The ringing screen, shown over the lock screen (no unlock needed to answer, like a phone call). It does not ring
 * itself: the service's [Ringer] does, and owns the 30 s timeout. Two large plain-tap buttons, no swiping.
 */
class IncomingCallActivity : BaseActivity() {

    private lateinit var binding: ActivityIncomingCallBinding
    private var callId: String = ""
    private val ringAnimators = mutableListOf<Animator>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // over the lock screen; deliberately no requestDismissKeyguard (that pops up the PIN pad instead of ringing)
        setShowWhenLocked(true)
        setTurnScreenOn(true)

        binding = ActivityIncomingCallBinding.inflate(layoutInflater)
        setContentView(binding.root)
        bind(intent)

        A11y.button(binding.btnAcceptCall, getString(R.string.inc_accept_long))
        A11y.button(binding.btnDeclineCall, getString(R.string.inc_decline_long))
        binding.btnDeclineCall.setOnClickListener {
            A11y.tap(it)
            IncomingCalls.declined(this, callId)
            finish()
        }
        binding.btnAcceptCall.setOnClickListener {
            A11y.tap(it)
            startActivity(Intent(this, CallActivity::class.java).putExtra("CALL_ID", callId))
            IncomingCalls.accepted(this, callId)
            finish()
        }
        // back does not decline by accident
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {}
        })
        IncomingCalls.onRingingOver = { runOnUiThread { if (!isFinishing) finish() } }
        startRingAnimations()
    }

    /** A newer call replaces the one on screen. */
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        bind(intent)
    }

    private fun bind(i: Intent) {
        callId = i.getStringExtra("CALL_ID").orEmpty()
        // already answered, declined or timed out (e.g. the notification was tapped late)
        if (callId.isEmpty() || Ringer.ringingCallId != callId) {
            finish()
            return
        }
        binding.tvCallerName.text = getString(R.string.inc_name)
        binding.root.announceForAccessibility(getString(R.string.inc_announce))
    }

    /** Gentle pulsing rings; none when the system "remove animations" setting is on. */
    private fun startRingAnimations() {
        if (!ValueAnimator.areAnimatorsEnabled()) return
        listOf(binding.ring1, binding.ring2, binding.ring3).forEachIndexed { i, ring ->
            ringAnimators += ObjectAnimator.ofPropertyValuesHolder(
                ring,
                PropertyValuesHolder.ofFloat(View.SCALE_X, 1f, 1.9f),
                PropertyValuesHolder.ofFloat(View.SCALE_Y, 1f, 1.9f),
                PropertyValuesHolder.ofFloat(View.ALPHA, 0.5f, 0f)
            ).apply {
                duration = 2400
                startDelay = i * 800L
                repeatCount = ObjectAnimator.INFINITE
                interpolator = DecelerateInterpolator()
                start()
            }
        }
        ringAnimators += ObjectAnimator.ofFloat(binding.ivAcceptIcon, View.ROTATION, -12f, 12f).apply {
            duration = 300
            repeatCount = ObjectAnimator.INFINITE
            repeatMode = ObjectAnimator.REVERSE
            start()
        }
    }

    override fun onDestroy() {
        if (IncomingCalls.onRingingOver != null) IncomingCalls.onRingingOver = null
        ringAnimators.forEach { it.cancel() }
        super.onDestroy()
    }
}
