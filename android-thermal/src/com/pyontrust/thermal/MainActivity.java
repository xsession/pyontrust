package com.pyontrust.thermal;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.graphics.Bitmap;
import android.graphics.Typeface;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ConcurrentLinkedQueue;

/**
 * pyontrust Thermal: live Seek Thermal image on the phone (USB OTG) or from
 * the lab PC (pyontrust gateway), with pyontrust's Thermal workspace tools —
 * regions with limits, tracking to CSV, continuous / soak / delta / gradient
 * measurements with HTML reports, one-point calibration, flat-field — plus
 * palettes, isotherms, alarms, emissivity, line profiles, histogram,
 * radiometric snapshots / recordings and re-analysis.
 */
public class MainActivity extends Activity implements ThermalView.Listener {
    private static final String ACTION_USB_PERMISSION = "com.pyontrust.thermal.USB_PERMISSION";
    static final String EXTRA_OPEN = "open_thr";

    private Settings s;
    private Processor proc;
    private ThermalView view;
    private ChartView chart;
    private TextView status, info;
    private ProgressBar progress;
    private Button btnTool, btnRec, btnTrack, btnFreeze, btnMeasure;
    private final Handler ui = new Handler(Looper.getMainLooper());

    private final List<Region> regions = new java.util.concurrent.CopyOnWriteArrayList<>();
    private final Tracker tracker = new Tracker();
    private Alarm alarm;
    private volatile Measurement measurement;
    private volatile ThrFile.Writer recorder;
    private File recordFile;
    private long lastRecordMs;

    private volatile FrameSource source;
    private volatile boolean sourceOpen, running, frozen;
    private volatile Frame frozenApparent;
    private volatile String sourceError;
    private final ConcurrentLinkedQueue<Runnable> workerTasks = new ConcurrentLinkedQueue<>();
    private Thread worker;
    private float fps;
    private int chartMode;            // 0 hidden, 1 trend, 2 profile, 3 histogram
    private long lastChartMs;

    // ── lifecycle ────────────────────────────────────────────────────

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        s = new Settings(this);
        proc = new Processor(s);
        alarm = new Alarm(this, s);
        regions.addAll(Region.listFromJson(s.regionsJson()));
        buildUi();

        IntentFilter f = new IntentFilter();
        f.addAction(ACTION_USB_PERMISSION);
        f.addAction(UsbManager.ACTION_USB_DEVICE_ATTACHED);
        f.addAction(UsbManager.ACTION_USB_DEVICE_DETACHED);
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(usbReceiver, f, Context.RECEIVER_NOT_EXPORTED);
        else registerReceiver(usbReceiver, f);

        if (!handleIntent(getIntent())) autoSelectSource();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        handleIntent(intent);
    }

    private boolean handleIntent(Intent i) {
        if (i == null) return false;
        if (i.hasExtra(EXTRA_OPEN)) {
            openRecording(new File(i.getStringExtra(EXTRA_OPEN)));
            return true;
        }
        if (UsbManager.ACTION_USB_DEVICE_ATTACHED.equals(i.getAction())) {
            UsbDevice d = i.getParcelableExtra(UsbManager.EXTRA_DEVICE);
            if (SeekUsb.isSeek(d)) { useUsb(d); return true; }
        }
        return false;
    }

    @Override
    protected void onResume() {
        super.onResume();
        running = true;
        if (worker == null) {
            worker = new Thread(this::loop, "thermal");
            worker.start();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        // keep running while tracking / measuring / recording (screen stays on); otherwise stop the camera
        if (!tracker.running() && measurement == null && recorder == null) stopWorker();
    }

    @Override
    protected void onDestroy() {
        stopWorker();
        stopRecording(false);
        tracker.stop();
        alarm.release();
        try { unregisterReceiver(usbReceiver); } catch (Exception ignored) { }
        super.onDestroy();
    }

    private void stopWorker() {
        running = false;
        Thread t = worker;
        worker = null;
        if (t != null) {
            t.interrupt();
            try { t.join(3000); } catch (InterruptedException ignored) { }
        }
    }

    // ── sources ──────────────────────────────────────────────────────

    private UsbManager usb() { return (UsbManager) getSystemService(Context.USB_SERVICE); }

    private UsbDevice attachedSeek() {
        UsbManager m = usb();
        if (m == null) return null;
        for (UsbDevice d : m.getDeviceList().values()) if (SeekUsb.isSeek(d)) return d;
        return null;
    }

    static final String WAITING = "Plug in the Seek Thermal camera\n(USB OTG adapter)";

    /** Standalone by default: the phone's own USB camera. The gateway only if it was chosen last time. */
    private void autoSelectSource() {
        UsbDevice d = attachedSeek();
        if (d != null && (s.preferUsb || !s.lastSourceGateway)) useUsb(d);
        else if (s.lastSourceGateway) useGateway();
        else showWaiting();
    }

    private void showWaiting() {
        setSource(null);
        status.setText("Waiting for the Seek camera — Source ▸ for the PC gateway or saved images");
        view.banner = WAITING;
        view.clear();
    }

    private void useGateway() {
        s.lastSourceGateway = true;
        s.save();
        setSource(new GatewaySource(s.gatewayUrl));
    }

    private void useUsb(UsbDevice d) {
        UsbManager m = usb();
        if (m.hasPermission(d)) {
            s.lastSourceGateway = false;
            s.save();
            setSource(new SeekUsb(m, d, new File(FilesProvider.root(this), "calibration")));
            return;
        }
        Intent i = new Intent(ACTION_USB_PERMISSION).setPackage(getPackageName());
        int flags = Build.VERSION.SDK_INT >= 31 ? PendingIntent.FLAG_MUTABLE : 0;
        m.requestPermission(d, PendingIntent.getBroadcast(this, 0, i, flags));
        status.setText("Allow USB access to the Seek camera…");
    }

    private void setSource(FrameSource src) {
        workerTasks.add(() -> {
            closeSource();
            source = src;
            sourceError = null;
            frozen = false;
            proc.reset();
        });
        if (worker == null && running) onResume();
    }

    private void closeSource() {
        FrameSource old = source;
        if (old != null && sourceOpen) old.close();
        sourceOpen = false;
    }

    private final BroadcastReceiver usbReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context c, Intent i) {
            UsbDevice d = i.getParcelableExtra(UsbManager.EXTRA_DEVICE);
            String a = i.getAction();
            if (ACTION_USB_PERMISSION.equals(a)) {
                if (d != null && i.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false)) useUsb(d);
                else toast("USB access denied — the camera can't be used");
            } else if (UsbManager.ACTION_USB_DEVICE_ATTACHED.equals(a) && SeekUsb.isSeek(d)) {
                if (!(source instanceof SeekUsb)) useUsb(d);
            } else if (UsbManager.ACTION_USB_DEVICE_DETACHED.equals(a) && SeekUsb.isSeek(d) && source instanceof SeekUsb) {
                workerTasks.add(() -> { closeSource(); source = null; });
                showWaiting();
            }
        }
    };

    // ── frame loop (worker thread) ───────────────────────────────────

    private void loop() {
        long lastFrameMs = 0;
        while (running) {
            Runnable task;
            while ((task = workerTasks.poll()) != null) {
                try { task.run(); } catch (Exception e) { post(() -> toast(e.getMessage())); }
            }
            FrameSource src = source;
            try {
                if (src == null) { Thread.sleep(300); continue; }
                Frame f;
                if (frozen && frozenApparent != null) {
                    Thread.sleep(150);
                    f = Processor.emissivity(frozenApparent, s.emissivity, s.reflectedC).stats();
                    for (Region r : regions) r.measure(f);
                } else {
                    if (!sourceOpen) {
                        post(() -> status.setText("Connecting to " + src.name() + "…"));
                        src.open();
                        sourceOpen = true;
                        sourceError = null;
                    }
                    Frame raw = src.grab();
                    f = proc.process(raw, src, s.calibrationOffset(src.calibrationKey()));
                    long now = System.currentTimeMillis();
                    if (lastFrameMs != 0) fps = 0.8f * fps + 0.2f * (1000f / Math.max(1, now - lastFrameMs));
                    lastFrameMs = now;
                    onFrame(f);
                }
                Bitmap b = proc.render(f);
                final Frame ff = f;
                final float lo = proc.rangeLo, hi = proc.rangeHi;
                post(() -> showFrame(ff, b, lo, hi));
            } catch (InterruptedException e) {
                break;
            } catch (Exception e) {
                String msg = e.getMessage() != null ? e.getMessage() : e.toString();
                sourceError = msg;
                if (sourceOpen) { try { src.close(); } catch (Exception ignored) { } }
                sourceOpen = false;
                post(() -> {
                    status.setText("⚠ " + msg.split("\n")[0]);
                    view.banner = "No image\n" + msg + "\nretrying…";
                    view.clear();
                });
                try { Thread.sleep(2000); } catch (InterruptedException ie) { break; }
            }
        }
        closeSource();
    }

    /** Live-only work: tracking, measurement, recording, alarms. */
    private void onFrame(Frame f) {
        for (Region r : regions) r.measure(f);
        alarm.check(f, regions);
        if (tracker.offer(f) && chartMode == 1) post(this::refreshChart);
        Measurement m = measurement;
        if (m != null && m.offer(f) && m.done) finishMeasurement(m);
        ThrFile.Writer w = recorder;
        if (w != null) {
            long now = System.currentTimeMillis();
            if (now - lastRecordMs >= s.recordIntervalS * 1000) {
                lastRecordMs = now;
                try { w.add(proc.apparent); } catch (Exception e) { post(() -> stopRecording(true)); }
            }
        }
    }

    private void post(Runnable r) { ui.post(r); }

    private void showFrame(Frame f, Bitmap b, float lo, float hi) {
        view.banner = bannerText();
        view.setFrame(f, b, lo, hi, regions);
        FrameSource src = source;
        String cal = src == null ? "" : s.calibrationOffset(src.calibrationKey()) != 0 ? "  · cal" : "";
        String rate = frozen ? "  · FROZEN"
                : src instanceof ThrFile.Playback ? "  · frame " + (((ThrFile.Playback) src).index() + 1) + "/" + ((ThrFile.Playback) src).frames()
                : String.format(Locale.US, "  · %.1f fps", fps);
        status.setText((src == null ? "" : src.name()) + rate
                + "  · " + f.w + "×" + f.h + cal);
        info.setText(infoText(f));
        Measurement m = measurement;
        progress.setVisibility(m != null ? View.VISIBLE : View.GONE);
        if (m != null) progress.setProgress((int) (m.progress() * 1000));
        long now = System.currentTimeMillis();
        if (chartMode > 1 && now - lastChartMs > 400) { lastChartMs = now; refreshChart(); }
    }

    private String bannerText() {
        List<String> parts = new ArrayList<>();
        if (alarm.active != null) parts.add("⚠ " + alarm.active);
        if (recorder != null) parts.add("● REC " + recorder.frames);
        if (tracker.running()) parts.add("TRACK " + tracker.samples());
        Measurement m = measurement;
        if (m != null) parts.add("MEAS " + m.phase);
        if (parts.isEmpty()) return null;
        StringBuilder sb = new StringBuilder();
        for (String p : parts) sb.append(sb.length() == 0 ? "" : "   ").append(p);
        return sb.toString();
    }

    private String infoText(Frame f) {
        StringBuilder sb = new StringBuilder();
        for (Region r : regions) {
            if (sb.length() > 0) sb.append("   ");
            String lv = r.level == 2 ? "✕" : r.level == 1 ? "!" : "";
            sb.append(lv).append(r.name).append(' ');
            if (r.isPoint()) sb.append(s.fmt(r.rMean));
            else sb.append(s.fmt(r.rMin)).append('…').append(s.fmt(r.rMax)).append(" ⌀").append(s.fmt(r.rMean));
        }
        if (sb.length() == 0) sb.append("Tap the image to read a spot. Tools ▸ add points, areas and lines.");
        return sb.toString();
    }

    // ── UI ───────────────────────────────────────────────────────────

    private final List<Button> buttons = new ArrayList<>();

    /** Widgets are created once; {@link #layoutUi()} arranges them for portrait or landscape. */
    private void buildUi() {
        float dp = getResources().getDisplayMetrics().density;
        status = new TextView(this);
        status.setTextColor(0xffcdd6f4);
        status.setTextSize(12);
        status.setPadding((int) (8 * dp), (int) (6 * dp), (int) (8 * dp), (int) (4 * dp));
        status.setSingleLine(true);
        status.setText("pyontrust Thermal");
        status.setOnClickListener(v -> sourceDialog());

        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(1000);
        progress.setVisibility(View.GONE);

        view = new ThermalView(this, s);
        view.listener = this;

        info = new TextView(this);
        info.setTextColor(0xffbac2de);
        info.setTextSize(12);
        info.setTypeface(Typeface.MONOSPACE);
        info.setPadding((int) (8 * dp), (int) (4 * dp), (int) (8 * dp), (int) (4 * dp));
        info.setMaxLines(3);

        chart = new ChartView(this, s);
        chart.setVisibility(View.GONE);
        chart.setOnClickListener(v -> { chartMode = chartMode % 3 + 1; refreshChart(); });

        btn("Source", v -> sourceDialog());
        btn("Palette", v -> paletteDialog());
        btn("Range", v -> rangeDialog());
        btnTool = btn("Tool: —", v -> toolDialog());
        btnFreeze = btn("Freeze", v -> toggleFreeze());
        btn("Snapshot", v -> snapshot());
        btnRec = btn("● Rec", v -> toggleRecording());
        btnTrack = btn("Track", v -> toggleTracking());
        btnMeasure = btn("Measure", v -> measureDialog());
        btn("Chart", v -> toggleChart());
        btn("Gallery", v -> startActivity(new Intent(this, GalleryActivity.class)));
        btn("Settings", v -> settingsDialog());
        layoutUi();
    }

    @Override
    public void onConfigurationChanged(android.content.res.Configuration c) {
        super.onConfigurationChanged(c);
        layoutUi();          // rotation keeps the camera, tracking and recordings running
    }

    private static void detach(View v) {
        if (v.getParent() instanceof ViewGroup) ((ViewGroup) v.getParent()).removeView(v);
    }

    private void layoutUi() {
        float dp = getResources().getDisplayMetrics().density;
        boolean land = getResources().getConfiguration().orientation == android.content.res.Configuration.ORIENTATION_LANDSCAPE;
        for (View v : new View[]{status, progress, view, info, chart}) detach(v);
        for (Button b : buttons) detach(b);

        LinearLayout main = new LinearLayout(this);
        main.setOrientation(LinearLayout.VERTICAL);
        main.addView(status);
        main.addView(progress, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, (int) (6 * dp)));
        main.addView(view, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        main.addView(info);
        main.addView(chart, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, (int) ((land ? 110 : 150) * dp)));

        LinearLayout root = new LinearLayout(this);
        root.setBackgroundColor(0xff11111b);
        if (land) {
            // image on the left, buttons in a 2-column side panel
            root.setOrientation(LinearLayout.HORIZONTAL);
            root.addView(main, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1f));
            LinearLayout side = new LinearLayout(this);
            side.setOrientation(LinearLayout.VERTICAL);
            for (int i = 0; i < buttons.size(); i += 2) {
                LinearLayout r = new LinearLayout(this);
                for (int k = i; k < Math.min(i + 2, buttons.size()); k++) {
                    r.addView(buttons.get(k), new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
                }
                side.addView(r, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
            }
            android.widget.ScrollView sv = new android.widget.ScrollView(this);
            sv.setFillViewport(true);
            sv.addView(side);
            root.addView(sv, new LinearLayout.LayoutParams((int) (230 * dp), ViewGroup.LayoutParams.MATCH_PARENT));
        } else {
            root.setOrientation(LinearLayout.VERTICAL);
            root.addView(main, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
            for (int i = 0; i < buttons.size(); i += 4) {
                LinearLayout r = new LinearLayout(this);
                for (int k = i; k < Math.min(i + 4, buttons.size()); k++) {
                    r.addView(buttons.get(k), new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
                }
                root.addView(r);
            }
        }
        setContentView(root);
    }

    private Button btn(String label, View.OnClickListener l) {
        Button b = new Button(this, null, android.R.attr.buttonStyleSmall);
        b.setText(label);
        b.setAllCaps(false);
        b.setTextSize(13);
        b.setSingleLine(true);
        b.setOnClickListener(l);
        buttons.add(b);
        return b;
    }

    private void toast(String m) { Toast.makeText(this, m, Toast.LENGTH_LONG).show(); }

    private File dir(String name) {
        File d = new File(FilesProvider.root(this), name);
        //noinspection ResultOfMethodCallIgnored
        d.mkdirs();
        return d;
    }

    private static String stamp() { return new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(new Date()); }

    // ── dialogs ──────────────────────────────────────────────────────

    private void sourceDialog() {
        List<String> labels = new ArrayList<>();
        List<Runnable> actions = new ArrayList<>();
        UsbManager m = usb();
        if (m != null) {
            for (UsbDevice d : m.getDeviceList().values()) {
                if (!SeekUsb.isSeek(d)) continue;
                labels.add("USB: " + (d.getProductId() == SeekUsb.PID_PRO ? "Seek CompactPRO" : "Seek Compact / XR"));
                actions.add(() -> useUsb(d));
            }
        }
        if (labels.isEmpty()) {
            labels.add("USB: no Seek camera attached (OTG)");
            actions.add(() -> toast("Plug the Seek Thermal camera into the phone (USB OTG)"));
        }
        labels.add("pyontrust gateway: " + s.gatewayUrl);
        actions.add(this::useGateway);
        labels.add("Change gateway address…");
        actions.add(this::gatewayDialog);
        labels.add("Open snapshot / recording…");
        actions.add(() -> startActivity(new Intent(this, GalleryActivity.class)));
        String err = sourceError;
        new AlertDialog.Builder(this).setTitle(err == null ? "Image source" : "Image source — ⚠ " + err)
                .setItems(labels.toArray(new String[0]), (d, w) -> actions.get(w).run()).show();
    }

    private void gatewayDialog() {
        Form f = new Form(this);
        EditText url = f.text("Gateway URL", s.gatewayUrl);
        f.note("Over the USB cable: run  adb reverse tcp:5210 tcp:5210  on the PC (android-thermal/build.sh install does it) "
                + "and use http://127.0.0.1:5210. Over Wi-Fi: http://<PC address>:5210.");
        new AlertDialog.Builder(this).setTitle("pyontrust gateway").setView(f.view)
                .setPositiveButton("Connect", (d, w) -> {
                    s.gatewayUrl = url.getText().toString().trim();
                    useGateway();
                }).setNegativeButton("Cancel", null).show();
    }

    private void paletteDialog() {
        new AlertDialog.Builder(this).setTitle("Palette")
                .setSingleChoiceItems(Palette.NAMES, s.palette, (d, w) -> { s.palette = w; s.save(); d.dismiss(); }).show();
    }

    private void rangeDialog() {
        Form f = new Form(this);
        CheckBox auto = f.check("Automatic range (1 … 99.7 % of the scene)", s.autoRange);
        EditText span = f.number("Minimum span (K)", s.minSpan);
        f.header("Manual range (" + s.unit() + ")");
        EditText lo = f.number("Low", s.disp(s.manualLo));
        EditText hi = f.number("High", s.disp(s.manualHi));
        f.button("Lock to the current range", v -> {
            lo.setText(Form.fmt(Math.round(s.disp(proc.rangeLo) * 10) / 10f));
            hi.setText(Form.fmt(Math.round(s.disp(proc.rangeHi) * 10) / 10f));
            auto.setChecked(false);
        });
        f.header("Isotherm (colour only a temperature band)");
        Spinner iso = f.spinner("Mode", new String[]{"Off", "Above", "Below", "Between"}, s.isoMode);
        EditText isoLo = f.number("Threshold / low (" + s.unit() + ")", s.disp(s.isoLo));
        EditText isoHi = f.number("High (" + s.unit() + ", Between)", s.disp(s.isoHi));
        new AlertDialog.Builder(this).setTitle("Range & isotherm").setView(f.view)
                .setPositiveButton("Apply", (d, w) -> {
                    s.autoRange = auto.isChecked();
                    s.minSpan = Math.max(0.1f, Form.num(span, s.minSpan));
                    s.manualLo = s.fromDisp(Form.num(lo, s.disp(s.manualLo)));
                    s.manualHi = s.fromDisp(Form.num(hi, s.disp(s.manualHi)));
                    s.isoMode = iso.getSelectedItemPosition();
                    s.isoLo = s.fromDisp(Form.num(isoLo, s.disp(s.isoLo)));
                    s.isoHi = s.fromDisp(Form.num(isoHi, s.disp(s.isoHi)));
                    s.save();
                }).setNegativeButton("Cancel", null).show();
    }

    private static final String[] TOOLS = {"— (tap = read spot, drag = move region)", "Point", "Area (rectangle)", "Line (profile)", "Delete region"};
    private static final String[] TOOL_SHORT = {"—", "Point", "Area", "Line", "Delete"};

    private void toolDialog() {
        List<String> items = new ArrayList<>();
        for (String t : TOOLS) items.add(t);
        items.add("Clear all regions");
        items.add("Import regions from the gateway");
        items.add("Copy regions to the gateway");
        new AlertDialog.Builder(this).setTitle("Measuring tool").setItems(items.toArray(new String[0]), (d, w) -> {
            if (w < TOOLS.length) {
                view.tool = w;
                btnTool.setText("Tool: " + TOOL_SHORT[w]);
            } else if (w == TOOLS.length) {
                if (tracker.running() || measurement != null) { toast("Stop tracking / measuring first"); return; }
                regions.clear();
                saveRegions();
            } else if (w == TOOLS.length + 1) {
                importRegions();
            } else {
                exportRegions();
            }
        }).show();
    }

    private void saveRegions() { s.saveRegions(Region.toJson(regions)); }

    private boolean regionsLocked() {
        if (tracker.running() || measurement != null) {
            toast("Regions are fixed while tracking / measuring (they are the CSV / report columns)");
            return true;
        }
        return false;
    }

    @Override
    public void onRegionAdded(Region r) {
        if (regionsLocked()) return;
        r.name = Region.nextName(regions, r.kind);
        regions.add(r);
        saveRegions();
        view.selected = r;
        if (r.isLine() && chartMode != 2) { chartMode = 2; chart.setVisibility(View.VISIBLE); }
        refreshChart();
    }

    @Override public void onRegionChanged(Region r) { saveRegions(); }

    @Override
    public void onRegionDeleted(Region r) {
        if (regionsLocked()) return;
        regions.remove(r);
        saveRegions();
    }

    @Override
    public void onRegionSelected(Region r) {
        if (r != null && r.isLine() && chartMode == 2) refreshChart();
    }

    @Override
    public void onRegionLongPress(Region r) {
        Form f = new Form(this);
        f.note(r.kind + "  at (" + r.x + ", " + r.y + ")" + (r.isPoint() ? "" : "  size " + r.w + " × " + r.h));
        EditText name = f.text("Name", r.name);
        EditText warn = f.number("Warn limit (" + s.unit() + ")", s.disp(r.warnC));
        EditText max = f.number("Max limit (" + s.unit() + ")", s.disp(r.maxC));
        CheckBox al = f.check("Alarm when the max limit is reached", r.alarm);
        new AlertDialog.Builder(this).setTitle("Region " + r.name).setView(f.view)
                .setPositiveButton("Save", (d, w) -> {
                    String nm = name.getText().toString().trim();
                    if (!nm.matches("[A-Za-z0-9_.\\-]{1,24}")) { toast("Name: 1–24 letters / digits / _ . -"); return; }
                    for (Region o : regions) if (o != r && o.name.equals(nm)) { toast("Name already used"); return; }
                    float wv = s.fromDisp(Form.num(warn, s.disp(r.warnC))), mv = s.fromDisp(Form.num(max, s.disp(r.maxC)));
                    if (wv > mv) { toast("Warn limit must not exceed the max limit"); return; }
                    if (!tracker.running() && measurement == null) r.name = nm;
                    r.warnC = wv;
                    r.maxC = mv;
                    r.alarm = al.isChecked();
                    saveRegions();
                })
                .setNeutralButton("Delete", (d, w) -> onRegionDeleted(r))
                .setNegativeButton("Cancel", null).show();
    }

    private void importRegions() {
        GatewaySource g = new GatewaySource(s.gatewayUrl);
        new Thread(() -> {
            try {
                JSONArray a = g.regions();
                List<Region> got = new ArrayList<>();
                for (int i = 0; i < a.length(); i++) got.add(Region.fromJson(a.getJSONObject(i)));
                post(() -> {
                    if (regionsLocked()) return;
                    regions.clear();
                    regions.addAll(got);
                    saveRegions();
                    toast("Imported " + got.size() + " regions from the gateway");
                });
            } catch (Exception e) {
                post(() -> toast("Import failed: " + e.getMessage()));
            }
        }).start();
    }

    private void exportRegions() {
        GatewaySource g = new GatewaySource(s.gatewayUrl);
        List<Region> copy = new ArrayList<>(regions);
        new Thread(() -> {
            int ok = 0;
            String err = null;
            for (Region r : copy) {
                if (r.isLine()) continue;                       // the PC workspace has no lines
                try {
                    g.post("/thermal/api/regions", new JSONObject().put("kind", r.kind).put("name", r.name)
                            .put("x", r.x).put("y", r.y).put("w", r.w).put("h", r.h)
                            .put("warn_c", r.warnC).put("max_c", r.maxC));
                    ok++;
                } catch (Exception e) {
                    err = e.getMessage();
                }
            }
            int n = ok;
            String e = err;
            post(() -> toast("Copied " + n + " regions to the gateway" + (e == null ? "" : " — " + e)));
        }).start();
    }

    // ── freeze / snapshot / recording ────────────────────────────────

    private void toggleFreeze() {
        if (!frozen) {
            Frame f = proc.apparent;
            if (f == null) return;
            frozenApparent = f.copy();
            frozen = true;
            btnFreeze.setText("Live");
        } else {
            FrameSource src = source;
            if (src instanceof ThrFile.Playback) ((ThrFile.Playback) src).paused = false;
            frozen = false;
            btnFreeze.setText("Freeze");
        }
    }

    private void snapshot() {
        Frame shown = view.frame();
        Frame app = frozen ? frozenApparent : proc.apparent;
        if (shown == null || app == null) { toast("No image yet"); return; }
        Bitmap b = view.renderToBitmap();
        String name = "IMG_" + stamp();
        File dir = dir("snapshots");
        try {
            File png = new File(dir, name + ".png");
            try (FileOutputStream o = new FileOutputStream(png)) { b.compress(Bitmap.CompressFormat.PNG, 100, o); }
            ThrFile.writeSingle(new File(dir, name + ThrFile.EXT), app, meta());
            boolean gallery = saveToMediaStore(b, name);
            toast("Snapshot saved" + (gallery ? " (also in the phone gallery)" : "") + " — radiometric, re-measurable in Gallery");
        } catch (Exception e) {
            toast("Snapshot failed: " + e.getMessage());
        }
    }

    private boolean saveToMediaStore(Bitmap b, String name) {
        if (Build.VERSION.SDK_INT < 29) return false;
        try {
            ContentValues v = new ContentValues();
            v.put(MediaStore.Images.Media.DISPLAY_NAME, name + ".png");
            v.put(MediaStore.Images.Media.MIME_TYPE, "image/png");
            v.put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/pyontrust Thermal");
            Uri u = getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, v);
            if (u == null) return false;
            try (OutputStream o = getContentResolver().openOutputStream(u)) { b.compress(Bitmap.CompressFormat.PNG, 100, o); }
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    private JSONObject meta() {
        JSONObject m = new JSONObject();
        try {
            FrameSource src = source;
            m.put("source", src == null ? "" : src.name()).put("time", System.currentTimeMillis())
                    .put("emissivity_at_capture", s.emissivity).put("reflected_c", s.reflectedC)
                    .put("palette", Palette.NAMES[s.palette]).put("regions", new JSONArray(Region.toJson(regions)))
                    .put("note", "°C before emissivity correction (apparent), calibration applied");
        } catch (Exception ignored) { }
        return m;
    }

    private void toggleRecording() {
        if (recorder != null) { stopRecording(true); return; }
        Frame f = proc.apparent;
        if (f == null || source == null || source.isPlayback()) { toast("Recording needs a live image"); return; }
        try {
            recordFile = new File(dir("recordings"), "REC_" + stamp() + ThrFile.EXT);
            lastRecordMs = 0;
            recorder = new ThrFile.Writer(recordFile, f.w, f.h, meta());
            btnRec.setText("■ Stop rec");
        } catch (Exception e) {
            toast("Cannot record: " + e.getMessage());
        }
    }

    private void stopRecording(boolean tell) {
        ThrFile.Writer w = recorder;
        recorder = null;
        if (w == null) return;
        try { w.close(); } catch (Exception ignored) { }
        if (btnRec != null) btnRec.setText("● Rec");
        if (tell) toast("Recorded " + w.frames + " radiometric frames — Gallery ▸ " + recordFile.getName());
    }

    void openRecording(File f) {
        ThrFile.Playback p = new ThrFile.Playback(f);
        setSource(p);
        btnFreeze.setText("Freeze");
    }

    // ── tracking ─────────────────────────────────────────────────────

    private void toggleTracking() {
        if (tracker.running()) {
            tracker.stop();
            btnTrack.setText("Track");
            File csv = tracker.csv;
            new AlertDialog.Builder(this).setTitle("Tracking stopped")
                    .setMessage(tracker.samples() + " samples\n" + csv.getName())
                    .setPositiveButton("Share CSV", (d, w) -> FilesProvider.share(this, csv))
                    .setNeutralButton("Open", (d, w) -> FilesProvider.view(this, csv))
                    .setNegativeButton("Close", null).show();
            return;
        }
        Form f = new Form(this);
        EditText iv = f.number("Interval (s)", s.trackIntervalS);
        f.note(regions.isEmpty() ? "No regions: only the frame min / max are logged. Add points or areas with Tools first."
                : regions.size() + " regions + frame min / max are logged to CSV (same columns as the PC).");
        new AlertDialog.Builder(this).setTitle("Start tracking").setView(f.view)
                .setPositiveButton("Start", (d, w) -> {
                    s.trackIntervalS = Math.max(0.1f, Form.num(iv, s.trackIntervalS));
                    s.save();
                    try {
                        tracker.start(regions, s.trackIntervalS, dir("tracking"));
                        btnTrack.setText("■ Stop track");
                        chartMode = 1;
                        chart.setVisibility(View.VISIBLE);
                        refreshChart();
                    } catch (Exception e) {
                        toast("Cannot start: " + e.getMessage());
                    }
                }).setNegativeButton("Cancel", null).show();
    }

    private void toggleChart() {
        chartMode = (chartMode + 1) % 4;
        chart.setVisibility(chartMode == 0 ? View.GONE : View.VISIBLE);
        refreshChart();
    }

    private void refreshChart() {
        if (chartMode == 1) {
            chart.showTrend(tracker.running() ? "Trend (" + tracker.samples() + " samples) — tap: next chart"
                    : tracker.samples() > 0 ? "Trend (last session)" : "Trend — start Track", tracker.columns, tracker.rows);
        } else if (chartMode == 2) {
            Region line = view.selected != null && view.selected.isLine() ? view.selected : null;
            if (line == null) for (Region r : regions) if (r.isLine()) line = r;
            if (line == null) chart.showProfile("Line profile — add a line with Tools ▸ Line", null);
            else chart.showProfile("Profile " + line.name + ": min " + s.fmt(line.rMin) + "  max " + s.fmt(line.rMax)
                    + "  ⌀ " + s.fmt(line.rMean), line.profile);
        } else if (chartMode == 3) {
            chart.showHistogram(view.frame());
        }
    }

    // ── measurement ──────────────────────────────────────────────────

    private void measureDialog() {
        Measurement running = measurement;
        if (running != null) {
            new AlertDialog.Builder(this).setTitle("Measurement running").setMessage(running.phase)
                    .setPositiveButton("Stop", (d, w) -> { running.abort(); finishMeasurement(running); })
                    .setNegativeButton("Continue", null).show();
            return;
        }
        Form f = new Form(this);
        Spinner mode = f.spinner("Mode", Measurement.MODES, java.util.Arrays.asList(Measurement.MODES).indexOf(s.measMode));
        EditText board = f.text("Board / DUT id", s.boardId);
        EditText dur = f.number("Duration (s) — continuous", s.measDuration);
        EditText iv = f.number("Capture interval (s)", s.measInterval);
        EditText gmax = f.number("Global max limit (°C)", s.measGlobalMax);
        EditText grad = f.number("Max gradient (°C/mm, 0 = off)", s.measMaxGradient);
        EditText pitch = f.number("Pixel pitch (mm on the target)", s.measPixelPitch);
        f.header("Soak");
        EditText sw = f.number("Stable window (s)", s.soakWindow);
        EditText st = f.number("Stable threshold (°C)", s.soakThreshold);
        EditText sto = f.number("Timeout (s)", s.soakTimeout);
        f.header("Delta (baseline → stimulus)");
        EditText db = f.number("Baseline frames", s.deltaBaseline);
        EditText dp = f.number("Pause for the stimulus (s)", s.deltaPause);
        EditText ds = f.number("Stimulus frames", s.deltaStimulus);
        f.note("Zones = your regions (" + regions.size() + "), judged against their max limits. "
                + "The report (HTML) is saved in Gallery ▸ Reports.");
        new AlertDialog.Builder(this).setTitle("Thermal measurement").setView(f.view)
                .setPositiveButton("Start", (d, w) -> {
                    s.measMode = Measurement.MODES[mode.getSelectedItemPosition()];
                    s.boardId = board.getText().toString().trim();
                    s.measDuration = Math.max(1, Form.num(dur, s.measDuration));
                    s.measInterval = Math.max(0.05f, Form.num(iv, s.measInterval));
                    s.measGlobalMax = Form.num(gmax, s.measGlobalMax);
                    s.measMaxGradient = Math.max(0, Form.num(grad, s.measMaxGradient));
                    s.measPixelPitch = Math.max(0.001f, Form.num(pitch, s.measPixelPitch));
                    s.soakWindow = Math.max(1, Form.num(sw, s.soakWindow));
                    s.soakThreshold = Math.max(0.01f, Form.num(st, s.soakThreshold));
                    s.soakTimeout = Math.max(s.soakWindow, Form.num(sto, s.soakTimeout));
                    s.deltaBaseline = (int) Math.max(1, Form.num(db, s.deltaBaseline));
                    s.deltaPause = Math.max(0, Form.num(dp, s.deltaPause));
                    s.deltaStimulus = (int) Math.max(1, Form.num(ds, s.deltaStimulus));
                    s.save();
                    if (source == null || source.isPlayback() || frozen) { toast("Measurements need a live image"); return; }
                    measurement = new Measurement(s, regions);
                    btnMeasure.setText("■ Measuring");
                }).setNegativeButton("Cancel", null).show();
    }

    /** Called on the worker thread (or UI on abort): write the report, show the verdict. */
    private void finishMeasurement(Measurement m) {
        if (measurement != m) return;
        measurement = null;
        post(() -> {
            btnMeasure.setText("Measure");
            File report = null;
            try {
                report = Report.write(dir("reports"), m, s, view.renderToBitmap(), source == null ? "" : source.name());
            } catch (Exception e) {
                toast("Report failed: " + e.getMessage());
            }
            File rep = report;
            AlertDialog.Builder b = new AlertDialog.Builder(this).setTitle(m.passed ? "✔ PASS" : "✕ FAIL")
                    .setMessage(m.summary(s)).setNegativeButton("Close", null);
            if (rep != null) {
                b.setPositiveButton("Open report", (d, w) -> FilesProvider.view(this, rep));
                b.setNeutralButton("Share", (d, w) -> FilesProvider.share(this, rep));
            }
            b.show();
        });
    }

    // ── settings ─────────────────────────────────────────────────────

    private static final String[] MATERIALS = {"Custom", "Black body / matte paint 0.95", "Human skin 0.98", "Water 0.96",
            "PCB solder mask 0.90", "Kapton / electrical tape 0.95", "Plastic (ABS, PVC) 0.93", "Rubber 0.95",
            "Glass 0.92", "Ceramic 0.92", "Paper 0.93", "Wood 0.90", "Concrete / brick 0.92", "Anodised aluminium 0.77",
            "Oxidised steel 0.80", "Oxidised copper 0.65", "Bare aluminium 0.09", "Polished copper 0.03"};

    private void settingsDialog() {
        Form f = new Form(this);
        FrameSource src = source;

        f.header("Measurement corrections");
        Spinner mat = f.spinner("Material", MATERIALS, 0);
        EditText eps = f.number("Emissivity ε (1 = off)", s.emissivity);
        EditText refl = f.number("Reflected temperature (" + s.unit() + ")", s.disp(s.reflectedC));
        mat.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(android.widget.AdapterView<?> p, View v, int pos, long id) {
                if (pos > 0) eps.setText(MATERIALS[pos].substring(MATERIALS[pos].lastIndexOf(' ') + 1));
            }

            @Override public void onNothingSelected(android.widget.AdapterView<?> p) { }
        });
        f.note("Shiny metal reads far too cold — put matte tape / paint on it, or set ε. ε applies live and to saved images.");

        f.header("Calibration (" + (src == null ? "no source" : src.name()) + ")");
        TextView calInfo = f.note(src == null ? "" : s.calibrationInfo(src.calibrationKey()));
        EditText ref = f.number("Reference temperature (" + s.unit() + ")", s.disp(24f));
        f.note("Aim at a surface of known temperature filling the image (e.g. a contact-thermometer reading), then Calibrate. "
                + "The image median is shifted to the reference (pyontrust one-point calibration).");
        f.button("Calibrate now", v -> calibrate(s.fromDisp(Form.num(ref, s.disp(24f))), calInfo));
        f.button("Clear calibration", v -> {
            if (source != null) { s.clearCalibration(source.calibrationKey()); calInfo.setText("not calibrated"); }
        });
        f.button("Learn flat-field (aim at a uniform surface)", v -> flatField(false));
        f.button("Clear flat-field", v -> flatField(true));

        f.header("View");
        CheckBox fahr = f.check("Fahrenheit", s.fahrenheit);
        CheckBox smooth = f.check("Edge-preserving smoothing", s.smoothing);
        Spinner nr = f.spinner("Noise reduction (temporal)", new String[]{"Off", "Low", "High"}, s.noiseReduction);
        Spinner rot = f.spinner("Rotate", new String[]{"0°", "90°", "180°", "270°"}, s.rotation / 90);
        CheckBox mirror = f.check("Flip horizontal", s.mirror);
        CheckBox flipV = f.check("Flip vertical", s.flipV);
        CheckBox hot = f.check("Hottest spot marker", s.showHot);
        CheckBox cold = f.check("Coldest spot marker", s.showCold);
        CheckBox center = f.check("Centre spot", s.showCenter);
        CheckBox scale = f.check("Colour scale", s.showScale);

        f.header("Alarms");
        CheckBox hiOn = f.check("High alarm", s.alarmHighOn);
        EditText hiV = f.number("High (" + s.unit() + ")", s.disp(s.alarmHigh));
        CheckBox loOn = f.check("Low alarm", s.alarmLowOn);
        EditText loV = f.number("Low (" + s.unit() + ")", s.disp(s.alarmLow));
        CheckBox snd = f.check("Sound", s.alarmSound);
        CheckBox vib = f.check("Vibrate", s.alarmVibrate);
        f.note("Regions also alarm when they reach their own max limit (long-press a region).");

        f.header("Recording");
        EditText rec = f.number("Record every (s, 0 = every frame)", s.recordIntervalS);

        f.header("Sources");
        CheckBox pref = f.check("Prefer the USB camera when attached", s.preferUsb);
        EditText gw = f.text("Gateway URL", s.gatewayUrl);
        f.header("Advanced: raw → °C (USB camera)");
        EditText ro = f.number("Raw offset (counts)", s.rawOffset);
        EditText rs = f.number("Raw scale (counts / °C)", s.rawScale);
        f.note("T = (raw − offset) / scale, then the calibration offset — identical to pyontrust on the PC.");

        new AlertDialog.Builder(this).setTitle("Settings").setView(f.view)
                .setPositiveButton("Save", (d, w) -> {
                    s.emissivity = Math.max(0.01f, Math.min(1f, Form.num(eps, s.emissivity)));
                    s.reflectedC = s.fromDisp(Form.num(refl, s.disp(s.reflectedC)));
                    s.smoothing = smooth.isChecked();
                    s.noiseReduction = nr.getSelectedItemPosition();
                    int newRot = rot.getSelectedItemPosition() * 90;
                    if ((newRot != s.rotation || mirror.isChecked() != s.mirror || flipV.isChecked() != s.flipV) && !regions.isEmpty()) {
                        toast("Rotation changed — region positions refer to the new orientation");
                    }
                    s.rotation = newRot;
                    s.mirror = mirror.isChecked();
                    s.flipV = flipV.isChecked();
                    s.showHot = hot.isChecked();
                    s.showCold = cold.isChecked();
                    s.showCenter = center.isChecked();
                    s.showScale = scale.isChecked();
                    s.alarmHighOn = hiOn.isChecked();
                    s.alarmHigh = s.fromDisp(Form.num(hiV, s.disp(s.alarmHigh)));
                    s.alarmLowOn = loOn.isChecked();
                    s.alarmLow = s.fromDisp(Form.num(loV, s.disp(s.alarmLow)));
                    s.alarmSound = snd.isChecked();
                    s.alarmVibrate = vib.isChecked();
                    s.recordIntervalS = Math.max(0, Form.num(rec, s.recordIntervalS));
                    s.preferUsb = pref.isChecked();
                    s.gatewayUrl = gw.getText().toString().trim();
                    s.rawOffset = Form.num(ro, s.rawOffset);
                    s.rawScale = Math.max(0.01f, Form.num(rs, s.rawScale));
                    s.fahrenheit = fahr.isChecked();     // last: the fields above were read in the old unit
                    s.save();
                    proc.reset();
                }).setNegativeButton("Cancel", null).show();
    }

    private void calibrate(float refC, TextView infoView) {
        FrameSource src = source;
        Frame app = proc.apparent;
        if (src == null || src.isPlayback() || app == null) { toast("Calibration needs a live image"); return; }
        if (refC < -60 || refC > 400) { toast("Reference out of range (-60 … 400 °C)"); return; }
        float old = s.calibrationOffset(src.calibrationKey());
        float rawMedian = app.median() - old;
        float off = Math.round((refC - rawMedian) * 1000) / 1000f;
        s.setCalibration(src.calibrationKey(), off, refC);
        proc.reset();
        infoView.setText(s.calibrationInfo(src.calibrationKey()));
        toast(String.format(Locale.US, "Calibrated: offset %+.2f °C", off));
    }

    private void flatField(boolean clear) {
        FrameSource src = source;
        if (src == null || !src.supportsFlatField() || !sourceOpen) { toast("Flat-field needs the live camera"); return; }
        if (tracker.running() || measurement != null) { toast("Stop tracking / measuring first"); return; }
        if (!clear) toast("Learning flat-field — keep the camera on the uniform surface…");
        workerTasks.add(() -> {
            try {
                String msg;
                if (clear) { src.clearFlatField(); msg = "Flat-field cleared"; }
                else msg = src.captureFlatField(20);
                proc.reset();
                post(() -> toast(msg));
            } catch (Exception e) {
                post(() -> toast("Flat-field failed: " + e.getMessage()));
            }
        });
    }
}
