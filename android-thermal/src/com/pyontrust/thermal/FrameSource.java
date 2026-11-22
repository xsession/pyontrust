package com.pyontrust.thermal;

/** Something that produces radiometric frames: the USB camera, the gateway, or a recording. */
interface FrameSource {
    /** Short label for the status bar, e.g. "Seek Compact (USB)". */
    String name();

    void open() throws Exception;

    /** Blocks until the next frame (°C, before any user calibration offset). */
    Frame grab() throws Exception;

    void close();

    /** Key under which the user's one-point calibration offset is stored. */
    String calibrationKey();

    /** True for recordings: frames are already calibrated and corrected. */
    boolean isPlayback();

    /** Flat-field (vignetting) support — only the local USB camera has it. */
    boolean supportsFlatField();

    String captureFlatField(int frames) throws Exception;

    void clearFlatField();
}
