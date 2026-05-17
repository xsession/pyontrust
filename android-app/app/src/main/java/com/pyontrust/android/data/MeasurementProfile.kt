package com.pyontrust.android.data

data class MeasurementProfile(
    val name: String = "Default profile",
    val sampleRateHz: String = "1000",
    val durationSeconds: String = "10",
    val channel: String = "A0",
    val applyCommandTemplate: String = "SET RATE={rate};DURATION={duration};CHANNEL={channel}\n",
    val startCommand: String = "MEASURE:START\n",
    val stopCommand: String = "MEASURE:STOP\n",
    val monitorCommand: String = "MEASURE:STATUS?\n",
) {
    fun renderApplyCommand(): String {
        return applyCommandTemplate
            .replace("{rate}", sampleRateHz.ifBlank { "1000" })
            .replace("{duration}", durationSeconds.ifBlank { "10" })
            .replace("{channel}", channel.ifBlank { "A0" })
    }
}

data class UsbDeviceSummary(
    val deviceId: Int,
    val productName: String,
    val vendorId: Int,
    val productId: Int,
) {
    val label: String
        get() = "$productName (${vendorId.toString(16)}:${productId.toString(16)})"
}

data class UsbUiEvent(
    val devices: List<UsbDeviceSummary> = emptyList(),
    val connectedDeviceLabel: String? = null,
    val isConnecting: Boolean = false,
    val isConnected: Boolean = false,
    val isRunning: Boolean = false,
    val latestReading: String = "--",
    val status: String = "Idle",
    val logLines: List<String> = emptyList(),
)
