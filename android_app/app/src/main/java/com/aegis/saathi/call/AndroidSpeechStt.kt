package com.aegis.saathi.call

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.coroutines.resume

/**
 * Fallback speech-to-text using the phone's own recognizer (Google speech service).
 * Used when the server's speech engine is unreachable. Many emulators (e.g. LDPlayer) have
 * no recognition service - [available] tells us.
 */
object AndroidSpeechStt {

    fun available(context: Context): Boolean = SpeechRecognizer.isRecognitionAvailable(context)

    /** Listens once; returns the recognized Hindi text, or null if nothing was understood. */
    suspend fun listenOnce(context: Context): String? = withContext(Dispatchers.Main) {
        withTimeoutOrNull(20_000L) {
            suspendCancellableCoroutine<String?> { cont ->
                val sr = SpeechRecognizer.createSpeechRecognizer(context)
                fun finish(text: String?) {
                    if (cont.isActive) cont.resume(text)
                    try { sr.destroy() } catch (_: Exception) {}
                }
                sr.setRecognitionListener(object : RecognitionListener {
                    override fun onReadyForSpeech(params: Bundle?) {}
                    override fun onBeginningOfSpeech() {}
                    override fun onRmsChanged(rmsdB: Float) {}
                    override fun onBufferReceived(buffer: ByteArray?) {}
                    override fun onEndOfSpeech() {}
                    override fun onError(error: Int) = finish(null)
                    override fun onPartialResults(partialResults: Bundle?) {}
                    override fun onEvent(eventType: Int, params: Bundle?) {}
                    override fun onResults(results: Bundle?) {
                        finish(results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull())
                    }
                })
                val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, "hi-IN")
                    putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
                }
                sr.startListening(intent)
                cont.invokeOnCancellation {
                    try { sr.cancel(); sr.destroy() } catch (_: Exception) {}
                }
            }
        }
    }
}
