package com.pyontrust.android.data

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.hardware.usb.UsbConstants
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbDeviceConnection
import android.hardware.usb.UsbEndpoint
import android.hardware.usb.UsbInterface
import android.hardware.usb.UsbManager
import android.os.Build
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.nio.charset.StandardCharsets

private val Context.profileStore by preferencesDataStore(name = "pyontrust_usb_profile")

class PyontrustUsbRepository(
    private val context: Context,
) {
    private val usbManager = context.getSystemService(Context.USB_SERVICE) as UsbManager
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val _deviceEvents = MutableStateFlow(UsbUiEvent())
    val deviceEvents: StateFlow<UsbUiEvent> = _deviceEvents.asStateFlow()

    val profile = context.profileStore.data.map { prefs ->
        MeasurementProfile(
            name = prefs[NAME_KEY] ?: "Default profile",
            sampleRateHz = prefs[SAMPLE_RATE_KEY] ?: "1000",
            durationSeconds = prefs[DURATION_KEY] ?: "10",
            channel = prefs[CHANNEL_KEY] ?: "A0",
            applyCommandTemplate = prefs[APPLY_TEMPLATE_KEY] ?: "SET RATE={rate};DURATION={duration};CHANNEL={channel}\n",
            startCommand = prefs[START_KEY] ?: "MEASURE:START\n",
            stopCommand = prefs[STOP_KEY] ?: "MEASURE:STOP\n",
            monitorCommand = prefs[MONITOR_KEY] ?: "MEASURE:STATUS?\n",
        )
    }

    private var currentProfile = MeasurementProfile()
    private var connection: UsbDeviceConnection? = null
    private var usbInterface: UsbInterface? = null
    private var inEndpoint: UsbEndpoint? = null
    private var outEndpoint: UsbEndpoint? = null
    private var monitorJob: Job? = null
    private var readJob: Job? = null

    private val permissionReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action != ACTION_USB_PERMISSION) return
            val device = intent.getParcelableExtraCompat<UsbDevice>(UsbManager.EXTRA_DEVICE) ?: return
            val granted = intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false)
            if (!granted) {
                appendLog("USB permission denied for ${device.deviceName}")
                _deviceEvents.update { it.copy(isConnecting = false, status = "Permission denied") }
                return
            }
            openDevice(device)
        }
    }

    init {
        val filter = IntentFilter(ACTION_USB_PERMISSION)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            context.registerReceiver(permissionReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            @Suppress("DEPRECATION")
            context.registerReceiver(permissionReceiver, filter)
        }

        scope.launch {
            profile.collect {
                currentProfile = it
            }
        }
    }

    fun refreshDevices() {
        val devices = usbManager.deviceList.values.map { device ->
            UsbDeviceSummary(
                deviceId = device.deviceId,
                productName = device.productName ?: device.deviceName,
                vendorId = device.vendorId,
                productId = device.productId,
            )
        }.sortedBy { it.productName.lowercase() }

        _deviceEvents.update { it.copy(devices = devices) }
        appendLog("Discovered ${devices.size} USB device(s)")
    }

    fun connect(deviceId: Int) {
        val device = usbManager.deviceList.values.firstOrNull { it.deviceId == deviceId }
        if (device == null) {
            appendLog("Selected USB device no longer available")
            refreshDevices()
            return
        }
        _deviceEvents.update { it.copy(isConnecting = true, status = "Requesting USB permission") }
        if (usbManager.hasPermission(device)) {
            openDevice(device)
            return
        }

        val flags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0
        val intent = PendingIntent.getBroadcast(
            context,
            device.deviceId,
            Intent(ACTION_USB_PERMISSION),
            flags,
        )
        usbManager.requestPermission(device, intent)
    }

    fun disconnect() {
        monitorJob?.cancel()
        readJob?.cancel()
        usbInterface?.let { intf -> connection?.releaseInterface(intf) }
        connection?.close()
        connection = null
        usbInterface = null
        inEndpoint = null
        outEndpoint = null
        _deviceEvents.update {
            it.copy(
                isConnecting = false,
                isConnected = false,
                isRunning = false,
                connectedDeviceLabel = null,
                status = "Disconnected",
            )
        }
    }

    suspend fun saveProfile(profile: MeasurementProfile) {
        context.profileStore.edit { prefs ->
            prefs[NAME_KEY] = profile.name
            prefs[SAMPLE_RATE_KEY] = profile.sampleRateHz
            prefs[DURATION_KEY] = profile.durationSeconds
            prefs[CHANNEL_KEY] = profile.channel
            prefs[APPLY_TEMPLATE_KEY] = profile.applyCommandTemplate
            prefs[START_KEY] = profile.startCommand
            prefs[STOP_KEY] = profile.stopCommand
            prefs[MONITOR_KEY] = profile.monitorCommand
        }
    }

    fun applyProfile() {
        sendCommand(currentProfile.renderApplyCommand(), "Profile applied")
    }

    fun startMeasurement() {
        sendCommand(currentProfile.startCommand, "Measurement started")
        _deviceEvents.update { it.copy(isRunning = true, status = "Measurement running") }
        monitorJob?.cancel()
        monitorJob = scope.launch {
            while (isActive && _deviceEvents.value.isConnected) {
                sendCommand(currentProfile.monitorCommand, "Monitoring")
                delay(1000)
            }
        }
    }

    fun stopMeasurement() {
        monitorJob?.cancel()
        monitorJob = null
        sendCommand(currentProfile.stopCommand, "Measurement stopped")
        _deviceEvents.update { it.copy(isRunning = false, status = "Measurement stopped") }
    }

    fun clearLog() {
        _deviceEvents.update { it.copy(logLines = emptyList()) }
    }

    fun close() {
        disconnect()
        runCatching { context.unregisterReceiver(permissionReceiver) }
    }

    private fun openDevice(device: UsbDevice) {
        disconnect()

        val session = findSession(device)
        if (session == null) {
            appendLog("No matching USB bulk endpoints on ${device.deviceName}")
            _deviceEvents.update { it.copy(isConnecting = false, status = "Unsupported USB device") }
            return
        }

        val opened = usbManager.openDevice(device)
        if (opened == null) {
            appendLog("Failed to open ${device.deviceName}")
            _deviceEvents.update { it.copy(isConnecting = false, status = "Open failed") }
            return
        }

        if (!opened.claimInterface(session.usbInterface, true)) {
            opened.close()
            appendLog("Failed to claim interface for ${device.deviceName}")
            _deviceEvents.update { it.copy(isConnecting = false, status = "Claim failed") }
            return
        }

        connection = opened
        usbInterface = session.usbInterface
        inEndpoint = session.inEndpoint
        outEndpoint = session.outEndpoint

        _deviceEvents.update {
            it.copy(
                isConnecting = false,
                isConnected = true,
                connectedDeviceLabel = "${device.productName ?: device.deviceName} (${device.deviceName})",
                status = "Connected",
            )
        }
        appendLog("Connected to ${device.productName ?: device.deviceName}")
        startReader()
    }

    private fun startReader() {
        readJob?.cancel()
        readJob = scope.launch {
            val buffer = ByteArray(512)
            while (isActive && connection != null && inEndpoint != null) {
                val bytesRead = connection?.bulkTransfer(inEndpoint, buffer, buffer.size, 250) ?: -1
                if (bytesRead > 0) {
                    val text = String(buffer, 0, bytesRead, StandardCharsets.UTF_8).trim()
                    if (text.isNotEmpty()) {
                        appendLog("RX $text")
                        _deviceEvents.update { it.copy(latestReading = text) }
                    }
                }
            }
        }
    }

    private fun sendCommand(command: String, label: String) {
        val out = outEndpoint
        val conn = connection
        if (out == null || conn == null) {
            appendLog("Cannot send command while disconnected")
            _deviceEvents.update { it.copy(status = "No USB connection") }
            return
        }

        val payload = command.toByteArray(StandardCharsets.UTF_8)
        val sent = conn.bulkTransfer(out, payload, payload.size, 1000)
        if (sent >= 0) {
            appendLog("TX ${command.trimEnd()}")
            _deviceEvents.update { it.copy(status = label) }
        } else {
            appendLog("USB write failed")
            _deviceEvents.update { it.copy(status = "USB write failed") }
        }
    }

    private fun appendLog(message: String) {
        _deviceEvents.update { event ->
            event.copy(logLines = (event.logLines + message).takeLast(MAX_LOG_LINES))
        }
    }

    private fun findSession(device: UsbDevice): UsbSession? {
        for (interfaceIndex in 0 until device.interfaceCount) {
            val usbInterface = device.getInterface(interfaceIndex)
            var bulkIn: UsbEndpoint? = null
            var bulkOut: UsbEndpoint? = null
            for (endpointIndex in 0 until usbInterface.endpointCount) {
                val endpoint = usbInterface.getEndpoint(endpointIndex)
                if (endpoint.type != UsbConstants.USB_ENDPOINT_XFER_BULK) continue
                if (endpoint.direction == UsbConstants.USB_DIR_IN) bulkIn = endpoint
                if (endpoint.direction == UsbConstants.USB_DIR_OUT) bulkOut = endpoint
            }
            if (bulkIn != null && bulkOut != null) {
                return UsbSession(usbInterface, bulkIn, bulkOut)
            }
        }
        return null
    }

    private inline fun <reified T> Intent.getParcelableExtraCompat(name: String): T? {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            getParcelableExtra(name, T::class.java)
        } else {
            @Suppress("DEPRECATION")
            getParcelableExtra(name)
        }
    }

    private data class UsbSession(
        val usbInterface: UsbInterface,
        val inEndpoint: UsbEndpoint,
        val outEndpoint: UsbEndpoint,
    )

    companion object {
        private const val ACTION_USB_PERMISSION = "com.pyontrust.android.USB_PERMISSION"
        private const val MAX_LOG_LINES = 120

        private val NAME_KEY = stringPreferencesKey("name")
        private val SAMPLE_RATE_KEY = stringPreferencesKey("sample_rate")
        private val DURATION_KEY = stringPreferencesKey("duration")
        private val CHANNEL_KEY = stringPreferencesKey("channel")
        private val APPLY_TEMPLATE_KEY = stringPreferencesKey("apply_template")
        private val START_KEY = stringPreferencesKey("start")
        private val STOP_KEY = stringPreferencesKey("stop")
        private val MONITOR_KEY = stringPreferencesKey("monitor")
    }
}
