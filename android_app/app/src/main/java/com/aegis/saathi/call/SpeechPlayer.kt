package com.aegis.saathi.call

import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import java.util.Locale
import kotlin.coroutines.resume

/**
 * Speaks the AI's reply and suspends until it has finished, or until [interrupt] is called because the senior
 * started talking over it. Plays on the call channel (earpiece / headset; see CallAudio), not as media.
 * Primary: natural Hindi neural voice streamed from the server (Edge-TTS).
 * Fallback: the phone's own TextToSpeech (hi-IN) if the server audio fails.
 * Call from the main thread (MediaPlayer/TextToSpeech callbacks need a Looper).
 */
class SpeechPlayer(private val context: Context, callChannel: Boolean = true) {

    private var player: MediaPlayer? = null
    private var playing: kotlinx.coroutines.CancellableContinuation<Boolean>? = null

    // in a call: the call channel (earpiece / headset); elsewhere (home screen): the loudspeaker
    private val callAttributes: AudioAttributes = AudioAttributes.Builder()
        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
        .setUsage(if (callChannel) AudioAttributes.USAGE_VOICE_COMMUNICATION else AudioAttributes.USAGE_MEDIA)
        .build()

    /** The senior began to speak: stop at once and let [speak] return (true = it was cut short, not failed). */
    fun interrupt() {
        val c = playing
        playing = null
        try { tts?.stop() } catch (_: Exception) {}
        stop()
        if (c != null && c.isActive) c.resume(true)
    }
    private var tts: TextToSpeech? = null
    private var ttsReady = false

    /** @return true if something was spoken (either voice), false if both failed. */
    suspend fun speak(text: String, audioUrl: String?): Boolean {
        val url = if (audioUrl != null) CallApi.absolute(audioUrl) else CallApi.ttsUrl(text)
        if (playUrl(url)) return true
        return speakLocal(text)
    }

    /** Reads any text aloud in Saathi's voice for the chosen language (cards, reminders). */
    suspend fun say(text: String, english: Boolean): Boolean {
        if (playUrl(CallApi.ttsUrl(text, english))) return true
        return speakLocal(text)
    }

    /** Plays MP3 bytes that arrived with the reply (no network fetch), falling back to the phone's voice. */
    suspend fun speakBytes(text: String, audio: ByteArray): Boolean {
        val f = java.io.File.createTempFile("aegis_tts", ".mp3", context.cacheDir)
        try {
            f.writeBytes(audio)
            if (playUrl(f.absolutePath)) return true
        } catch (_: Exception) {
        } finally {
            f.delete()
        }
        return speakLocal(text)
    }

    private suspend fun playUrl(url: String): Boolean {
        val ok = withTimeoutOrNull(60_000L) {
            suspendCancellableCoroutine<Boolean> { cont ->
                val p = MediaPlayer()
                player = p
                playing = cont
                try {
                    p.setAudioAttributes(callAttributes)
                    p.setDataSource(url)
                    p.setOnPreparedListener { it.start() }
                    p.setOnCompletionListener { if (cont.isActive) cont.resume(true) }
                    p.setOnErrorListener { _, _, _ -> if (cont.isActive) cont.resume(false); true }
                    p.prepareAsync()
                } catch (e: Exception) {
                    if (cont.isActive) cont.resume(false)
                }
                cont.invokeOnCancellation { stop() }
            }
        } ?: false
        stop()
        return ok
    }

    private suspend fun speakLocal(text: String): Boolean =
        withTimeoutOrNull(60_000L) {
            suspendCancellableCoroutine<Boolean> { cont ->
                playing = cont
                fun go(engine: TextToSpeech) {
                    engine.setAudioAttributes(callAttributes)
                    engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                        override fun onStart(utteranceId: String?) {}
                        override fun onDone(utteranceId: String?) { if (cont.isActive) cont.resume(true) }
                        @Deprecated("Deprecated in Java")
                        override fun onError(utteranceId: String?) { if (cont.isActive) cont.resume(false) }
                    })
                    val r = engine.speak(text, TextToSpeech.QUEUE_FLUSH, null, "aegis_utt")
                    if (r != TextToSpeech.SUCCESS && cont.isActive) cont.resume(false)
                }

                val existing = tts
                if (existing != null && ttsReady) {
                    go(existing)
                } else {
                    tts = TextToSpeech(context) { status ->
                        val engine = tts
                        if (status == TextToSpeech.SUCCESS && engine != null) {
                            engine.language = Locale("hi", "IN")
                            ttsReady = true
                            go(engine)
                        } else if (cont.isActive) {
                            cont.resume(false)
                        }
                    }
                }
                cont.invokeOnCancellation { tts?.stop() }
            }
        } ?: false

    fun stop() {
        try { player?.stop() } catch (_: Exception) {}
        try { player?.release() } catch (_: Exception) {}
        player = null
    }

    fun release() {
        stop()
        try { tts?.stop(); tts?.shutdown() } catch (_: Exception) {}
        tts = null
        ttsReady = false
    }
}
