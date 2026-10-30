package com.aegis.saathi.call

/** What the call screen is doing right now. Drives the orb animation and the status label. */
enum class Phase { CONNECTING, AI_SPEAKING, LISTENING, THINKING, ENDED }

data class CallUiState(
    val phase: Phase = Phase.CONNECTING,
    /** What the AI is saying / just said. */
    val aiLine: String = "",
    /** What the senior said last (shown small, so they see they were understood). */
    val heardLine: String = "",
    /** Microphone level 0..1 while listening (animates the orb). */
    val level: Float = 0f,
    /** Short status/problem note, e.g. "Mic not working - type below". */
    val note: String = "",
    /** True once the conversation finished normally (server has saved the call). */
    val finishedNormally: Boolean = false,
    /** Voice on the loudspeaker instead of the earpiece. */
    val speakerOn: Boolean = false,
    /** The senior's microphone is muted (Saathi hears silence). */
    val muted: Boolean = false,
    /** Audio is backing up on the way to the server: shown as a gentle "connection is weak" line. */
    val weakNetwork: Boolean = false
)
