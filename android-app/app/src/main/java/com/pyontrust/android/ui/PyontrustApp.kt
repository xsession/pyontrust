package com.pyontrust.android.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.weight
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.dp
import com.pyontrust.android.MainUiState
import com.pyontrust.android.data.MeasurementProfile

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PyontrustApp(
    state: MainUiState,
    onRefreshDevices: () -> Unit,
    onConnectDevice: (Int) -> Unit,
    onDisconnect: () -> Unit,
    onProfileChange: (MeasurementProfile) -> Unit,
    onApplyProfile: () -> Unit,
    onStartMeasurement: () -> Unit,
    onStopMeasurement: () -> Unit,
    onClearLog: () -> Unit,
) {
    Scaffold(
        topBar = { TopAppBar(title = { Text("Pyontrust USB Bench") }) },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .navigationBarsPadding()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            StatusCard(state)
            DeviceCard(state, onRefreshDevices, onConnectDevice, onDisconnect)
            ProfileCard(state.profile, onProfileChange, onApplyProfile, onStartMeasurement, onStopMeasurement, state.isConnected, state.isRunning)
            LogCard(state.logLines, onClearLog)
        }
    }
}

@Composable
private fun StatusCard(state: MainUiState) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("Live status", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                StatusBadge(
                    text = if (state.isConnected) "USB connected" else "USB disconnected",
                    active = state.isConnected,
                )
                StatusBadge(
                    text = if (state.isRunning) "Measurement running" else "Measurement idle",
                    active = state.isRunning,
                )
                StatusBadge(text = "Latest reading: ${state.latestReading}")
            }
            Text("State: ${state.status}")
            Text("Device: ${state.connectedDeviceLabel ?: "None"}")
        }
    }
}

@Composable
private fun StatusBadge(text: String, active: Boolean? = null) {
    val containerColor = when (active) {
        true -> MaterialTheme.colorScheme.primaryContainer
        false -> MaterialTheme.colorScheme.surfaceVariant
        null -> MaterialTheme.colorScheme.secondaryContainer
    }
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .semantics { stateDescription = text },
        shape = RoundedCornerShape(12.dp),
        color = containerColor,
        tonalElevation = 1.dp,
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
            style = MaterialTheme.typography.labelLarge,
        )
    }
}

@Composable
private fun DeviceCard(
    state: MainUiState,
    onRefreshDevices: () -> Unit,
    onConnectDevice: (Int) -> Unit,
    onDisconnect: () -> Unit,
) {
    Card {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("USB hardware", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Button(
                    onClick = onRefreshDevices,
                    modifier = Modifier.weight(1f),
                ) { Text("Refresh") }
                OutlinedButton(
                    onClick = onDisconnect,
                    enabled = state.isConnected || state.isConnecting,
                    modifier = Modifier.weight(1f),
                ) { Text("Disconnect") }
            }
            if (state.devices.isEmpty()) {
                Text("No USB devices discovered yet.")
            } else {
                state.devices.forEach { device ->
                    Surface(
                        shape = RoundedCornerShape(16.dp),
                        tonalElevation = 2.dp,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(device.productName, fontWeight = FontWeight.SemiBold)
                            Text("VID:PID ${device.vendorId.toString(16)}:${device.productId.toString(16)}")
                            OutlinedButton(
                                onClick = { onConnectDevice(device.deviceId) },
                                enabled = !state.isConnecting,
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Text("Connect")
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ProfileCard(
    profile: MeasurementProfile,
    onProfileChange: (MeasurementProfile) -> Unit,
    onApplyProfile: () -> Unit,
    onStartMeasurement: () -> Unit,
    onStopMeasurement: () -> Unit,
    isConnected: Boolean,
    isRunning: Boolean,
) {
    Card {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Measurement profile", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            OutlinedTextField(
                value = profile.name,
                onValueChange = { onProfileChange(profile.copy(name = it)) },
                label = { Text("Profile name") },
                modifier = Modifier.fillMaxWidth(),
            )
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = profile.sampleRateHz,
                    onValueChange = { onProfileChange(profile.copy(sampleRateHz = it)) },
                    label = { Text("Sample rate Hz") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
                OutlinedTextField(
                    value = profile.durationSeconds,
                    onValueChange = { onProfileChange(profile.copy(durationSeconds = it)) },
                    label = { Text("Duration s") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
            }
            OutlinedTextField(
                value = profile.channel,
                onValueChange = { onProfileChange(profile.copy(channel = it)) },
                label = { Text("Channel") },
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = profile.applyCommandTemplate,
                onValueChange = { onProfileChange(profile.copy(applyCommandTemplate = it)) },
                label = { Text("Apply command template") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
            )
            OutlinedTextField(
                value = profile.startCommand,
                onValueChange = { onProfileChange(profile.copy(startCommand = it)) },
                label = { Text("Start command") },
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = profile.stopCommand,
                onValueChange = { onProfileChange(profile.copy(stopCommand = it)) },
                label = { Text("Stop command") },
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = profile.monitorCommand,
                onValueChange = { onProfileChange(profile.copy(monitorCommand = it)) },
                label = { Text("Monitor command") },
                modifier = Modifier.fillMaxWidth(),
            )
            Text(
                text = "Rendered apply command: ${profile.renderApplyCommand().trimEnd()}",
                style = MaterialTheme.typography.bodySmall,
                fontFamily = FontFamily.Monospace,
            )
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedButton(
                    onClick = onApplyProfile,
                    enabled = isConnected,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Apply profile") }
                Button(
                    onClick = onStartMeasurement,
                    enabled = isConnected && !isRunning,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Start measurement") }
                OutlinedButton(
                    onClick = onStopMeasurement,
                    enabled = isConnected && isRunning,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Stop measurement") }
            }
        }
    }
}

@Composable
private fun LogCard(lines: List<String>, onClearLog: () -> Unit) {
    Card {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Measurement log", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                OutlinedButton(onClick = onClearLog) { Text("Clear") }
            }
            HorizontalDivider()
            if (lines.isEmpty()) {
                Text("No USB traffic yet.")
            } else {
                LazyColumn(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(240.dp)
                        .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(16.dp))
                        .padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    items(lines) { line ->
                        Text(line, fontFamily = FontFamily.Monospace)
                    }
                }
            }
        }
    }
}
