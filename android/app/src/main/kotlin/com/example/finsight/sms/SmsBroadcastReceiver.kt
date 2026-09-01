package com.example.finsight.sms

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.telephony.SmsMessage
import android.util.Log
import io.flutter.plugin.common.EventChannel

class SmsBroadcastReceiver() : BroadcastReceiver() {

    companion object {
        const val TAG = "SmsBroadcastReceiver"
        var sharedEventSink: EventChannel.EventSink? = null
    }

    override fun onReceive(context: Context?, intent: Intent?) {
        if (intent?.action != "android.provider.Telephony.SMS_RECEIVED") return

        val bundle = intent.extras ?: return
        val pdus = bundle.get("pdus") as? Array<*> ?: return
        val format = bundle.getString("format") ?: "3gpp"

        val messages = pdus.mapNotNull { pdu ->
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    SmsMessage.createFromPdu(pdu as ByteArray, format)
                } else {
                    @Suppress("DEPRECATION")
                    SmsMessage.createFromPdu(pdu as ByteArray)
                }
            } catch (e: Exception) {
                Log.e(TAG, "PDU parse error: ${e.message}")
                null
            }
        }

        if (messages.isEmpty()) return

        val sender = messages.first().originatingAddress ?: "Unknown"
        val body = messages.joinToString("") { it.messageBody ?: "" }
        val timestamp = messages.first().timestampMillis

        Log.i(TAG, "Incoming SMS from $sender: ${body.take(80)}...")

        val smsData = mapOf(
            "id" to timestamp,
            "address" to sender,
            "body" to body,
            "timestamp" to timestamp,
            "type" to 1,
            "source" to "broadcast"
        )

        android.os.Handler(android.os.Looper.getMainLooper()).post {
            try {
                sharedEventSink?.success(smsData)
            } catch (e: Exception) {
                Log.e(TAG, "EventSink error: ${e.message}")
            }
        }
    }
}
