package com.aegis.saathi.call

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** The call notification's buttons that don't open a screen: Decline (ringing) and Hang up (during the call). */
class CallActionReceiver : BroadcastReceiver() {

    companion object {
        const val ACTION_DECLINE = "com.aegis.saathi.call.DECLINE"
        const val ACTION_HANG_UP = "com.aegis.saathi.call.HANG_UP"
        const val EXTRA_CALL_ID = "CALL_ID"
    }

    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            ACTION_DECLINE -> IncomingCalls.declined(context, intent.getStringExtra(EXTRA_CALL_ID).orEmpty())
            ACTION_HANG_UP -> ActiveCall.hangUp()
        }
    }
}
