package com.pyontrust.cam;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.WindowManager;
import android.widget.TextView;

/**
 * Launcher: makes sure the CAMERA permission is granted, then starts the
 * streaming service (a foreground service may only start camera use while
 * the app is in the foreground).  The PC starts it with
 * {@code adb shell am start -n com.pyontrust.cam/.MainActivity}.
 */
public class MainActivity extends Activity {
    private static final int REQ = 1;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        TextView tv = new TextView(this);
        tv.setGravity(Gravity.CENTER);
        tv.setPadding(40, 40, 40, 40);
        tv.setTextSize(18);
        tv.setText("pyontrust camera\n\nStreaming to the lab PC over USB.\n"
                + "Controlled from pyontrust (Microscopy / 3D Scan).");
        setContentView(tv);

        if (Build.VERSION.SDK_INT >= 23
                && checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            String[] perms = Build.VERSION.SDK_INT >= 33
                    ? new String[]{Manifest.permission.CAMERA, Manifest.permission.POST_NOTIFICATIONS}
                    : new String[]{Manifest.permission.CAMERA};
            requestPermissions(perms, REQ);
        } else {
            startStreaming();
        }
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] results) {
        if (code == REQ && results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) {
            startStreaming();
        }
    }

    private void startStreaming() {
        Intent i = new Intent(this, StreamService.class);
        if (Build.VERSION.SDK_INT >= 26) startForegroundService(i); else startService(i);
        moveTaskToBack(true);
    }
}
