package com.pyontrust.thermal;

/** Colour palettes as 256-entry ARGB lookup tables (built from control points). */
final class Palette {
    static final String[] NAMES = {"Inferno", "Iron", "Rainbow", "White hot", "Black hot",
            "Arctic", "Lava", "Medical", "Grey red"};

    private static final int[][] STOPS = {
            {0x000004, 0x320a5e, 0x781c6d, 0xbc3754, 0xed6925, 0xfbb61a, 0xfcffa4},          // inferno
            {0x000010, 0x2c0a6e, 0x8a0f8f, 0xd2303b, 0xf5761a, 0xfbc63a, 0xfffff0},          // iron
            {0x200060, 0x0000ff, 0x00c0ff, 0x00ff60, 0xffff00, 0xff8000, 0xff0000, 0xffffff}, // rainbow
            {0x000000, 0xffffff},                                                            // white hot
            {0xffffff, 0x000000},                                                            // black hot
            {0x05051e, 0x10307a, 0x2c7fc0, 0x9ad8ef, 0xf6e3a2, 0xf6a03c, 0xffffff},          // arctic
            {0x0a0a28, 0x1d4b6e, 0x2aa198, 0xd8c040, 0xe85a20, 0xa00000, 0xffffd0},          // lava
            {0x000000, 0x0000a0, 0x00a0a0, 0x00c000, 0xc0c000, 0xc00000, 0xffffff},          // medical
            {0x000000, 0x808080, 0xd0d0d0, 0xff6040, 0xff0000},                              // grey red
    };

    private static final int[][] CACHE = new int[NAMES.length][];

    static int[] lut(int index) {
        index = Math.max(0, Math.min(NAMES.length - 1, index));
        if (CACHE[index] == null) CACHE[index] = build(STOPS[index]);
        return CACHE[index];
    }

    private static int[] build(int[] stops) {
        int[] lut = new int[256];
        int segs = stops.length - 1;
        for (int i = 0; i < 256; i++) {
            float pos = i / 255f * segs;
            int s = Math.min(segs - 1, (int) pos);
            float f = pos - s;
            int a = stops[s], b = stops[s + 1];
            int r = Math.round(((a >> 16) & 255) * (1 - f) + ((b >> 16) & 255) * f);
            int g = Math.round(((a >> 8) & 255) * (1 - f) + ((b >> 8) & 255) * f);
            int bl = Math.round((a & 255) * (1 - f) + (b & 255) * f);
            lut[i] = 0xff000000 | (r << 16) | (g << 8) | bl;
        }
        return lut;
    }

    private Palette() { }
}
