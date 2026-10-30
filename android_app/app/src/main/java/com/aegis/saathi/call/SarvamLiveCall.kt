package com.aegis.saathi.call

import android.annotation.SuppressLint
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.NoiseSuppressor
import android.util.Log
import com.aegis.saathi.api.AegisApiClient
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import java.net.URLEncoder
import java.util.concurrent.TimeUnit
import kotlin.coroutines.coroutineContext
import kotlin.math.max
import kotlin.math.sqrt

/**
 * The Saathi call when the hub runs it on a Sarvam voice agent (server: /ws/calls/{id}/live).
 *
 * Full duplex like a real phone call: the microphone streams 16 kHz PCM the whole time and Saathi's voice
 * streams back as PCM. Sarvam decides when the senior has finished and handles barge-in; on
 * {"type":"interrupt"} playback stops at once. Captions keep the screen in step with what is said.
 * The API key never reaches the phone.
 */
class SarvamLiveCall(
    private val callId: String,
    private val onWeakNetwork: (Boolean) -> Unit = {},
    private val onState: (phase: Phase, aiLine: String?, heardLine: String?, level: Float) -> Unit
) {
    /** Mute: the microphone keeps running (so un-muting is instant) but only silence is sent. */
    @Volatile var muted = false
    enum class Result { ENDED, FALLBACK, FAILED }

    private val client = OkHttpClient.Builder()
        .pingInterval(15, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .build()

    private val done = CompletableDeferred<Result>()
    private val opened = CompletableDeferred<Boolean>()
    private val playback = Channel<ByteArray>(Channel.UNLIMITED)
    @Volatile private var ws: WebSocket? = null
    @Volatile private var track: AudioTrack? = null
    @Volatile private var outRate = 16000
    @Volatile private var speakingUntil = 0L
    @Volatile private var started = false

    /** Runs the call until it ends; returns how it ended. Cancelling the caller hangs up. */
    suspend fun run(): Result = withContext(Dispatchers.IO) {
        val url = AegisApiClient.baseUrl.replace("https://", "wss://").replace("http://", "ws://") +
            "/ws/calls/$callId/live?token=" + URLEncoder.encode(AegisApiClient.deviceKey, "UTF-8")
        ws = client.newWebSocket(Request.Builder().url(url).build(), listener)
        if (withTimeoutOrNull(8000) { opened.await() } != true) {
            close()
            return@withContext Result.FAILED
        }
        val scope = CoroutineScope(coroutineContext + Job())
        val mic = scope.launch { micLoop() }
        val speaker = scope.launch { playLoop() }
        try {
            done.await()
        } finally {
            mic.cancel(); speaker.cancel()
            try { ws?.send(JSONObject().put("type", "hangup").toString()) } catch (_: Exception) {}
            close()
        }
    }

    private fun close() {
        try { ws?.close(1000, "bye") } catch (_: Exception) {}
        ws = null
        try { track?.stop(); track?.release() } catch (_: Exception) {}
        track = null
        playback.close()
    }

    // ------------------------------------------------------------------ microphone -> hub
    @SuppressLint("MissingPermission")    // RECORD_AUDIO is granted during setup; the call screen checks it too
    private suspend fun micLoop() {
        val frame = 320                     // 20 ms at 16 kHz
        val minBuf = AudioRecord.getMinBufferSize(16000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val rec = AudioRecord(MediaRecorder.AudioSource.VOICE_COMMUNICATION, 16000, AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT, max(minBuf, frame * 2 * 8))
        val aec = if (AcousticEchoCanceler.isAvailable()) try { AcousticEchoCanceler.create(rec.audioSessionId)?.also { it.enabled = true } } catch (_: Exception) { null } else null
        val ns = if (NoiseSuppressor.isAvailable()) try { NoiseSuppressor.create(rec.audioSessionId)?.also { it.enabled = true } } catch (_: Exception) { null } else null
        val buf = ShortArray(frame)
        val bytes = ByteArray(frame * 2)
        try {
            rec.startRecording()
            while (coroutineContext.isActive) {
                val n = rec.read(buf, 0, frame)
                if (n <= 0) continue
                var sum = 0.0
                val mute = muted
                for (i in 0 until n) {
                    val v = if (mute) 0 else buf[i].toInt()
                    bytes[2 * i] = (v and 0xff).toByte()
                    bytes[2 * i + 1] = ((v shr 8) and 0xff).toByte()
                    sum += v.toDouble() * v
                }
                val socket = ws
                socket?.send(bytes.toByteString(0, n * 2))
                // more than ~1.5 s of our audio still waiting to go out: the connection is struggling
                val backlog = (socket?.queueSize() ?: 0L) > 48_000L
                if (backlog != weak) { weak = backlog; onWeakNetwork(backlog) }
                val level = (sqrt(sum / n) / 6000.0).coerceIn(0.0, 1.0).toFloat()
                if (started) {
                    val talking = System.currentTimeMillis() < speakingUntil
                    onState(if (talking) Phase.AI_SPEAKING else Phase.LISTENING, null, null, if (talking) 0f else level)
                }
            }
        } finally {
            try { rec.stop() } catch (_: Exception) {}
            rec.release(); aec?.release(); ns?.release()
        }
    }

    // ------------------------------------------------------------------ hub -> earpiece
    @Volatile private var weak = false
    @Volatile private var playing = false       // the track has been started for the current sentence
    @Volatile private var queuedBytes = 0L      // written since the last (re)start, before play()

    /**
     * About half a second of room, started paused. Speech arrives over the internet in uneven bursts; starting
     * playback only once ~200 ms is queued (see [playLoop]) keeps Saathi's voice smooth instead of choppy,
     * for a delay a listener does not notice.
     */
    private fun newTrack(rate: Int): AudioTrack {
        val min = AudioTrack.getMinBufferSize(rate, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
        return AudioTrack.Builder()
            .setAudioAttributes(AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
            .setAudioFormat(AudioFormat.Builder().setSampleRate(rate)
                .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                .setEncoding(AudioFormat.ENCODING_PCM_16BIT).build())
            .setBufferSizeInBytes(max(min, rate))          // 16-bit mono: rate bytes = 500 ms
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()
            .also { playing = false; queuedBytes = 0 }
    }

    private suspend fun playLoop() {
        while (coroutineContext.isActive) {
            // wait briefly for audio; if nothing more comes, start whatever short sentence is queued
            val r = withTimeoutOrNull(150) { playback.receiveCatching() }
            if (r == null) {
                startIfQueued(force = true)
                continue
            }
            val chunk = r.getOrNull() ?: break           // channel closed: the call is over
            val t = track ?: newTrack(outRate).also { track = it }
            val ms = chunk.size * 1000L / (2L * outRate)
            speakingUntil = max(speakingUntil, System.currentTimeMillis()) + ms
            t.write(chunk, 0, chunk.size)
            queuedBytes += chunk.size
            startIfQueued(force = false)
        }
    }

    private fun startIfQueued(force: Boolean) {
        val t = track ?: return
        if (playing || queuedBytes == 0L) return
        if (force || queuedBytes >= outRate * 2L / 5) {   // >= 200 ms
            try { t.play(); playing = true } catch (_: Exception) {}
        }
    }

    private fun interrupt() {
        // the senior started talking: drop what is queued and what the track still holds
        while (playback.tryReceive().isSuccess) { /* drain */ }
        track?.let { try { it.pause(); it.flush() } catch (_: Exception) {} }
        playing = false
        queuedBytes = 0
        speakingUntil = 0L
    }

    // ------------------------------------------------------------------ socket
    private val listener = object : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            opened.complete(true)
        }

        override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
            started = true
            playback.trySend(bytes.toByteArray())
        }

        override fun onMessage(webSocket: WebSocket, text: String) {
            val j = try { JSONObject(text) } catch (_: Exception) { return }
            when (j.optString("type")) {
                "audio_format" -> {
                    val rate = j.optInt("sample_rate", 16000)
                    if (rate != outRate) {
                        outRate = rate
                        track?.let { try { it.stop(); it.release() } catch (_: Exception) {} }
                        track = null
                    }
                }
                "caption" -> {
                    started = true
                    val text = j.optString("text")
                    if (j.optString("speaker") == "senior") onState(Phase.THINKING, null, text, 0f)
                    else onState(Phase.AI_SPEAKING, text, null, 0f)
                }
                "interrupt" -> interrupt()
                "fallback" -> done.complete(Result.FALLBACK)
                "end" -> done.complete(Result.ENDED)
            }
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            opened.complete(false)
            done.complete(Result.ENDED)
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            Log.w("SarvamLiveCall", "socket failed: ${t.message}")
            opened.complete(false)
            done.complete(if (started) Result.ENDED else Result.FAILED)
        }
    }
}
