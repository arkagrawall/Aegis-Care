package com.aegis.saathi.ui

import android.content.Context
import android.content.Intent
import android.content.res.ColorStateList
import android.os.Bundle
import android.provider.Settings
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.RecyclerView
import androidx.viewpager2.widget.ViewPager2
import com.aegis.saathi.A11yPrefs
import com.aegis.saathi.LocaleManager
import com.aegis.saathi.R
import com.aegis.saathi.call.SpeechPlayer
import com.aegis.saathi.databinding.ActivityIntroBinding
import com.aegis.saathi.databinding.ItemIntroSlideBinding
import kotlinx.coroutines.launch
import kotlin.math.abs

/**
 * Six welcome slides shown once, before setup: what Saathi does, in pictures and two short lines each.
 * Swipe or use Back / Next; "Skip" and the last slide's "Get started" go on to setup. The language can be
 * switched on any slide, and "Listen" reads the slide out loud. Opened again from the Me tab with REPLAY.
 */
class IntroActivity : BaseActivity() {

    companion object {
        const val REPLAY = "replay"
    }

    private data class Slide(val art: Int, val title: Int, val body: Int)

    private val slides = listOf(
        Slide(R.drawable.ill_welcome, R.string.intro_1_title, R.string.intro_1_body),
        Slide(R.drawable.ill_checkin, R.string.intro_2_title, R.string.intro_2_body),
        Slide(R.drawable.ill_calls, R.string.intro_3_title, R.string.intro_3_body),
        Slide(R.drawable.ill_medicines, R.string.intro_4_title, R.string.intro_4_body),
        Slide(R.drawable.ill_sos, R.string.intro_5_title, R.string.intro_5_body),
        Slide(R.drawable.ill_family, R.string.intro_6_title, R.string.intro_6_body),
    )

    private lateinit var binding: ActivityIntroBinding
    private val player by lazy { SpeechPlayer(this, callChannel = false) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityIntroBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.pager.adapter = Adapter()
        binding.pager.offscreenPageLimit = 1
        if (animationsOn()) binding.pager.setPageTransformer { page, pos ->
            // the picture drifts slower than the page (gentle depth); the words fade
            page.findViewById<View>(R.id.ivSlide)?.translationX = -pos * page.width * 0.3f
            listOf(R.id.tvSlideTitle, R.id.tvSlideBody, R.id.btnListen).forEach { id ->
                page.findViewById<View>(id)?.alpha = 1f - minOf(1f, abs(pos) * 1.4f)
            }
        }
        binding.pager.registerOnPageChangeCallback(object : ViewPager2.OnPageChangeCallback() {
            override fun onPageSelected(position: Int) {
                render(position)
                player.stop()
                binding.pager.announceForAccessibility(
                    getString(R.string.intro_slide_of, position + 1, slides.size) + ". " + getString(slides[position].title))
            }
        })

        binding.btnPrev.setOnClickListener { A11yPrefs.tap(it); binding.pager.currentItem -= 1 }
        binding.btnNextSlide.setOnClickListener {
            A11yPrefs.tap(it)
            if (binding.pager.currentItem == slides.lastIndex) done() else binding.pager.currentItem += 1
        }
        binding.btnSkip.setOnClickListener { done() }
        binding.btnNextSlide.pressable()
        binding.langToggle.onLanguageSelected = { lang ->
            if (lang != LocaleManager.current(this)) {
                LocaleManager.set(this, lang)
                intent.putExtra("page", binding.pager.currentItem)
                binding.root.animate().alpha(0f).setDuration(140).withEndAction { recreate() }.start()
            }
        }

        val start = savedInstanceState?.getInt("page") ?: intent.getIntExtra("page", 0)
        binding.pager.setCurrentItem(start, false)
        render(start)
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putInt("page", binding.pager.currentItem)
    }

    private fun animationsOn(): Boolean =
        Settings.Global.getFloat(contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) > 0f

    /** Dots, Back visibility, and Next turning into a filled "Get started" on the last slide. */
    private fun render(position: Int) {
        val d = resources.displayMetrics.density
        binding.introDots.removeAllViews()
        slides.indices.forEach { i ->
            val on = i == position
            binding.introDots.addView(View(this).apply {
                background = ContextCompat.getDrawable(this@IntroActivity, R.drawable.bg_dot)?.mutate()
                backgroundTintList = ColorStateList.valueOf(ContextCompat.getColor(this@IntroActivity, if (on) R.color.primary else R.color.primary_soft))
                layoutParams = LinearLayout.LayoutParams(((if (on) 26 else 10) * d).toInt(), (10 * d).toInt()).apply {
                    marginStart = (5 * d).toInt(); marginEnd = (5 * d).toInt()
                }
            })
        }
        binding.btnPrev.visibility = if (position == 0) View.INVISIBLE else View.VISIBLE
        val last = position == slides.lastIndex
        binding.btnNextSlide.text = getString(if (last) R.string.intro_start else R.string.intro_next)
        if (last) {
            binding.btnNextSlide.setBackgroundResource(R.drawable.bg_btn_teal)
            binding.btnNextSlide.setTextColor(ContextCompat.getColor(this, android.R.color.white))
        } else {
            binding.btnNextSlide.setBackgroundResource(android.R.color.transparent)
            binding.btnNextSlide.setTextColor(ContextCompat.getColor(this, R.color.primary_dark))
        }
        binding.btnSkip.visibility = if (last) View.INVISIBLE else View.VISIBLE
    }

    private fun done() {
        getSharedPreferences("aegis_senior_prefs", Context.MODE_PRIVATE).edit().putBoolean("intro_seen", true).apply()
        if (!intent.getBooleanExtra(REPLAY, false)) startActivity(Intent(this, OnboardingActivity::class.java))
        finish()
    }

    override fun onDestroy() {
        player.release()
        super.onDestroy()
    }

    private inner class Holder(val b: ItemIntroSlideBinding) : RecyclerView.ViewHolder(b.root)

    private inner class Adapter : RecyclerView.Adapter<Holder>() {
        override fun getItemCount() = slides.size

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): Holder {
            val b = ItemIntroSlideBinding.inflate(LayoutInflater.from(parent.context), parent, false)
            // the picture takes about 42% of the screen, whatever the phone
            b.ivSlide.layoutParams.height = (resources.displayMetrics.heightPixels * 0.42f).toInt()
            return Holder(b)
        }

        override fun onBindViewHolder(h: Holder, position: Int) {
            val s = slides[position]
            h.b.ivSlide.setImageResource(s.art)
            h.b.tvSlideTitle.setText(s.title)
            h.b.tvSlideBody.setText(s.body)
            h.b.root.contentDescription = getString(R.string.intro_slide_of, position + 1, slides.size)
            h.b.btnListen.pressable()
            h.b.btnListen.setOnClickListener {
                A11yPrefs.tap(it)
                val text = getString(s.title) + ". " + getString(s.body)
                lifecycleScope.launch { player.say(text, english = LocaleManager.current(this@IntroActivity) == LocaleManager.EN) }
            }
            A11yPrefs.applyContrast(h.b.root)
        }
    }
}
