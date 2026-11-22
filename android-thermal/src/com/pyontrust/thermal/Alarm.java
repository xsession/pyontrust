package com.pyontrust.thermal;

import android.content.Context;
import android.media.AudioManager;
import android.media.ToneGenerator;
import android.os.Build;
import android.os.VibrationEffect;
import android.os.Vibrator;

import java.util.List;
import java.util.Locale;

/** High / low temperature alarms (global and per region), with sound and vibration. */
final class Alarm {
    private final Context ctx;
    private final Settings s;
    private ToneGenerator tone;
    private long lastMs;
    String active;                 // text of the active alarm, null when quiet

    Alarm(Context ctx, Settings s) {
        this.ctx = ctx;
        this.s = s;
    }

    void check(Frame f, List<Region> regions) {
        String msg = null;
        if (s.alarmHighOn && f.max >= s.alarmHigh) msg = "HIGH " + s.fmt(f.max) + " ≥ " + s.fmt(s.alarmHigh);
        else if (s.alarmLowOn && f.min <= s.alarmLow) msg = "LOW " + s.fmt(f.min) + " ≤ " + s.fmt(s.alarmLow);
        else {
            for (Region r : regions) {
                if (r.alarm && r.level == 2) {
                    msg = String.format(Locale.US, "%s %s ≥ limit %s", r.name, s.fmt(r.rMax), s.fmt(r.maxC));
                    break;
                }
            }
        }
        active = msg;
        if (msg == null) return;
        long now = System.currentTimeMillis();
        if (now - lastMs < 2000) return;
        lastMs = now;
        if (s.alarmSound) {
            try {
                if (tone == null) tone = new ToneGenerator(AudioManager.STREAM_ALARM, 80);
                tone.startTone(ToneGenerator.TONE_CDMA_ALERT_CALL_GUARD, 400);
            } catch (RuntimeException ignored) { }
        }
        if (s.alarmVibrate) {
            Vibrator v = (Vibrator) ctx.getSystemService(Context.VIBRATOR_SERVICE);
            if (v != null && v.hasVibrator()) {
                if (Build.VERSION.SDK_INT >= 26) v.vibrate(VibrationEffect.createOneShot(300, VibrationEffect.DEFAULT_AMPLITUDE));
                else v.vibrate(300);
            }
        }
    }

    void release() {
        if (tone != null) tone.release();
        tone = null;
    }
}
