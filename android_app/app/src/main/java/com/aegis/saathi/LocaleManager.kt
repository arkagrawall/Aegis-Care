package com.aegis.saathi

import android.content.Context
import android.content.res.Configuration
import java.util.Locale

/**
 * App-wide language (Hindi / English), independent of the phone's own language.
 * Every Activity, the Application and the background Service wrap their context with [wrap],
 * so all texts (including notifications) follow the choice made with the toggle at the top.
 */
object LocaleManager {
    private const val PREFS = "aegis_senior_prefs"
    private const val KEY = "lang"
    const val HI = "hi"
    const val EN = "en"

    fun current(context: Context): String =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, HI) ?: HI

    fun isChosen(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).contains(KEY)

    fun set(context: Context, lang: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(KEY, lang).apply()
    }

    fun wrap(base: Context): Context {
        val locale = Locale(current(base))
        Locale.setDefault(locale)
        val config = Configuration(base.resources.configuration)
        config.setLocale(locale)
        config.setLayoutDirection(locale)
        return base.createConfigurationContext(config)
    }

    fun locale(context: Context): Locale = Locale(current(context))

    /** A string in the language chosen right now (Application/Service contexts are wrapped only once, at start). */
    fun string(context: Context, res: Int, vararg args: Any): String = wrap(context).getString(res, *args)
}
