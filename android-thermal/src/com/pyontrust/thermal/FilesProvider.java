package com.pyontrust.thermal;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import android.webkit.MimeTypeMap;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.util.ArrayList;

/** Minimal read-only provider so saved images, CSVs and reports can be shared (no AndroidX). */
public class FilesProvider extends ContentProvider {
    static final String AUTHORITY = "com.pyontrust.thermal.files";

    static File root(Context c) {
        File d = c.getExternalFilesDir(null);
        return d != null ? d : c.getFilesDir();
    }

    static Uri uriFor(Context c, File f) {
        String rel = root(c).toURI().relativize(f.toURI()).getPath();
        return new Uri.Builder().scheme("content").authority(AUTHORITY).encodedPath("/" + Uri.encode(rel, "/")).build();
    }

    static String mime(File f) {
        String n = f.getName();
        String ext = n.substring(n.lastIndexOf('.') + 1).toLowerCase(java.util.Locale.US);
        if ("thr".equals(ext)) return "application/octet-stream";
        if ("csv".equals(ext)) return "text/csv";
        String m = MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext);
        return m != null ? m : "application/octet-stream";
    }

    /** Share one or more files with any app (mail, Drive, chat …). */
    static void share(Context c, File... files) {
        ArrayList<Uri> uris = new ArrayList<>();
        for (File f : files) if (f != null && f.isFile()) uris.add(uriFor(c, f));
        if (uris.isEmpty()) return;
        Intent i;
        if (uris.size() == 1) {
            i = new Intent(Intent.ACTION_SEND).setType(mime(files[0])).putExtra(Intent.EXTRA_STREAM, uris.get(0));
        } else {
            i = new Intent(Intent.ACTION_SEND_MULTIPLE).setType("*/*").putParcelableArrayListExtra(Intent.EXTRA_STREAM, uris);
        }
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        c.startActivity(Intent.createChooser(i, "Share").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
    }

    /** Open a file in a viewer app (HTML report in the browser, CSV in a sheet app …). */
    static void view(Context c, File f) {
        Intent i = new Intent(Intent.ACTION_VIEW).setDataAndType(uriFor(c, f), mime(f))
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        c.startActivity(Intent.createChooser(i, "Open with").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
    }

    private File fileFor(Uri uri) throws FileNotFoundException {
        File root = root(getContext());
        File f = new File(root, uri.getPath() == null ? "" : uri.getPath());
        try {
            if (!f.getCanonicalPath().startsWith(root.getCanonicalPath() + File.separator)) throw new FileNotFoundException();
        } catch (IOException e) {
            throw new FileNotFoundException();
        }
        if (!f.isFile()) throw new FileNotFoundException(uri.toString());
        return f;
    }

    @Override public boolean onCreate() { return true; }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        return ParcelFileDescriptor.open(fileFor(uri), ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String sel, String[] args, String sort) {
        try {
            File f = fileFor(uri);
            MatrixCursor c = new MatrixCursor(new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE});
            c.addRow(new Object[]{f.getName(), f.length()});
            return c;
        } catch (FileNotFoundException e) {
            return null;
        }
    }

    @Override
    public String getType(Uri uri) {
        try { return mime(fileFor(uri)); } catch (FileNotFoundException e) { return null; }
    }

    @Override public Uri insert(Uri uri, ContentValues v) { throw new UnsupportedOperationException(); }
    @Override public int delete(Uri uri, String s, String[] a) { throw new UnsupportedOperationException(); }
    @Override public int update(Uri uri, ContentValues v, String s, String[] a) { throw new UnsupportedOperationException(); }
}
