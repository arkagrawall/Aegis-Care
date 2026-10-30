package com.aegis.saathi.call

import android.app.NotificationManager
import android.content.Context
import com.aegis.saathi.service.CallListenerService
import org.json.JSONObject

/**
 * The three ways a ringing call can end, wherever they happen (the ringing screen, the notification's buttons, the
 * 30 s timeout): stop the ringer, clear the call notification and tell the hub. Each call ID is reported once.
 */
object IncomingCalls {
    const val NOTIF_ID = 2002
    private var reported = ""

    /** The ringing screen, if open: closed whenever the call stops ringing, however that happened. */
    @Volatile var onRingingOver: (() -> Unit)? = null

    fun accepted(context: Context, callId: String) = finish(context, callId, "CALL_ACCEPTED")
    fun declined(context: Context, callId: String) = finish(context, callId, "CALL_DECLINED")
    fun missed(context: Context, callId: String) = finish(context, callId, "CALL_MISSED")

    @Synchronized
    private fun finish(context: Context, callId: String, event: String) {
        Ringer.stop()
        try {
            (context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).cancel(NOTIF_ID)
        } catch (_: Exception) {}
        onRingingOver?.invoke()
        if (callId.isEmpty() || callId == reported) return
        reported = callId
        CallListenerService.sendSocketEvent(JSONObject().put("event", event).put("call_id", callId))
    }
}
