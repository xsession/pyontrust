package com.pyontrust.thermal;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.text.InputType;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;

import java.util.Locale;

/** Tiny programmatic form builder for the dialogs (no XML layouts in this app). */
final class Form {
    final Context c;
    final LinearLayout box;
    final ScrollView view;
    private final float dp;

    Form(Context c) {
        this.c = c;
        dp = c.getResources().getDisplayMetrics().density;
        box = new LinearLayout(c);
        box.setOrientation(LinearLayout.VERTICAL);
        int pad = (int) (18 * dp);
        box.setPadding(pad, (int) (8 * dp), pad, (int) (8 * dp));
        view = new ScrollView(c);
        view.addView(box);
    }

    TextView header(String text) {
        TextView t = new TextView(c);
        t.setText(text);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setTextColor(0xff89b4fa);
        t.setPadding(0, (int) (14 * dp), 0, (int) (2 * dp));
        box.addView(t);
        return t;
    }

    TextView note(String text) {
        TextView t = new TextView(c);
        t.setText(text);
        t.setTextSize(12);
        t.setTextColor(Color.GRAY);
        box.addView(t);
        return t;
    }

    private LinearLayout row(String label) {
        LinearLayout r = new LinearLayout(c);
        r.setOrientation(LinearLayout.HORIZONTAL);
        TextView t = new TextView(c);
        t.setText(label);
        r.addView(t, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        box.addView(r);
        return r;
    }

    EditText number(String label, float value) {
        EditText e = new EditText(c);
        e.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL | InputType.TYPE_NUMBER_FLAG_SIGNED);
        e.setText(fmt(value));
        e.setSelectAllOnFocus(true);
        row(label).addView(e, new LinearLayout.LayoutParams((int) (110 * dp), LinearLayout.LayoutParams.WRAP_CONTENT));
        return e;
    }

    EditText text(String label, String value) {
        EditText e = new EditText(c);
        e.setSingleLine(true);
        e.setText(value);
        if (label != null) {
            TextView t = new TextView(c);
            t.setText(label);
            box.addView(t);
        }
        box.addView(e);
        return e;
    }

    CheckBox check(String label, boolean value) {
        CheckBox cb = new CheckBox(c);
        cb.setText(label);
        cb.setChecked(value);
        box.addView(cb);
        return cb;
    }

    Spinner spinner(String label, String[] items, int selected) {
        Spinner sp = new Spinner(c);
        sp.setAdapter(new ArrayAdapter<>(c, android.R.layout.simple_spinner_dropdown_item, items));
        sp.setSelection(Math.max(0, Math.min(items.length - 1, selected)));
        row(label).addView(sp, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        return sp;
    }

    Button button(String label, View.OnClickListener l) {
        Button b = new Button(c);
        b.setText(label);
        b.setAllCaps(false);
        b.setOnClickListener(l);
        box.addView(b);
        return b;
    }

    static float num(EditText e, float fallback) {
        try {
            return Float.parseFloat(e.getText().toString().trim().replace(',', '.'));
        } catch (NumberFormatException ex) {
            return fallback;
        }
    }

    static String fmt(float v) {
        return v == Math.rint(v) && Math.abs(v) < 1e7 ? String.valueOf((long) v) : String.format(Locale.US, "%.3f", v).replaceAll("0+$", "");
    }
}
