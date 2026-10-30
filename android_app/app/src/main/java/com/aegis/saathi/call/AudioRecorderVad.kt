package com.aegis.saathi.call

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.NoiseSuppressor
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/**
 * Records ONE utterance from the microphone and stops by itself.
 *
 * Simple energy-based voice activity detection with an adaptive noise floor:
 *  - waits for speech (needs ~60 ms of sound clearly above the room noise),
 *  - keeps a 300 ms pre-roll so the first syllable is never cut off,
 *  - stops after ~0.7 s of silence for a short answer, ~0.9 s for a long one (or 15 s max),
 *  - gives up if nothing is said within [noSpeechTimeoutMs] (counted only once Saathi has stopped talking).
 *
 * Barge-in: it can run WHILE Saathi is speaking ([audioOut] = true; [isPlaying] = her reply is still on its way,
 * which only pauses the no-speech timeout). Then it needs clearly louder, sustained
 * speech (close to the phone, ~0.3 s) before it counts, so Saathi's own voice leaking back is not mistaken for
 * the senior; when it does count, [onSpeechStart] fires so the caller can stop Saathi mid-sentence.
 * The call-mode microphone (VOICE_COMMUNICATION) applies the phone's echo cancellation for this.
 * Output is 16 kHz mono PCM16 WAV, which is what the server's speech engine expects.
 */
class AudioRecorderVad {

    /** Mute button: frames are replaced by silence, so nothing is heard or sent until un-muted. */
    @Volatile var muted = false

    /** [wav] == null with [micError] == false means "nobody spoke". */
    class Result(val wav: ByteArray?, val micError: Boolean = false)

    companion object {
        const val SAMPLE_RATE = 16000
        private const val FRAME = 320 // 20 ms

        fun pcmToWav(pcm: ByteArray, rate: Int = SAMPLE_RATE): ByteArray {
            val out = ByteArrayOutputStream(44 + pcm.size)
            fun int(v: Int) { out.write(v and 0xFF); out.write((v shr 8) and 0xFF); out.write((v shr 16) and 0xFF); out.write((v shr 24) and 0xFF) }
            fun short(v: Int) { out.write(v and 0xFF); out.write((v shr 8) and 0xFF) }
            out.write("RIFF".toByteArray()); int(36 + pcm.size)
            out.write("WAVE".toByteArray()); out.write("fmt ".toByteArray())
            int(16); short(1); short(1); int(rate); int(rate * 2); short(2); short(16)
            out.write("data".toByteArray()); int(pcm.size)
            out.write(pcm)
            return out.toByteArray()
        }

        private fun rms(buf: ShortArray, n: Int): Double {
            var sum = 0.0
            for (i in 0 until n) sum += buf[i].toDouble() * buf[i]
            return sqrt(sum / max(n, 1))
        }

        private fun write(out: ByteArrayOutputStream, buf: ShortArray, n: Int) {
            for (i in 0 until n) {
                out.write(buf[i].toInt() and 0xFF)
                out.write((buf[i].toInt() shr 8) and 0xFF)
            }
        }
    }

    @SuppressLint("MissingPermission") // RECORD_AUDIO is requested by CallActivity before starting
    suspend fun recordUtterance(
        noSpeechTimeoutMs: Long = 7000,
        maxUtteranceMs: Long = 15000,
        onPcm: ((ByteArray) -> Unit)? = null,
        isPlaying: () -> Boolean = { false },
        audioOut: () -> Boolean = isPlaying,
        speakerOn: () -> Boolean = { false },
        onSpeechStart: () -> Unit = {},
        onLevel: (Float) -> Unit
    ): Result = withContext(Dispatchers.IO) {
        val minBuf = AudioRecord.getMinBufferSize(
            SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT
        )
        if (minBuf <= 0) return@withContext Result(null, micError = true)

        var rec: AudioRecord? = null
        var aec: AcousticEchoCanceler? = null
        var ns: NoiseSuppressor? = null
        try {
            // VOICE_COMMUNICATION = the call microphone, with the phone's echo cancellation (needed to listen while
            // Saathi talks); then the speech-tuned and the plain microphone as fallbacks
            for (source in intArrayOf(MediaRecorder.AudioSource.VOICE_COMMUNICATION, MediaRecorder.AudioSource.VOICE_RECOGNITION, MediaRecorder.AudioSource.MIC)) {
                val r = AudioRecord(source, SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, max(minBuf, FRAME * 2 * 8))
                if (r.state == AudioRecord.STATE_INITIALIZED) { rec = r; break } else r.release()
            }
            if (rec == null) return@withContext Result(null, micError = true)
            if (AcousticEchoCanceler.isAvailable()) aec = try { AcousticEchoCanceler.create(rec.audioSessionId)?.also { it.enabled = true } } catch (_: Exception) { null }
            if (NoiseSuppressor.isAvailable()) ns = try { NoiseSuppressor.create(rec.audioSessionId)?.also { it.enabled = true } } catch (_: Exception) { null }
            rec.startRecording()

            val frame = ShortArray(FRAME)
            val preRoll = ArrayDeque<ShortArray>()
            val pcm = ByteArrayOutputStream()
            val chunk = ByteArrayOutputStream()   // ~100 ms batches for the streaming channel
            var chunkFrames = 0
            var noise = -1.0
            var calibrated = 0
            var speaking = false
            var speechRun = 0
            var silenceMs = 0
            var speechMs = 0
            var quietMs = 0          // time without speech AFTER Saathi stopped talking

            while (currentCoroutineContext().isActive) {
                val n = rec.read(frame, 0, FRAME)
                if (n < 0) return@withContext Result(null, micError = true)
                if (n == 0) continue
                if (muted) java.util.Arrays.fill(frame, 0, n, 0.toShort())
                val replyActive = isPlaying()        // Saathi's reply is playing or still on its way
                val playing = audioOut()              // her voice is coming out right now (echo possible)
                if (!replyActive) quietMs += 20
                val level = rms(frame, n)
                onLevel(min(1f, (level / 3500.0).toFloat()))

                // Measure the room noise in the first ~240 ms
                if (calibrated < 12) {
                    noise = if (noise < 0) level else (noise * calibrated + level) / (calibrated + 1)
                    noise = min(noise, 500.0)
                    calibrated++
                    preRoll.addLast(frame.copyOf(n))
                    continue
                }

                val startThr = max(noise * 3.0, 280.0)
                val keepThr = max(noise * 1.8, 180.0)

                if (!speaking) {
                    preRoll.addLast(frame.copyOf(n))
                    if (preRoll.size > 15) preRoll.removeFirst()
                    val started = if (playing) {
                        // Saathi is talking: only clear, sustained, close-up speech counts (echo stays below this)
                        val bargeThr = max(noise * 4.0, if (speakerOn()) 2400.0 else 1100.0)
                        speechRun = if (level > bargeThr) speechRun + 1 else max(0, speechRun - 1)
                        speechRun >= 14
                    } else {
                        noise = min(noise * 0.95 + level * 0.05, 600.0) // follow slow noise changes
                        speechRun = if (level > startThr) speechRun + 1 else 0
                        speechRun >= 3
                    }
                    if (started) {
                        speaking = true
                        onSpeechStart()
                        preRoll.forEach { write(pcm, it, it.size); if (onPcm != null) write(chunk, it, it.size) }
                        preRoll.clear()
                        if (onPcm != null && chunk.size() > 0) { onPcm(chunk.toByteArray()); chunk.reset(); chunkFrames = 0 }
                        speechMs = 60
                        silenceMs = 0
                    } else if (quietMs > noSpeechTimeoutMs) {
                        return@withContext Result(null)
                    }
                } else {
                    write(pcm, frame, n)
                    if (onPcm != null) {
                        write(chunk, frame, n)
                        if (++chunkFrames >= 5) { onPcm(chunk.toByteArray()); chunk.reset(); chunkFrames = 0 }
                    }
                    speechMs += 20
                    silenceMs = if (level > keepThr) 0 else silenceMs + 20
                    val endSilence = if (speechMs < 2000) 700 else 900
                    if (silenceMs >= endSilence || speechMs >= maxUtteranceMs) break
                }
            }

            if (onPcm != null && chunk.size() > 0) onPcm(chunk.toByteArray())
            if (!speaking || speechMs < 300) Result(null) else Result(pcmToWav(pcm.toByteArray()))
        } catch (e: SecurityException) {
            Result(null, micError = true)
        } catch (e: IllegalStateException) {
            Result(null, micError = true)
        } finally {
            try { aec?.release() } catch (_: Exception) {}
            try { ns?.release() } catch (_: Exception) {}
            try { rec?.stop() } catch (_: Exception) {}
            try { rec?.release() } catch (_: Exception) {}
        }
    }
}
