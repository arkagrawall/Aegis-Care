package com.aegis.saathi.call

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.ReceiveChannel

/** One sentence of Saathi's reply: its text and its voice (MP3 bytes, or a URL to fetch, or neither = phone voice). */
class Clip(val text: String, val audio: ByteArray?, val url: String?)

/**
 * Saathi's reply as it is spoken: sentence clips arrive one by one ([clips], closed when the reply is complete),
 * and [final] carries the turn's outcome (heard text, call finished, emergency) once the server has sent it.
 * A whole reply (HTTP, rule-based agent) is simply one clip.
 */
class SpokenReply(val clips: ReceiveChannel<Clip>, val final: Deferred<CallApi.Turn?>) {
    companion object {
        fun of(turn: CallApi.Turn): SpokenReply {
            val ch = Channel<Clip>(Channel.UNLIMITED)
            ch.trySend(Clip(turn.reply, turn.audio, turn.audioUrl))
            ch.close()
            return SpokenReply(ch, CompletableDeferred(turn))
        }
    }
}
