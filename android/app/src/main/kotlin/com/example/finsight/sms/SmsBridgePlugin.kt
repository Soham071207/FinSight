package com.example.finsight.sms

import android.content.ContentResolver
import android.content.Context
import android.content.pm.PackageManager
import android.database.Cursor
import android.net.Uri
import android.os.Build
import android.util.Log
import androidx.core.content.ContextCompat
import io.flutter.embedding.engine.plugins.FlutterPlugin
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugin.common.MethodChannel.MethodCallHandler
import io.flutter.plugin.common.MethodChannel.Result

class SmsBridgePlugin : FlutterPlugin, MethodCallHandler {

    companion object {
        const val METHOD_CHANNEL = "com.finsight/sms_bridge"
        const val EVENT_CHANNEL  = "com.finsight/sms_stream"
        const val TAG = "SmsBridgePlugin"

        val SMS_URIS = listOf(
            "content://sms/inbox",
            "content://sms",
            "content://mms-sms/complete-conversations",
            "content://sms/inbox?sim_id=0",
            "content://com.samsung.android.messaging.dataProvider/message",
            "content://com.android.messaging.datamodel.DatabaseHelper/conversations",
        )

        val BANK_KEYWORDS = listOf(
            "debited", "credited", "debit", "credit",
            "rs.", "rs ", "inr", "₹",
            "spent", "paid", "withdrawn", "txn", "upi",
            "a/c", "acct", "account", "bank", "balance",
            "neft", "imps", "rtgs", "atm",
        )

        val FINANCIAL_SENDER_PATTERNS = listOf(
            Regex("^[A-Z]{2}-[A-Z]{4,6}$"),
            Regex("^[0-9]{6}$"),
            Regex("(?i)(bank|finance|pay|upi|axis|sbi|hdfc|icici|kotak|union|bob|pnb|canara|indus)"),
        )
    }

    private lateinit var context: Context
    private lateinit var methodChannel: MethodChannel
    private lateinit var eventChannel: EventChannel

    override fun onAttachedToEngine(binding: FlutterPlugin.FlutterPluginBinding) {
        setup(binding.applicationContext, binding.binaryMessenger)
    }

    override fun onDetachedFromEngine(binding: FlutterPlugin.FlutterPluginBinding) {
        methodChannel.setMethodCallHandler(null)
    }
    
    fun setup(ctx: Context, messenger: io.flutter.plugin.common.BinaryMessenger) {
        context = ctx
        methodChannel = MethodChannel(messenger, METHOD_CHANNEL)
        methodChannel.setMethodCallHandler(this)

        eventChannel = EventChannel(messenger, EVENT_CHANNEL)
        eventChannel.setStreamHandler(SmsStreamHandler(context))
    }

    override fun onMethodCall(call: MethodCall, result: Result) {
        when (call.method) {
            "hasPermission" -> result.success(checkSmsPermission())
            "fetchBankSms" -> {
                val limit  = call.argument<Int>("limit") ?: 200
                val since  = call.argument<Long>("sinceTimestamp") ?: 0L
                result.success(fetchBankSms(limit, since))
            }
            "fetchAllSms" -> {
                val limit = call.argument<Int>("limit") ?: 50
                result.success(fetchRawSms(limit))
            }
            "getPlatformInfo" -> {
                result.success(mapOf(
                    "sdk"          to Build.VERSION.SDK_INT,
                    "manufacturer" to Build.MANUFACTURER,
                    "model"        to Build.MODEL,
                    "brand"        to Build.BRAND,
                ))
            }
            else -> result.notImplemented()
        }
    }

    private fun checkSmsPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            context, android.Manifest.permission.READ_SMS
        ) == PackageManager.PERMISSION_GRANTED
    }

    fun fetchBankSms(limit: Int, sinceTimestamp: Long): List<Map<String, Any?>> {
        if (!checkSmsPermission()) return emptyList()
        val results = mutableListOf<Map<String, Any?>>()
        for (uriString in SMS_URIS) {
            try {
                val uri = Uri.parse(uriString)
                val messages = queryUri(uri, limit, sinceTimestamp)
                if (messages.isNotEmpty()) {
                    results.addAll(messages)
                    break
                }
            } catch (e: Exception) {}
        }
        return results.distinctBy { it["id"] }.filter { isBankSms(it) }
    }

    private fun fetchRawSms(limit: Int): List<Map<String, Any?>> {
        if (!checkSmsPermission()) return emptyList()
        val all = mutableListOf<Map<String, Any?>>()
        for (uriString in SMS_URIS) {
            try {
                val msgs = queryUri(Uri.parse(uriString), limit, 0L)
                if (msgs.isNotEmpty()) {
                    all.addAll(msgs)
                    break
                }
            } catch (_: Exception) {}
        }
        return all.distinctBy { it["id"] }.take(limit)
    }

    private fun queryUri(uri: Uri, limit: Int, sinceTimestamp: Long): List<Map<String, Any?>> {
        val cr: ContentResolver = context.contentResolver
        val results = mutableListOf<Map<String, Any?>>()
        val projection = arrayOf("_id", "address", "body", "date", "type", "read")
        val selection = if (sinceTimestamp > 0) "date > ?" else null
        val selectionArgs = if (sinceTimestamp > 0) arrayOf(sinceTimestamp.toString()) else null
        val sortOrder = "date DESC LIMIT $limit"
        val cursor: Cursor? = try {
            cr.query(uri, projection, selection, selectionArgs, sortOrder)
        } catch (e: Exception) { null }

        cursor?.use { c ->
            val idIdx = c.getColumnIndex("_id")
            val addressIdx = c.getColumnIndex("address")
            val bodyIdx = c.getColumnIndex("body")
            val dateIdx = c.getColumnIndex("date")
            val typeIdx = c.getColumnIndex("type")

            while (c.moveToNext()) {
                val body = if (bodyIdx >= 0) c.getString(bodyIdx) ?: "" else ""
                val addr = if (addressIdx >= 0) c.getString(addressIdx) ?: "" else ""
                results.add(mapOf(
                    "id" to (if (idIdx >= 0) c.getLong(idIdx) else 0L),
                    "address" to addr,
                    "body" to body,
                    "timestamp" to (if (dateIdx >= 0) c.getLong(dateIdx) else 0L),
                    "type" to (if (typeIdx >= 0) c.getInt(typeIdx) else 0),
                ))
            }
        }
        return results
    }

    private fun isBankSms(sms: Map<String, Any?>): Boolean {
        val body = (sms["body"] as? String ?: "").lowercase()
        val address = (sms["address"] as? String ?: "")
        val hasKeyword = BANK_KEYWORDS.any { body.contains(it) }
        val hasPattern = FINANCIAL_SENDER_PATTERNS.any { it.containsMatchIn(address) }
        return hasKeyword || hasPattern
    }
}

class SmsStreamHandler(private val context: Context) : EventChannel.StreamHandler {
    private var receiver: SmsBroadcastReceiver? = null
    override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
        if (events == null) return
        SmsBroadcastReceiver.sharedEventSink = events
        receiver = SmsBroadcastReceiver()
        val filter = android.content.IntentFilter("android.provider.Telephony.SMS_RECEIVED")
        filter.priority = Int.MAX_VALUE
        context.registerReceiver(receiver, filter)
    }
    override fun onCancel(arguments: Any?) {
        SmsBroadcastReceiver.sharedEventSink = null
        receiver?.let { context.unregisterReceiver(it) }
        receiver = null
    }
}
