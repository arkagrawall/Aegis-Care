package com.aegis.saathi.ui

import android.content.Intent
import android.content.res.ColorStateList
import android.net.Uri
import android.view.LayoutInflater
import android.view.View
import com.aegis.saathi.A11yPrefs
import com.aegis.saathi.R
import com.aegis.saathi.databinding.ItemContactBinding
import com.aegis.saathi.databinding.PageFamilyBinding
import com.aegis.saathi.meds.CareRepo

/** The Family tab: the care manager first, then family and friends, one tap to call each. */
class FamilyTab(private val act: MainActivity, private val b: PageFamilyBinding) {

    // soft avatar colours so faces are easy to tell apart (background, text)
    private val tints = listOf(0xFFDDF2EC to 0xFF0A5C50, 0xFFFBF0D9 to 0xFF8A5A12, 0xFFE4E9FB to 0xFF2F4FA8,
                               0xFFFBE4E1 to 0xFF9A2B22, 0xFFEDE4F8 to 0xFF5B3C8C)

    init {
        b.rowFamilySharing.pressable(0.98f)
        b.rowFamilySharing.setOnClickListener { act.showFamilyDialog() }
    }

    fun render(st: CareRepo.ContactsState, sharingOn: Boolean) {
        val inflater = LayoutInflater.from(act)
        b.contactsList.removeAllViews()
        if (st.careName.isNotEmpty()) {
            addRow(inflater, st.careName, act.getString(R.string.family_care_manager), st.carePhone, 0)
        }
        st.contacts.forEachIndexed { i, c ->
            if (c.id == "emergency") {
                // the number given at registration, before any family were added: show it in the senior's language
                addRow(inflater, act.getString(R.string.family_emergency), c.phone, c.phone, i + 1)
                return@forEachIndexed
            }
            val relation = listOf(c.relation, if (c.isEmergency) act.getString(R.string.family_emergency) else "")
                .filter { it.isNotEmpty() }.joinToString(" · ")
            addRow(inflater, c.name.ifEmpty { c.relation }, relation, c.phone, i + 1)
        }
        b.contactsEmpty.root.visibility = if (st.loaded && st.contacts.isEmpty()) View.VISIBLE else View.GONE
        b.contactsEmpty.ivEmpty.setImageResource(R.drawable.ill_contacts_empty)
        b.contactsEmpty.tvEmptyTitle.setText(R.string.family_empty_title)
        b.contactsEmpty.tvEmptyBody.setText(R.string.family_none_yet)
        b.tvFamilyShareState.text = act.getString(if (sharingOn) R.string.family_share_on else R.string.family_share_off)
        A11yPrefs.applyContrast(b.root)
    }

    private fun addRow(inflater: LayoutInflater, name: String, relation: String, phone: String, i: Int) {
        val row = ItemContactBinding.inflate(inflater, b.contactsList, false)
        val (bg, fg) = tints[i % tints.size]
        row.tvAvatar.text = name.trim().split(Regex("\\s+")).take(2).mapNotNull { it.firstOrNull()?.uppercase() }.joinToString("")
        row.tvAvatar.backgroundTintList = ColorStateList.valueOf(bg.toInt())
        row.tvAvatar.setTextColor(fg.toInt())
        row.tvContactName.text = name
        row.tvContactRelation.text = relation
        row.tvContactRelation.visibility = if (relation.isEmpty()) View.GONE else View.VISIBLE
        row.btnContactCall.visibility = if (phone.isBlank()) View.GONE else View.VISIBLE
        row.btnContactCall.contentDescription = act.getString(R.string.family_call_who, name)
        row.btnContactCall.pressable()
        row.btnContactCall.setOnClickListener {
            A11yPrefs.tap(it)
            dial(phone)
        }
        b.contactsList.addView(row.root)
    }

    /** Opens the phone's dialer with the number filled in; no call permission needed. */
    fun dial(phone: String) {
        act.startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + phone.filter { it.isDigit() || it == '+' })))
    }
}
