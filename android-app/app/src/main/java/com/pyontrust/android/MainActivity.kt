package com.pyontrust.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pyontrust.android.ui.PyontrustApp
import com.pyontrust.android.ui.theme.PyontrustTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        setContent {
            PyontrustTheme {
                val viewModel: MainViewModel = viewModel(factory = MainViewModel.factory(applicationContext))
                val state by viewModel.state.collectAsState()
                PyontrustApp(
                    state = state,
                    onRefreshDevices = viewModel::refreshDevices,
                    onConnectDevice = viewModel::connectToDevice,
                    onDisconnect = viewModel::disconnect,
                    onProfileChange = viewModel::updateProfile,
                    onApplyProfile = viewModel::applyProfile,
                    onStartMeasurement = viewModel::startMeasurement,
                    onStopMeasurement = viewModel::stopMeasurement,
                    onClearLog = viewModel::clearLog,
                )
            }
        }
    }
}
