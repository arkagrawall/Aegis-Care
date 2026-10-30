package com.aegis.saathi.ui

import android.app.NotificationManager
import android.content.Context
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.os.CountDownTimer
import android.os.VibrationEffect
import android.os.Vibrator
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import com.aegis.saathi.R
import com.aegis.saathi.api.AegisApiClient
import com.aegis.saathi.call.CallApi
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/**
 * "Did you fall?" screen, opened by the phone-sensor FallDetector. Nothing is sent to the care team
 * until the senior answers here, or fails to answer for 30 seconds:
 *   I'm OK                -> logged as a false trigger, nothing else happens
 *   I fell, but I'm OK    -> a possible-fall flag for a human to follow up (not an emergency)
 *   I need help / no answer -> a tracked SOS, same as the SOS button
 */
class FallCheckActivity : BaseActivity() {

    companion object {
        const val EXTRA_IMPACT_G = "IMPACT_G"
        const val NOTIF_ID = 2003
        private const val TOTAL_S = 30
        private const val PREFS = "aegis_senior_prefs"
        private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    }

    private var answered = false
    private var impactG = 0f
    private var timer: CountDownTimer? = null
    private lateinit var tvCount: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        impactG = intent.getFloatExtra(EXTRA_IMPACT_G, 0f)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
        } else {
            @Suppress("DEPRECATION")
            window.addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON)
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContentView(buildLayout())
        buzz()
        startCountdown()
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private fun roundRect(color: Int, radiusDp: Int = 18) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = dp(radiusDp).toFloat()
    }

    private fun bigButton(text: Int, fill: Int, textColor: Int, onClick: () -> Unit) = Button(this).apply {
        setText(text)
        isAllCaps = false
        textSize = 20f
        typeface = Typeface.DEFAULT_BOLD
        setTextColor(textColor)
        background = roundRect(fill)
        stateListAnimator = null
        minHeight = dp(72)
        setOnClickListener { onClick() }
        layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT)
            .apply { topMargin = dp(14) }
    }

    private fun buildLayout(): View {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setBackgroundColor(androidx.core.content.ContextCompat.getColor(this@FallCheckActivity, R.color.fall_bg))
            setPadding(dp(24), dp(48), dp(24), dp(24))
        }
        root.addView(TextView(this).apply {
            setText(R.string.fall_title)
            textSize = 30f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(androidx.core.content.ContextCompat.getColor(this@FallCheckActivity, R.color.fall_title))
            gravity = Gravity.CENTER
        })
        root.addView(TextView(this).apply {
            setText(R.string.fall_msg)
            textSize = 19f
            setTextColor(androidx.core.content.ContextCompat.getColor(this@FallCheckActivity, R.color.fall_body))
            gravity = Gravity.CENTER
            setPadding(0, dp(12), 0, dp(8))
        })
        tvCount = TextView(this).apply {
            textSize = 22f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(androidx.core.content.ContextCompat.getColor(this@FallCheckActivity, R.color.fall_alert))
            gravity = Gravity.CENTER
            setPadding(0, dp(8), 0, dp(16))
        }
        root.addView(tvCount)
        root.addView(bigButton(R.string.fall_ok, androidx.core.content.ContextCompat.getColor(this, R.color.call_answer), Color.WHITE) { answer("false_alarm") })
        root.addView(bigButton(R.string.fall_fell_ok, androidx.core.content.ContextCompat.getColor(this@FallCheckActivity, R.color.fall_mid), androidx.core.content.ContextCompat.getColor(this@FallCheckActivity, R.color.fall_mid_ink)) { answer("ok_but_fell") })
        root.addView(bigButton(R.string.fall_help, androidx.core.content.ContextCompat.getColor(this@FallCheckActivity, R.color.fall_alert), Color.WHITE) { answer("need_help") })
        return root
    }

    private fun startCountdown() {
        tvCount.text = getString(R.string.fall_countdown, TOTAL_S)
        timer = object : CountDownTimer(TOTAL_S * 1000L, 1000L) {
            override fun onTick(msLeft: Long) {
                tvCount.text = getString(R.string.fall_countdown, ((msLeft + 999) / 1000).toInt())
            }

            override fun onFinish() {
                answer("no_response")
            }
        }.start()
    }

    private fun answer(outcome: String) {
        if (answered) return
        answered = true
        timer?.cancel()
        val seniorId = getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("senior_id", null)
        if (seniorId != null && AegisApiClient.deviceKey.isNotEmpty()) {
            val g = impactG
            scope.launch { CallApi.reportFall(seniorId, outcome, g) }
        }
        val msg = when (outcome) {
            "false_alarm" -> R.string.fall_done_ok
            "ok_but_fell" -> R.string.fall_done_fell
            else -> R.string.fall_done_help
        }
        android.widget.Toast.makeText(this, msg, android.widget.Toast.LENGTH_LONG).show()
        try { (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).cancel(NOTIF_ID) } catch (_: Exception) {}
        finish()
    }

    private fun buzz() {
        try {
            val v = getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
            val pattern = longArrayOf(0, 600, 400, 600, 400, 600)
            if (Build.VERSION.SDK_INT >= 26) v.vibrate(VibrationEffect.createWaveform(pattern, -1))
            else @Suppress("DEPRECATION") v.vibrate(pattern, -1)
        } catch (_: Exception) {}
    }

    @Deprecated("Back must not dismiss a fall check")
    override fun onBackPressed() {
        // deliberately ignored: the senior has to answer, or the countdown decides
    }

    override fun onDestroy() {
        timer?.cancel()
        super.onDestroy()
    }
}
