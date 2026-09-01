package com.example.finsight

import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.text.TextUtils
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel
import com.example.finsight.sms.SmsBridgePlugin
import com.example.finsight.sms.BankNotificationService

class MainActivity : FlutterActivity() {

    companion object {
        const val NOTIF_EVENT_CHANNEL = "com.finsight/notification_stream"
    }

    private lateinit var smsBridgePlugin: SmsBridgePlugin

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        smsBridgePlugin = SmsBridgePlugin()
        smsBridgePlugin.setup(applicationContext, flutterEngine.dartExecutor.binaryMessenger)

        EventChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            NOTIF_EVENT_CHANNEL
        ).setStreamHandler(object : EventChannel.StreamHandler {
            override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
                BankNotificationService.notificationEventSink = events
            }
            override fun onCancel(arguments: Any?) {
                BankNotificationService.notificationEventSink = null
            }
        })

        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            "com.finsight/notification_permission"
        ).setMethodCallHandler { call, result ->
            when (call.method) {
                "isNotificationListenerEnabled" ->
                    result.success(isNotificationListenerEnabled())
                "openNotificationSettings" -> {
                    openNotificationListenerSettings()
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
    }

    private fun isNotificationListenerEnabled(): Boolean {
        val flat = Settings.Secure.getString(
            contentResolver, "enabled_notification_listeners"
        ) ?: return false
        return flat.contains(packageName)
    }

    private fun openNotificationListenerSettings() {
        startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
    }
}
