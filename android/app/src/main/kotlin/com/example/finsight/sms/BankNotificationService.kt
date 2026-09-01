package com.example.finsight.sms

import android.app.Notification
import android.content.Intent
import android.os.Bundle
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import io.flutter.plugin.common.EventChannel

class BankNotificationService : NotificationListenerService() {

    companion object {
        const val TAG = "BankNotificationSvc"

        val BANK_PACKAGES = setOf(
            "net.one97.paytm",
            "com.phonepe.app",
            "com.google.android.apps.nbu.paisa.user",
            "in.amazon.mShop.android.shopping",
            "com.mobikwik_new",
            "com.freecharge.android",
            "com.dreamplug.androidapp",
            "com.sbi.SBIFreedomPlus",
            "com.sbi.lotusintouch",
            "com.unionbank.eunion",
            "com.pnb.mPassbook",
            "com.bankofbaroda.mpassbook",
            "com.canara.canaraMobile",
            "com.csam.icici.bank.imobile",
            "com.hdfc.hdfcbank",
            "net.fptech.axisbank",
            "com.kotak.mahindra.kotak811",
            "com.idbi.mPassBook",
            "com.indusind.ibmobile",
            "com.rbl.rblmobilebanking",
            "com.android.messaging",
            "com.google.android.apps.messaging",
            "com.samsung.android.messaging",
            "com.miui.sms",
            "com.coloros.message",
        )

        val BANK_KEYWORDS = listOf(
            "debited", "credited", "debit", "credit",
            "rs.", "rs ", "inr", "₹",
            "spent", "paid", "withdrawn", "txn", "upi",
            "a/c", "acct", "balance", "neft", "imps", "atm",
        )

        var notificationEventSink: EventChannel.EventSink? = null
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        sbn ?: return

        val pkg = sbn.packageName ?: return
        val notification = sbn.notification ?: return
        val extras = notification.extras ?: return

        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString() ?: ""
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString() ?: ""
        val big = extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString() ?: ""
        val body = if (big.length > text.length) big else text

        val combined = "$title $body".lowercase()

        val isKnownBankApp = BANK_PACKAGES.contains(pkg)
        val hasKeyword = BANK_KEYWORDS.any { combined.contains(it) }

        if (!isKnownBankApp && !hasKeyword) return

        Log.i(TAG, "Bank notification from [$pkg]: ${body.take(100)}")

        val data = mapOf(
            "id" to sbn.id.toLong(),
            "address" to pkg,
            "body" to body.ifEmpty { title },
            "title" to title,
            "timestamp" to sbn.postTime,
            "type" to 1,
            "source" to "notification",
        )

        android.os.Handler(android.os.Looper.getMainLooper()).post {
            notificationEventSink?.success(data)
        }
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification?) {
    }

    override fun onListenerConnected() {
        Log.i(TAG, "NotificationListenerService connected")
    }

    override fun onListenerDisconnected() {
        Log.w(TAG, "NotificationListenerService disconnected — requesting rebind")
        requestRebind(android.content.ComponentName(this, BankNotificationService::class.java))
    }
}
