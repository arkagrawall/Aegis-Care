package com.aegis.saathi.ui

import android.content.Context
import android.content.Intent
import android.view.View
import android.widget.PopupMenu
import com.aegis.saathi.R

/** The "three dots" overflow menu shared by the onboarding and home screens. */
object SettingsMenu {
    private const val ID_SETTINGS = 1
    private const val ID_EXTRA_BASE = 100

    /** [extras] are additional (label, action) entries shown above "Server settings". */
    fun show(context: Context, anchor: View, extras: List<Pair<String, () -> Unit>> = emptyList()) {
        val popup = PopupMenu(context, anchor)
        extras.forEachIndexed { i, (label, _) -> popup.menu.add(0, ID_EXTRA_BASE + i, i, label) }
        popup.menu.add(0, ID_SETTINGS, 99, context.getString(R.string.menu_server))
        popup.setOnMenuItemClickListener { item ->
            when {
                item.itemId == ID_SETTINGS -> context.startActivity(Intent(context, SettingsActivity::class.java))
                item.itemId >= ID_EXTRA_BASE -> extras.getOrNull(item.itemId - ID_EXTRA_BASE)?.second?.invoke()
            }
            true
        }
        popup.show()
    }
}
