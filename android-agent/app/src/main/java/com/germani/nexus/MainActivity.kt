package com.germani.nexus

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val store = Store(applicationContext)
        setContent { MaterialTheme { Surface(Modifier.fillMaxSize()) { App(store) } } }
    }
}

@Composable
fun App(store: Store) {
    var paired by remember { mutableStateOf(store.token.isNotEmpty()) }
    if (paired) StatusScreen(store) { store.clear(); paired = false }
    else PairScreen(store) { paired = true }
}

@Composable
fun PairScreen(store: Store, onDone: () -> Unit) {
    var url by remember { mutableStateOf(store.serverUrl) }
    var code by remember { mutableStateOf("") }
    var name by remember { mutableStateOf(DeviceInfo.model()) }
    var msg by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    Column(Modifier.padding(24.dp).statusBarsPadding(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Pair this device", style = MaterialTheme.typography.headlineSmall)
        Text("In the dashboard create a pairing code, then enter it here. This phone will only share what you see on the status screen.")
        OutlinedTextField(url, { url = it }, label = { Text("Server URL (https://...)") }, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(code, { code = it }, label = { Text("Pairing code") }, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(name, { name = it }, label = { Text("Device name") }, modifier = Modifier.fillMaxWidth())
        Button(onClick = {
            scope.launch {
                msg = "Pairing..."
                val r = Api.pair(url.trim().trimEnd('/'), code, name)
                r.onSuccess { store.serverUrl = url; store.token = it; onDone() }
                    .onFailure { msg = it.message ?: "Error" }
            }
        }, modifier = Modifier.fillMaxWidth()) { Text("Pair") }
        if (msg.isNotEmpty()) Text(msg)
    }
}

@Composable
fun StatusScreen(store: Store, onUnpair: () -> Unit) {
    val ctx = androidx.compose.ui.platform.LocalContext.current
    var status by remember { mutableStateOf(DeviceInfo.status(ctx)) }
    var msg by remember { mutableStateOf("Connected") }

    LaunchedEffect(Unit) {
        while (true) {
            status = DeviceInfo.status(ctx)
            Api.heartbeat(store.serverUrl, store.token, status)
                .onSuccess { msg = "Status sent" }
                .onFailure { msg = "Send failed: ${it.message}" }
            delay(60_000)
        }
    }

    Column(Modifier.padding(24.dp).statusBarsPadding(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Nexus Agent", style = MaterialTheme.typography.headlineSmall)
        Text("Device: ${DeviceInfo.model()}")
        Text("Battery: ${status.battery ?: "?"}%")
        Text("Storage free: ${status.freeMb} MB of ${status.totalMb} MB")
        Text(msg)
        Text("Status is sent every 60 seconds while this screen is open.")
        OutlinedButton(onClick = onUnpair, modifier = Modifier.fillMaxWidth()) { Text("Unpair this device") }
    }
}
