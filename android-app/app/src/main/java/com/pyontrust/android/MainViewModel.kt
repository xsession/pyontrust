package com.pyontrust.android

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.pyontrust.android.data.MeasurementProfile
import com.pyontrust.android.data.PyontrustUsbRepository
import com.pyontrust.android.data.UsbDeviceSummary
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class MainUiState(
    val devices: List<UsbDeviceSummary> = emptyList(),
    val connectedDeviceLabel: String? = null,
    val profile: MeasurementProfile = MeasurementProfile(),
    val isConnecting: Boolean = false,
    val isConnected: Boolean = false,
    val isRunning: Boolean = false,
    val latestReading: String = "--",
    val status: String = "Idle",
    val logLines: List<String> = emptyList(),
)

class MainViewModel(
    private val repository: PyontrustUsbRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(MainUiState())
    val state: StateFlow<MainUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repository.profile.collect { profile ->
                _state.update { it.copy(profile = profile) }
            }
        }
        viewModelScope.launch {
            repository.deviceEvents.collect { event ->
                _state.update {
                    it.copy(
                        devices = event.devices,
                        connectedDeviceLabel = event.connectedDeviceLabel,
                        isConnecting = event.isConnecting,
                        isConnected = event.isConnected,
                        isRunning = event.isRunning,
                        latestReading = event.latestReading,
                        status = event.status,
                        logLines = event.logLines,
                    )
                }
            }
        }
        refreshDevices()
    }

    fun refreshDevices() {
        repository.refreshDevices()
    }

    fun connectToDevice(deviceId: Int) {
        repository.connect(deviceId)
    }

    fun disconnect() {
        repository.disconnect()
    }

    fun updateProfile(profile: MeasurementProfile) {
        viewModelScope.launch {
            repository.saveProfile(profile)
        }
    }

    fun applyProfile() {
        repository.applyProfile()
    }

    fun startMeasurement() {
        repository.startMeasurement()
    }

    fun stopMeasurement() {
        repository.stopMeasurement()
    }

    fun clearLog() {
        repository.clearLog()
    }

    override fun onCleared() {
        repository.close()
        super.onCleared()
    }

    companion object {
        fun factory(context: Context): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                @Suppress("UNCHECKED_CAST")
                return MainViewModel(PyontrustUsbRepository(context.applicationContext)) as T
            }
        }
    }
}
