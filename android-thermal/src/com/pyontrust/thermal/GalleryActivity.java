package com.pyontrust.thermal;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import android.widget.BaseAdapter;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.TextView;

import java.io.File;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/**
 * Saved work: radiometric snapshots (re-measure them), recordings (play back),
 * measurement reports (HTML) and tracking CSVs — open, share or delete.
 */
public class GalleryActivity extends Activity {
    private static final String[][] SECTIONS = {
            {"snapshots", "Snapshots"}, {"recordings", "Recordings"}, {"reports", "Reports"}, {"tracking", "Tracking CSV"}};

    private final List<File> items = new ArrayList<>();
    private final List<String> headers = new ArrayList<>();   // non-null entries are section headers
    private BaseAdapter adapter;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        ListView lv = new ListView(this);
        lv.setBackgroundColor(0xff11111b);
        adapter = new BaseAdapter() {
            @Override public int getCount() { return items.size(); }
            @Override public Object getItem(int i) { return items.get(i); }
            @Override public long getItemId(int i) { return i; }

            @Override
            public View getView(int i, View convert, ViewGroup parent) {
                return row(i);
            }
        };
        lv.setAdapter(adapter);
        lv.setOnItemClickListener((p, v, i, id) -> open(i));
        lv.setOnItemLongClickListener((p, v, i, id) -> { actions(i); return true; });
        setContentView(lv);
        reload();
    }

    private void reload() {
        items.clear();
        headers.clear();
        File root = FilesProvider.root(this);
        for (String[] sec : SECTIONS) {
            File[] fs = new File(root, sec[0]).listFiles();
            List<File> show = new ArrayList<>();
            if (fs != null) {
                Arrays.sort(fs, (a, b) -> Long.compare(b.lastModified(), a.lastModified()));
                for (File f : fs) {
                    // a snapshot is a .png + .thr pair: list the picture only
                    if (sec[0].equals("snapshots") && f.getName().endsWith(ThrFile.EXT)
                            && new File(f.getParent(), base(f) + ".png").exists()) continue;
                    show.add(f);
                }
            }
            items.add(null);
            headers.add(sec[1] + " (" + show.size() + ")");
            for (File f : show) { items.add(f); headers.add(null); }
        }
        adapter.notifyDataSetChanged();
    }

    private static String base(File f) {
        String n = f.getName();
        int dot = n.lastIndexOf('.');
        return dot < 0 ? n : n.substring(0, dot);
    }

    private View row(int i) {
        float dp = getResources().getDisplayMetrics().density;
        File f = items.get(i);
        if (f == null) {
            TextView h = new TextView(this);
            h.setText(headers.get(i));
            h.setTextColor(0xff89b4fa);
            h.setTextSize(15);
            h.setPadding((int) (12 * dp), (int) (14 * dp), 0, (int) (4 * dp));
            return h;
        }
        LinearLayout r = new LinearLayout(this);
        r.setPadding((int) (12 * dp), (int) (6 * dp), (int) (12 * dp), (int) (6 * dp));
        if (f.getName().endsWith(".png")) {
            ImageView iv = new ImageView(this);
            BitmapFactory.Options o = new BitmapFactory.Options();
            o.inSampleSize = 4;
            Bitmap b = BitmapFactory.decodeFile(f.getPath(), o);
            iv.setImageBitmap(b);
            iv.setAdjustViewBounds(true);
            r.addView(iv, new LinearLayout.LayoutParams((int) (80 * dp), (int) (60 * dp)));
        }
        TextView t = new TextView(this);
        t.setTextColor(0xffcdd6f4);
        String extra = "";
        if (f.getName().endsWith(ThrFile.EXT)) {
            try (ThrFile.Reader rd = new ThrFile.Reader(f)) { extra = "  ·  " + rd.frames + " frames " + rd.w + "×" + rd.h; } catch (Exception ignored) { }
        }
        t.setText(f.getName() + "\n" + new SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.US).format(new Date(f.lastModified()))
                + "  ·  " + (f.length() / 1024) + " kB" + extra);
        t.setPadding((int) (10 * dp), 0, 0, 0);
        r.addView(t);
        return r;
    }

    private File radiometric(File f) {
        if (f.getName().endsWith(ThrFile.EXT)) return f;
        File thr = new File(f.getParent(), base(f) + ThrFile.EXT);
        return thr.exists() ? thr : null;
    }

    private void open(int i) {
        File f = items.get(i);
        if (f == null) return;
        File thr = radiometric(f);
        if (thr != null) {
            startActivity(new Intent(this, MainActivity.class).putExtra(MainActivity.EXTRA_OPEN, thr.getPath())
                    .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP));
            finish();
        } else {
            FilesProvider.view(this, f);
        }
    }

    private void actions(int i) {
        File f = items.get(i);
        if (f == null) return;
        File thr = radiometric(f);
        List<String> labels = new ArrayList<>();
        List<Runnable> acts = new ArrayList<>();
        if (thr != null) { labels.add("Analyse (radiometric)"); acts.add(() -> open(i)); }
        labels.add("Open with…");
        acts.add(() -> FilesProvider.view(this, f));
        labels.add("Share");
        acts.add(() -> FilesProvider.share(this, thr != null && thr != f ? new File[]{f, thr} : new File[]{f}));
        labels.add("Delete");
        acts.add(() -> new AlertDialog.Builder(this).setTitle("Delete " + f.getName() + "?")
                .setMessage("This cannot be undone.")
                .setPositiveButton("Delete", (d, w) -> {
                    //noinspection ResultOfMethodCallIgnored
                    f.delete();
                    if (thr != null && thr != f) //noinspection ResultOfMethodCallIgnored
                        thr.delete();
                    reload();
                }).setNegativeButton("Cancel", null).show());
        new AlertDialog.Builder(this).setTitle(f.getName())
                .setItems(labels.toArray(new String[0]), (d, w) -> acts.get(w).run()).show();
    }
}
