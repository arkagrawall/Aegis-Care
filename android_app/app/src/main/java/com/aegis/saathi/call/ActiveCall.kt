package com.aegis.saathi.call

/** The Saathi call on screen right now, so the emergency screen can end it before dialling the family. */
object ActiveCall {
    @Volatile var onHangUp: (() -> Unit)? = null

    val isActive: Boolean get() = onHangUp != null

    fun hangUp() {
        onHangUp?.invoke()
        onHangUp = null
    }
}
