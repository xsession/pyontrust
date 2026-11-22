package com.pyontrust.thermal;

import android.content.Context;
import android.content.SharedPreferences;

/** Every user setting, persisted in SharedPreferences. */
final class Settings {
    // view
    int palette = 0;
    int rotation = 0;
    boolean mirror = true;             // flip horizontal
    boolean flipV = true;              // flip vertical
    boolean fahrenheit = false;
    boolean smoothing = true;          // edge-preserving speckle filter (pyontrust render_frame)
    int noiseReduction = 1;            // temporal averaging: 0 off, 1 low, 2 high
    boolean showHot = true, showCold = true, showCenter = true, showScale = true;
    // range
    boolean autoRange = true;
    float manualLo = 20f, manualHi = 40f;
    float minSpan = 3f;                // DISPLAY_MIN_SPAN_C
    // isotherm: 0 off, 1 above, 2 below, 3 between
    int isoMode = 0;
    float isoLo = 40f, isoHi = 60f;
    // measurement corrections
    float emissivity = 1.0f;
    float reflectedC = 22f;
    // alarms (global)
    boolean alarmHighOn = false, alarmLowOn = false, alarmSound = true, alarmVibrate = true;
    float alarmHigh = 85f, alarmLow = 0f;
    // sources
    String gatewayUrl = "http://127.0.0.1:5210";
    boolean preferUsb = true;
    boolean lastSourceGateway = false;
    float rawOffset = 6000f, rawScale = 50f;
    // tracking / recording
    float trackIntervalS = 1f;
    float recordIntervalS = 0f;        // 0 = every frame
    // measurement defaults (pyontrust ThermalMeasurementConfig)
    String measMode = "continuous";
    float measDuration = 30f, measInterval = 0.5f, measGlobalMax = 85f, measMaxGradient = 0f,
            measPixelPitch = 0.17f, soakWindow = 10f, soakThreshold = 0.5f, soakTimeout = 300f,
            deltaPause = 5f;
    int deltaBaseline = 10, deltaStimulus = 10;
    String boardId = "";

    private final SharedPreferences p;

    Settings(Context c) {
        p = c.getSharedPreferences("thermal", Context.MODE_PRIVATE);
        load();
    }

    float calibrationOffset(String key) { return p.getFloat("cal_" + key, 0f); }

    void setCalibration(String key, float offset, float refC) {
        p.edit().putFloat("cal_" + key, offset).putFloat("calref_" + key, refC)
                .putLong("calts_" + key, System.currentTimeMillis()).apply();
    }

    String calibrationInfo(String key) {
        if (!p.contains("cal_" + key)) return "not calibrated";
        return String.format(java.util.Locale.US, "offset %+.2f °C (ref %.1f °C, %s)", p.getFloat("cal_" + key, 0),
                p.getFloat("calref_" + key, 0),
                android.text.format.DateFormat.format("yyyy-MM-dd HH:mm", p.getLong("calts_" + key, 0)));
    }

    void clearCalibration(String key) {
        p.edit().remove("cal_" + key).remove("calref_" + key).remove("calts_" + key).apply();
    }

    String regionsJson() { return p.getString("regions", "[]"); }

    void saveRegions(String json) { p.edit().putString("regions", json).apply(); }

    void load() {
        palette = p.getInt("palette", palette);
        rotation = p.getInt("rotation", rotation);
        mirror = p.getBoolean("flipH", mirror);
        flipV = p.getBoolean("flipV", flipV);
        fahrenheit = p.getBoolean("fahrenheit", fahrenheit);
        smoothing = p.getBoolean("smoothing", smoothing);
        noiseReduction = p.getInt("noiseReduction", noiseReduction);
        showHot = p.getBoolean("showHot", showHot);
        showCold = p.getBoolean("showCold", showCold);
        showCenter = p.getBoolean("showCenter", showCenter);
        showScale = p.getBoolean("showScale", showScale);
        autoRange = p.getBoolean("autoRange", autoRange);
        manualLo = p.getFloat("manualLo", manualLo);
        manualHi = p.getFloat("manualHi", manualHi);
        minSpan = p.getFloat("minSpan", minSpan);
        isoMode = p.getInt("isoMode", isoMode);
        isoLo = p.getFloat("isoLo", isoLo);
        isoHi = p.getFloat("isoHi", isoHi);
        emissivity = p.getFloat("emissivity", emissivity);
        reflectedC = p.getFloat("reflectedC", reflectedC);
        alarmHighOn = p.getBoolean("alarmHighOn", alarmHighOn);
        alarmLowOn = p.getBoolean("alarmLowOn", alarmLowOn);
        alarmSound = p.getBoolean("alarmSound", alarmSound);
        alarmVibrate = p.getBoolean("alarmVibrate", alarmVibrate);
        alarmHigh = p.getFloat("alarmHigh", alarmHigh);
        alarmLow = p.getFloat("alarmLow", alarmLow);
        gatewayUrl = p.getString("gatewayUrl", gatewayUrl);
        preferUsb = p.getBoolean("preferUsb", preferUsb);
        lastSourceGateway = p.getBoolean("lastSourceGateway", lastSourceGateway);
        rawOffset = p.getFloat("rawOffset", rawOffset);
        rawScale = p.getFloat("rawScale", rawScale);
        trackIntervalS = p.getFloat("trackIntervalS", trackIntervalS);
        recordIntervalS = p.getFloat("recordIntervalS", recordIntervalS);
        measMode = p.getString("measMode", measMode);
        measDuration = p.getFloat("measDuration", measDuration);
        measInterval = p.getFloat("measInterval", measInterval);
        measGlobalMax = p.getFloat("measGlobalMax", measGlobalMax);
        measMaxGradient = p.getFloat("measMaxGradient", measMaxGradient);
        measPixelPitch = p.getFloat("measPixelPitch", measPixelPitch);
        soakWindow = p.getFloat("soakWindow", soakWindow);
        soakThreshold = p.getFloat("soakThreshold", soakThreshold);
        soakTimeout = p.getFloat("soakTimeout", soakTimeout);
        deltaPause = p.getFloat("deltaPause", deltaPause);
        deltaBaseline = p.getInt("deltaBaseline", deltaBaseline);
        deltaStimulus = p.getInt("deltaStimulus", deltaStimulus);
        boardId = p.getString("boardId", boardId);
        SeekUsb.rawOffset = rawOffset;
        SeekUsb.rawScale = rawScale;
    }

    void save() {
        p.edit()
                .putInt("palette", palette).putInt("rotation", rotation).putBoolean("flipH", mirror).putBoolean("flipV", flipV)
                .putBoolean("fahrenheit", fahrenheit).putBoolean("smoothing", smoothing)
                .putInt("noiseReduction", noiseReduction).putBoolean("showHot", showHot)
                .putBoolean("showCold", showCold).putBoolean("showCenter", showCenter)
                .putBoolean("showScale", showScale).putBoolean("autoRange", autoRange)
                .putFloat("manualLo", manualLo).putFloat("manualHi", manualHi).putFloat("minSpan", minSpan)
                .putInt("isoMode", isoMode).putFloat("isoLo", isoLo).putFloat("isoHi", isoHi)
                .putFloat("emissivity", emissivity).putFloat("reflectedC", reflectedC)
                .putBoolean("alarmHighOn", alarmHighOn).putBoolean("alarmLowOn", alarmLowOn)
                .putBoolean("alarmSound", alarmSound).putBoolean("alarmVibrate", alarmVibrate)
                .putFloat("alarmHigh", alarmHigh).putFloat("alarmLow", alarmLow)
                .putString("gatewayUrl", gatewayUrl).putBoolean("preferUsb", preferUsb).putBoolean("lastSourceGateway", lastSourceGateway)
                .putFloat("rawOffset", rawOffset).putFloat("rawScale", rawScale)
                .putFloat("trackIntervalS", trackIntervalS).putFloat("recordIntervalS", recordIntervalS)
                .putString("measMode", measMode).putFloat("measDuration", measDuration)
                .putFloat("measInterval", measInterval).putFloat("measGlobalMax", measGlobalMax)
                .putFloat("measMaxGradient", measMaxGradient).putFloat("measPixelPitch", measPixelPitch)
                .putFloat("soakWindow", soakWindow).putFloat("soakThreshold", soakThreshold)
                .putFloat("soakTimeout", soakTimeout).putFloat("deltaPause", deltaPause)
                .putInt("deltaBaseline", deltaBaseline).putInt("deltaStimulus", deltaStimulus)
                .putString("boardId", boardId)
                .apply();
        SeekUsb.rawOffset = rawOffset;
        SeekUsb.rawScale = rawScale;
    }

    // ── units ────────────────────────────────────────────────────────

    float disp(float c) { return fahrenheit ? c * 9f / 5f + 32f : c; }

    float fromDisp(float v) { return fahrenheit ? (v - 32f) * 5f / 9f : v; }

    String unit() { return fahrenheit ? "°F" : "°C"; }

    String fmt(float c) { return Float.isNaN(c) ? "—" : String.format(java.util.Locale.US, "%.1f%s", disp(c), unit()); }

    /** Temperature difference (no +32 offset for °F). */
    String fmtDelta(float dc) {
        return String.format(java.util.Locale.US, "%+.2f %s", fahrenheit ? dc * 9f / 5f : dc, fahrenheit ? "°F" : "K");
    }
}
