package com.germani.nexus

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import android.os.Environment
import android.os.StatFs
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** Secure storage for the server URL and the device token (AES-encrypted). */
class Store(context: Context) {
    private val prefs = EncryptedSharedPreferences.create(
        context, "nexus_secure",
        MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )
    var serverUrl: String
        get() = prefs.getString("url", "") ?: ""
        set(v) = prefs.edit().putString("url", v.trim().trimEnd('/')).apply()
    var token: String
        get() = prefs.getString("token", "") ?: ""
        set(v) = prefs.edit().putString("token", v).apply()
    fun clear() = prefs.edit().clear().apply()
}

data class Status(val battery: Int?, val totalMb: Long, val freeMb: Long)

object DeviceInfo {
    fun model(): String = "${Build.MANUFACTURER} ${Build.MODEL}"

    fun status(context: Context): Status {
        val i: Intent? = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = i?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = i?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
        val pct = if (level >= 0 && scale > 0) level * 100 / scale else null
        val st = StatFs(Environment.getDataDirectory().path)
        return Status(pct, st.totalBytes / 1_048_576, st.availableBytes / 1_048_576)
    }
}

object Api {
    private fun call(url: String, body: JSONObject, bearer: String? = null): Pair<Int, String> {
        val c = URL(url).openConnection() as HttpURLConnection
        c.requestMethod = "POST"
        c.connectTimeout = 10000
        c.readTimeout = 10000
        c.doOutput = true
        c.setRequestProperty("Content-Type", "application/json")
        if (bearer != null) c.setRequestProperty("Authorization", "Bearer $bearer")
        c.outputStream.use { it.write(body.toString().toByteArray()) }
        val code = c.responseCode
        val stream = if (code in 200..299) c.inputStream else c.errorStream
        return code to (stream?.bufferedReader()?.readText() ?: "")
    }

    /** Pairs this phone using a one-time code created by the admin in the dashboard. */
    suspend fun pair(server: String, code: String, name: String): Result<String> = withContext(Dispatchers.IO) {
        runCatching {
            require(server.startsWith("https://")) { "Server URL must start with https://" }
            val body = JSONObject()
                .put("code", code.trim().uppercase())
                .put("name", name)
                .put("platform", "android")
                .put("model", DeviceInfo.model())
            val (status, text) = call("$server/pairing/pair", body)
            if (status != 201) error("Pairing failed ($status): $text")
            JSONObject(text).getString("device_token")
        }
    }

    suspend fun heartbeat(server: String, token: String, s: Status): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            val body = JSONObject()
                .put("battery_percent", s.battery ?: JSONObject.NULL)
                .put("storage_total_mb", s.totalMb)
                .put("storage_free_mb", s.freeMb)
            val (status, text) = call("$server/devices/me/heartbeat", body, token)
            if (status != 200) error("Status $status: $text")
        }
    }
}
