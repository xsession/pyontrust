package com.pyontrust.android.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = Color(0xFF0B6E4F),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFD3F3E3),
    onPrimaryContainer = Color(0xFF05261B),
    secondary = Color(0xFF3E5C76),
    background = Color(0xFFF8FBFC),
    surface = Color(0xFFF8FBFC),
    surfaceVariant = Color(0xFFE7EEF3),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF78D9B0),
    onPrimary = Color(0xFF043523),
    primaryContainer = Color(0xFF0A4F39),
    onPrimaryContainer = Color(0xFFD3F3E3),
    secondary = Color(0xFFA8C0D8),
)

@Composable
fun PyontrustTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        content = content,
    )
}
