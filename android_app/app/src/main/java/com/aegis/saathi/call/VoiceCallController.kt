package com.aegis.saathi.call

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import com.aegis.saathi.LocaleManager
import com.aegis.saathi.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.selects.select
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Runs the hands-free AI phone call like a real phone conversation:
 *
 *   start -> [ Saathi speaks WHILE the mic listens -> senior talks (even over her) -> reply ] x N -> end
 *
 * Her reply arrives as a stream of sentences (see CallStream / SpokenReply): the first plays as soon as it exists.
 *
 * The microphone is open the whole time, also while Saathi is talking. If the senior starts speaking,
 * Saathi stops mid-sentence and listens ("barge-in"), so they can bring up what matters to them instead
 * of waiting for their turn. Audio goes to the earpiece like a normal call (speaker on request, see CallAudio).
 * Typing ([submitTyped]) is only a fallback for noisy rooms or a broken microphone.
 */
class VoiceCallController(
    context: Context,
    private val callId: String,
    private val micEnabled: Boolean
) {
    private val appContext = context.applicationContext
    private val _state = MutableStateFlow(CallUiState())
    val state: StateFlow<CallUiState> = _state.asStateFlow()

    private val recorder = AudioRecorderVad()
    private val player = SpeechPlayer(appContext)
    private val audio = CallAudio(appContext)
    private val main = Handler(Looper.getMainLooper())
    private val typed = Channel<String>(Channel.CONFLATED)

    @Volatile private var replyActive = false   // her reply is playing or still arriving
    @Volatile private var audioOut = false      // her voice is coming out of the speaker right now
    @Volatile private var bargedIn = false
    private var lastWav: ByteArray? = null      // the senior's last utterance, kept to resend if the stream breaks
    @Volatile private var turnStream: CallStream? = null   // the channel this utterance is being streamed on

    private var job: Job? = null
    @Volatile private var live: SarvamLiveCall? = null
    private var serverFailures = 0
    private var useDeviceStt = false
    private var micBroken = !micEnabled
    private var streamLink: Deferred<CallStream?>? = null
    private var stream: CallStream? = null

    /** Starts the conversation loop on [scope] (use the activity's lifecycleScope = main thread). */
    fun start(scope: CoroutineScope) {
        job = scope.launch {
            audio.start()
            try {
                runCall()
            } finally {
                stream?.close()
                player.release()
                audio.stop()
            }
        }
    }

    /** Earpiece (default, like a phone call) or loudspeaker. */
    fun setSpeaker(on: Boolean) {
        audio.setSpeaker(on)
        _state.update { it.copy(speakerOn = on) }
    }

    /** Mute: Saathi hears silence until un-muted, on either engine. */
    fun setMute(on: Boolean) {
        recorder.muted = on
        live?.muted = on
        _state.update { it.copy(muted = on) }
    }

    fun submitTyped(text: String) {
        if (text.isNotBlank()) typed.trySend(text.trim())
    }

    /** Hang up from the UI. Saves what was said so far on the server. */
    fun hangUp() {
        job?.cancel()
        player.stop()
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch { CallApi.end(callId) }
    }

    // ------------------------------------------------------------------------------------ loop
    private sealed class Outcome {
        object Retry : Outcome()
        object Ended : Outcome()
        class Next(val reply: SpokenReply) : Outcome()
    }

    private suspend fun runCall() {
        set(Phase.CONNECTING, note = "")
        var first = CallApi.start(callId).getOrNull()
        if (first != null && first.engine == "sarvam") {
            // the hub runs this call on a Sarvam voice agent: one full-duplex stream until it ends
            val call = SarvamLiveCall(callId, onWeakNetwork = { w -> _state.update { it.copy(weakNetwork = w) } }) { phase, ai, heard, level ->
                _state.update { s ->
                    s.copy(phase = phase, aiLine = ai ?: s.aiLine, heardLine = heard ?: s.heardLine, level = level, note = "")
                }
            }
            call.muted = _state.value.muted
            live = call
            val result = try { call.run() } finally { live = null }
            when (result) {
                SarvamLiveCall.Result.ENDED -> {
                    _state.update { it.copy(phase = Phase.ENDED, finishedNormally = true, note = "", level = 0f) }
                    return
                }
                // Sarvam could not be reached: this call continues on the hub's own voice
                else -> first = CallApi.start(callId, "local").getOrNull()
            }
        }
        if (first == null) {
            _state.update { it.copy(phase = Phase.ENDED, note = LocaleManager.string(appContext, R.string.call_err_server)) }
            return
        }

        // Open the low-latency audio channel while the greeting plays
        val link = CoroutineScope(SupervisorJob() + Dispatchers.IO).async {
            CallStream(callId).let { if (it.connect()) it else null }
        }
        streamLink = link
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch { stream = link.await() }
        var reply = SpokenReply.of(first)
        var speakFirst = true
        var failures = 0
        while (true) {
            when (val r = talk(reply, speakFirst)) {
                Outcome.Ended -> break
                is Outcome.Next -> { failures = 0; reply = r.reply; speakFirst = true }
                Outcome.Retry -> {
                    failures++
                    if (failures >= 4) {
                        CallApi.end(callId)
                        _state.update { it.copy(phase = Phase.ENDED, note = LocaleManager.string(appContext, R.string.call_err_net)) }
                        return
                    }
                    speakFirst = false // transient problem: just listen again
                }
            }
        }
        _state.update { it.copy(phase = Phase.ENDED, finishedNormally = true, note = "", level = 0f) }
    }

    /**
     * Plays Saathi's reply sentence by sentence as the clips arrive; returns the turn's outcome (null = it never
     * completed). Stops speaking at once when the senior barges in (remaining clips are skipped).
     */
    private suspend fun play(reply: SpokenReply): CallApi.Turn? = withTimeoutOrNull(45_000L) {
        val said = StringBuilder()
        _state.update { it.copy(phase = Phase.THINKING, level = 0f, note = "") }
        for (clip in reply.clips) {
            if (bargedIn) continue
            if (said.isNotEmpty()) said.append(' ')
            said.append(clip.text)
            _state.update { it.copy(phase = Phase.AI_SPEAKING, aiLine = said.toString(), level = 0f) }
            audioOut = true
            try {
                if (clip.audio != null) player.speakBytes(clip.text, clip.audio) else player.speak(clip.text, clip.url)
            } finally {
                audioOut = false
            }
        }
        val turn = reply.final.await()
        if (turn == null && said.isEmpty() && !bargedIn) {
            // the stream broke before she said anything: ask again over plain HTTP so their words are not lost
            stream?.close(); stream = null; streamLink = null
            val again = lastWav?.let { sendAudio(it) } ?: sendSilence()
            return@withTimeoutOrNull again?.let { play(it) }
        }
        turn?.let { afterTurn(it) }
    }

    /**
     * Saathi says [reply] (unless [speakFirst] is false) while the microphone already listens; returns what happens
     * next. If the senior talks over her, she stops and their words are taken as the answer.
     */
    private suspend fun talk(reply: SpokenReply, speakFirst: Boolean): Outcome {
        if (useDeviceStt || micBroken) {
            if (speakFirst) {
                replyActive = true
                val t = try { play(reply) } finally { replyActive = false }
                if (t?.isCompleted == true) return Outcome.Ended
            }
            if (useDeviceStt && !micBroken) {
                _state.update { it.copy(phase = Phase.LISTENING, level = 0f) }
                return wrap(listenWithDeviceStt())
            }
            _state.update { it.copy(phase = Phase.LISTENING, level = 0f, note = LocaleManager.string(appContext, R.string.call_note_mic)) }
            val text = withTimeoutOrNull(15_000L) { typed.receive() }
            return wrap(if (text == null) sendSilence() else sendText(text))
        }

        bargedIn = false
        turnStream = null
        return coroutineScope {
            replyActive = speakFirst
            val recJob = async {
                recorder.recordUtterance(
                    onPcm = { b -> turnStream?.sendPcm(b) },
                    isPlaying = { replyActive },
                    audioOut = { audioOut },
                    speakerOn = { audio.speakerOn },
                    onSpeechStart = {
                        turnStream = stream?.takeIf { it.isOpen }
                        if (replyActive) {
                            bargedIn = true                     // the senior has the floor
                            main.post { player.interrupt() }   // Saathi stops mid-sentence (or never starts)
                        }
                        _state.update { it.copy(phase = Phase.LISTENING) }
                    }
                ) { lvl -> if (!audioOut) _state.update { it.copy(level = lvl) } }
            }
            val typedJob = async { typed.receive() }
            // a typed answer during her sentence also cuts it short
            val typedCut = launch { typedJob.await(); if (replyActive) { bargedIn = true; player.interrupt() } }

            if (speakFirst) {
                val turn = try { play(reply) } finally { replyActive = false; audioOut = false }
                if (turn?.isCompleted == true) {             // goodbye or escalation: the call is over
                    recJob.cancel(); typedJob.cancel(); typedCut.cancel()
                    return@coroutineScope Outcome.Ended
                }
            }
            if (!bargedIn) _state.update { it.copy(phase = Phase.LISTENING, level = 0f) }

            val first: Any = select {
                recJob.onAwait { it }
                typedJob.onAwait { it }
            }
            recJob.cancel()
            typedJob.cancel()
            typedCut.cancel()

            val st = turnStream
            val next: SpokenReply? = if (first is String) {
                st?.reset()
                sendText(first)
            } else if (first is AudioRecorderVad.Result) {
                val wav = first.wav
                lastWav = wav
                when {
                    first.micError -> { micBroken = true; null }
                    st != null && st.isOpen -> streamedTurn(st, first)
                    wav == null -> sendSilence()
                    else -> sendAudio(wav)          // the stream was not ready when they started: send the whole recording
                }
            } else {
                null
            }
            wrap(next)
        }
    }

    private fun wrap(r: SpokenReply?): Outcome = if (r == null) Outcome.Retry else Outcome.Next(r)

    /** Words were recognised while the senior spoke: ask for her reply as a stream of spoken sentences. */
    private suspend fun streamedTurn(st: CallStream, rec: AudioRecorderVad.Result): SpokenReply? {
        _state.update { it.copy(phase = Phase.THINKING, level = 0f) }
        val r = st.begin(silence = rec.wav == null)
        if (r != null) {
            serverFailures = 0
            return r
        }
        // channel broke: drop it and use the plain HTTP turn so the call carries on
        stream?.close()
        stream = null
        streamLink = null
        return if (rec.wav == null) sendSilence() else sendAudio(rec.wav)
    }

    private suspend fun listenWithDeviceStt(): SpokenReply? {
        val text = AndroidSpeechStt.listenOnce(appContext)
        return if (text.isNullOrBlank()) sendSilence() else sendText(text)
    }

    // ------------------------------------------------------------------------------- server I/O
    private suspend fun sendAudio(wav: ByteArray): SpokenReply? {
        _state.update { it.copy(phase = Phase.THINKING, level = 0f) }
        val r = CallApi.sendAudio(callId, wav)
        val turn = r.getOrNull()
        if (turn == null) {
            // Speech engine unreachable/not ready: after 2 failures switch to the phone's own recognizer
            serverFailures++
            if (serverFailures >= 2 && AndroidSpeechStt.available(appContext)) useDeviceStt = true
            _state.update { it.copy(note = LocaleManager.string(appContext, R.string.call_note_unclear)) }
            return null
        }
        serverFailures = 0
        return SpokenReply.of(afterTurn(turn))
    }

    private suspend fun sendText(text: String): SpokenReply? {
        _state.update { it.copy(phase = Phase.THINKING, level = 0f, heardLine = text) }
        return CallApi.sendText(callId, text).getOrNull()?.let { SpokenReply.of(afterTurn(it)) }
    }

    private suspend fun sendSilence(): SpokenReply? {
        _state.update { it.copy(phase = Phase.THINKING, level = 0f) }
        return CallApi.sendText(callId, "", silence = true).getOrNull()?.let { SpokenReply.of(afterTurn(it)) }
    }

    private fun afterTurn(turn: CallApi.Turn): CallApi.Turn {
        if (turn.heard.isNotBlank()) _state.update { it.copy(heardLine = turn.heard) }
        return turn
    }

    private fun set(phase: Phase, note: String) {
        _state.update { it.copy(phase = phase, note = note) }
    }
}
