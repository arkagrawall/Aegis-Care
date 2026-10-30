package com.aegis.saathi.call

import android.util.Log
import com.aegis.saathi.api.AegisApiClient
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.channels.Channel
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

/**
 * Low-latency turn channel (server: /ws/calls/{id}/audio).
 *
 * While the senior is still talking the phone streams 16 kHz PCM, so the server has the words ready the moment
 * they stop. [begin] then asks for Saathi's reply as a STREAM: each sentence arrives as soon as it is written and
 * voiced ({"type":"say"} + MP3), so she starts speaking before the whole reply exists; a closing turn JSON follows.
 * An older server (or the rule-based agent) answers with one turn JSON + one MP3, which becomes a one-clip reply.
 * Anything going wrong here completes the reply with null and the caller falls back to the plain HTTP turn.
 */
class CallStream(private val callId: String) {

    private val client = OkHttpClient.Builder()
        .pingInterval(15, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .build()

    private class Current {
        val clips = Channel<Clip>(Channel.UNLIMITED)
        val final = CompletableDeferred<CallApi.Turn?>()
    }

    @Volatile private var ws: WebSocket? = null
    @Volatile private var open = CompletableDeferred<Boolean>()
    @Volatile private var current: Current? = null
    @Volatile private var pendingSay: String? = null
    @Volatile private var pendingTurn: CallApi.Turn? = null

    val isOpen: Boolean get() = ws != null && open.isCompleted && !open.isCancelled

    suspend fun connect(): Boolean {
        val url = AegisApiClient.baseUrl.replace("https://", "wss://").replace("http://", "ws://") +
            "/ws/calls/$callId/audio?token=" + URLEncoder.encode(AegisApiClient.deviceKey, "UTF-8")
        open = CompletableDeferred()
        try {
            ws = client.newWebSocket(Request.Builder().url(url).build(), listener)
        } catch (e: Exception) {
            return false
        }
        val ok = withTimeoutOrNull(6000) { open.await() } ?: false
        if (!ok) close()
        return ok
    }

    private val listener = object : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            open.complete(true)
        }

        override fun onMessage(webSocket: WebSocket, text: String) {
            val cur = current ?: return
            try {
                val j = JSONObject(text)
                if (j.optString("type") == "say") {
                    val line = j.optString("text")
                    if (j.optBoolean("has_audio", false)) pendingSay = line else cur.clips.trySend(Clip(line, null, null))
                    return
                }
                val turn = CallApi.parseTurn(j)
                j.optJSONObject("timing_ms")?.let { Log.d("VoiceCall", "turn timing(ms) $it") }
                when {
                    j.optBoolean("streamed", false) -> finish(cur, turn)
                    j.optBoolean("has_audio", false) -> pendingTurn = turn          // its MP3 is the next frame
                    else -> { cur.clips.trySend(Clip(turn.reply, null, turn.audioUrl)); finish(cur, turn) }
                }
            } catch (e: Exception) {
                fail(e)
            }
        }

        override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
            val cur = current ?: return
            pendingSay?.let {
                pendingSay = null
                cur.clips.trySend(Clip(it, bytes.toByteArray(), null))
                return
            }
            pendingTurn?.let {
                pendingTurn = null
                cur.clips.trySend(Clip(it.reply, bytes.toByteArray(), null))
                finish(cur, it)
            }
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            fail(Exception("closed $code"))
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            Log.w("CallStream", "failure: ${t.message}")
            fail(t)
        }
    }

    private fun finish(cur: Current, turn: CallApi.Turn) {
        cur.clips.close()
        cur.final.complete(turn)
    }

    private fun fail(t: Throwable) {
        ws = null
        if (!open.isCompleted) open.complete(false)
        current?.let { it.clips.close(); it.final.complete(null) }
    }

    /** One chunk of 16 kHz mono PCM16 (about 100 ms). */
    fun sendPcm(pcm: ByteArray) {
        try { ws?.send(pcm.toByteString()) } catch (_: Exception) {}
    }

    /** Forget a half-recorded utterance (the senior typed instead). */
    fun reset() {
        try { ws?.send("""{"type":"reset"}""") } catch (_: Exception) {}
    }

    /** The senior stopped talking: Saathi's reply starts streaming back; null if the channel is gone. */
    fun begin(silence: Boolean): SpokenReply? {
        val socket = ws ?: return null
        val cur = Current()
        current = cur
        pendingSay = null
        pendingTurn = null
        val msg = JSONObject().put("type", "end").put("silence", silence).put("stream", true).toString()
        if (!socket.send(msg)) return null
        return SpokenReply(cur.clips, cur.final)
    }

    fun close() {
        try { ws?.close(1000, "done") } catch (_: Exception) {}
        ws = null
    }
}
