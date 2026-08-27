/**
 * FlowLab — LabVIEW-style Visual Dataflow Experiment Designer
 *
 * A complete client-side block-diagram editor with:
 *  - Draggable blocks from a palette
 *  - Typed input/output ports with cubic-bezier wires
 *  - Pan & zoom canvas (mouse wheel + middle-click)
 *  - Properties panel for per-block config
 *  - Topological-sort execution via the Flask backend
 *  - Save / load / export diagrams as JSON
 *
 * All rendering is SVG-based for crispness at any zoom level.
 */
(function () {
  'use strict';

  // ══════════════════════════════════════════════════════════════
  // Block catalogue — every block the palette offers
  // ══════════════════════════════════════════════════════════════

  const BLOCK_CATALOGUE = [
    // ═══════════════════════════════════════════════════════════
    // INSTRUMENTS — Sources of data
    // ═══════════════════════════════════════════════════════════

    { cat: 'Instruments', type: 'simulated_power',  label: 'Simulated Meter',  icon: '🔌', colour: '#89b4fa',
      inputs: [], outputs: [{name:'trace', dtype:'power_trace'}],
      params: {sample_rate_hz:{type:'slider',default:1000,min:100,max:100000,step:100}, duration_s:{type:'slider',default:2,min:0.1,max:60,step:0.1}, base_current_a:{type:'number',default:0.001}, noise_a:{type:'number',default:0.0001}},
      hint: 'Generates synthetic current trace' },

    { cat: 'Instruments', type: 'csv_file', label: 'CSV File Reader', icon: '📄', colour: '#89b4fa',
      inputs: [], outputs: [{name:'trace', dtype:'power_trace'}],
      params: {path:{type:'text',default:'artifacts/trace.csv'}, time_col:{type:'text',default:'time_s'}, current_col:{type:'text',default:'current_a'}},
      hint: 'Load trace from CSV' },

    { cat: 'Instruments', type: 'csv_replay', label: 'CSV Replay', icon: '⏪', colour: '#89b4fa',
      inputs: [], outputs: [{name:'trace', dtype:'power_trace'}],
      params: {path:{type:'text',default:'artifacts/trace.csv'}, speed:{type:'slider',default:1.0,min:0.1,max:10,step:0.1}, loop:{type:'checkbox',default:false}},
      hint: 'Replay a CSV recording' },

    { cat: 'Instruments', type: 'aoi_camera', label: 'AOI Camera', icon: '📷', colour: '#89b4fa',
      inputs: [], outputs: [{name:'frame', dtype:'image'}],
      params: {mode:{type:'select',default:'simulated',options:['simulated','webcam','harvesters']}, width:{type:'number',default:640}, height:{type:'number',default:480}},
      hint: 'Grab AOI / webcam frame' },

    { cat: 'Instruments', type: 'seek_thermal', label: 'Thermal Camera', icon: '🌡️', colour: '#89b4fa',
      inputs: [], outputs: [{name:'thermal', dtype:'thermal_frame'}, {name:'temp_c', dtype:'number'}],
      params: {mode:{type:'select',default:'simulated',options:['simulated','seek']}, base_temp_c:{type:'number',default:25}, inject_hotspot:{type:'checkbox',default:false}},
      hint: 'Seek Thermal radiometric frame' },

    { cat: 'Instruments', type: 'ppk2_meter', label: 'PPK2 Meter', icon: '⚡', colour: '#89b4fa',
      inputs: [], outputs: [{name:'trace', dtype:'power_trace'}],
      params: {serial_port:{type:'text',default:''}, vdd_mv:{type:'number',default:3300}, sample_rate_hz:{type:'number',default:100000}, duration_s:{type:'number',default:2}},
      hint: 'Nordic PPK2 source-meter' },

    { cat: 'Instruments', type: 'ad3_dwf_meter', label: 'AD3 / DWF Meter', icon: '📟', colour: '#89b4fa',
      inputs: [], outputs: [{name:'trace', dtype:'power_trace'}],
      params: {device_index:{type:'number',default:0}, channel:{type:'number',default:0}, shunt_ohm:{type:'number',default:1.0}, sample_rate_hz:{type:'number',default:10000}, duration_s:{type:'number',default:2}, vdd_v:{type:'number',default:3.3}},
      hint: 'Analog Discovery 3 power meter' },

    { cat: 'Instruments', type: 'waveform_gen', label: 'Waveform Gen', icon: '〜', colour: '#89b4fa',
      inputs: [], outputs: [{name:'trace', dtype:'power_trace'}],
      params: {shape:{type:'select',default:'sine',options:['sine','square','triangle','sawtooth','dc','pulse','noise','chirp']}, frequency_hz:{type:'slider',default:100,min:1,max:10000,step:1}, amplitude:{type:'slider',default:1.0,min:0,max:10,step:0.01}, offset:{type:'slider',default:0,min:-5,max:5,step:0.01}, duty_cycle:{type:'slider',default:0.5,min:0,max:1,step:0.01}, duration_s:{type:'slider',default:1,min:0.01,max:60,step:0.01}, sample_rate_hz:{type:'slider',default:10000,min:100,max:100000,step:100}},
      hint: 'Generate arbitrary waveform' },

    { cat: 'Instruments', type: 'random_data', label: 'Random Data', icon: '🎲', colour: '#89b4fa',
      inputs: [], outputs: [{name:'data', dtype:'any'}],
      params: {distribution:{type:'select',default:'normal',options:['normal','uniform','poisson','exponential','beta']}, size:{type:'slider',default:1000,min:10,max:100000,step:10}, param1:{type:'number',default:0}, param2:{type:'number',default:1}},
      hint: 'Random data from statistical distributions' },

    // ── Android Phone Sensors (USB / ADB) ────────────────────
    { cat: 'Instruments', type: 'android_accel', label: 'Android Accel', icon: '📱', colour: '#89b4fa',
      inputs: [], outputs: [{name:'accel', dtype:'dict'},{name:'trace', dtype:'power_trace'}],
      params: {mode:{type:'select',default:'simulated',options:['simulated','adb','adb_bridge']}, duration_s:{type:'slider',default:1,min:0.1,max:30,step:0.1}, sample_rate_hz:{type:'slider',default:50,min:1,max:500,step:1}},
      hint: 'Android accelerometer — 3-axis m/s² via USB' },

    { cat: 'Instruments', type: 'android_gyro', label: 'Android Gyro', icon: '🌀', colour: '#89b4fa',
      inputs: [], outputs: [{name:'gyro', dtype:'dict'},{name:'trace', dtype:'power_trace'}],
      params: {mode:{type:'select',default:'simulated',options:['simulated','adb','adb_bridge']}, duration_s:{type:'slider',default:1,min:0.1,max:30,step:0.1}, sample_rate_hz:{type:'slider',default:50,min:1,max:500,step:1}},
      hint: 'Android gyroscope — 3-axis rad/s via USB' },

    { cat: 'Instruments', type: 'android_mag', label: 'Android Magnetometer', icon: '🧭', colour: '#89b4fa',
      inputs: [], outputs: [{name:'mag', dtype:'dict'},{name:'trace', dtype:'power_trace'}],
      params: {mode:{type:'select',default:'simulated',options:['simulated','adb','adb_bridge']}, duration_s:{type:'slider',default:1,min:0.1,max:30,step:0.1}, sample_rate_hz:{type:'slider',default:50,min:1,max:500,step:1}},
      hint: 'Android magnetometer — 3-axis µT via USB' },

    { cat: 'Instruments', type: 'android_mic', label: 'Android Mic', icon: '🎤', colour: '#89b4fa',
      inputs: [], outputs: [{name:'audio', dtype:'power_trace'},{name:'level_db', dtype:'number'}],
      params: {mode:{type:'select',default:'simulated',options:['simulated','adb','adb_bridge']}, duration_s:{type:'slider',default:2,min:0.1,max:60,step:0.1}, sample_rate:{type:'select',default:'16000',options:['8000','16000','22050','44100','48000']}},
      hint: 'Android microphone — audio capture via USB' },

    { cat: 'Instruments', type: 'android_proximity', label: 'Android Proximity', icon: '👋', colour: '#89b4fa',
      inputs: [], outputs: [{name:'distance', dtype:'number'},{name:'near', dtype:'bool'}],
      params: {mode:{type:'select',default:'simulated',options:['simulated','adb','adb_bridge']}},
      hint: 'Android proximity sensor — distance in cm' },

    { cat: 'Instruments', type: 'android_light', label: 'Android Light', icon: '☀️', colour: '#89b4fa',
      inputs: [], outputs: [{name:'lux', dtype:'number'}],
      params: {mode:{type:'select',default:'simulated',options:['simulated','adb','adb_bridge']}, duration_s:{type:'slider',default:1,min:0.1,max:30,step:0.1}},
      hint: 'Android ambient light sensor — lux' },

    { cat: 'Instruments', type: 'android_pressure', label: 'Android Barometer', icon: '🌤️', colour: '#89b4fa',
      inputs: [], outputs: [{name:'hpa', dtype:'number'}],
      params: {mode:{type:'select',default:'simulated',options:['simulated','adb','adb_bridge']}, duration_s:{type:'slider',default:1,min:0.1,max:30,step:0.1}},
      hint: 'Android barometric pressure — hPa' },

    { cat: 'Instruments', type: 'android_gps', label: 'Android GPS', icon: '📍', colour: '#89b4fa',
      inputs: [], outputs: [{name:'location', dtype:'dict'}],
      params: {mode:{type:'select',default:'simulated',options:['simulated','adb','adb_bridge']}},
      hint: 'Android GPS — lat, lon, alt, speed' },

    { cat: 'Instruments', type: 'android_battery', label: 'Android Battery', icon: '🔋', colour: '#89b4fa',
      inputs: [], outputs: [{name:'battery', dtype:'dict'}],
      params: {mode:{type:'select',default:'simulated',options:['simulated','adb','adb_bridge']}},
      hint: 'Android battery — level, voltage, temp, status' },

    { cat: 'Instruments', type: 'android_gravity', label: 'Android Gravity', icon: '⬇️', colour: '#89b4fa',
      inputs: [], outputs: [{name:'gravity', dtype:'dict'},{name:'trace', dtype:'power_trace'}],
      params: {mode:{type:'select',default:'simulated',options:['simulated','adb','adb_bridge']}, duration_s:{type:'slider',default:1,min:0.1,max:30,step:0.1}, sample_rate_hz:{type:'slider',default:50,min:1,max:500,step:1}},
      hint: 'Android gravity sensor — 3-axis m/s²' },

    { cat: 'Instruments', type: 'android_rotation', label: 'Android Rotation', icon: '🔄', colour: '#89b4fa',
      inputs: [], outputs: [{name:'rotation', dtype:'dict'},{name:'trace', dtype:'power_trace'}],
      params: {mode:{type:'select',default:'simulated',options:['simulated','adb','adb_bridge']}, duration_s:{type:'slider',default:1,min:0.1,max:30,step:0.1}, sample_rate_hz:{type:'slider',default:50,min:1,max:500,step:1}},
      hint: 'Android rotation vector — quaternion orientation' },

    { cat: 'Instruments', type: 'android_torch', label: 'Android Torch', icon: '🔦', colour: '#f9e2af',
      inputs: [], outputs: [{name:'ok', dtype:'bool'},{name:'state', dtype:'string'}],
      params: {mode:{type:'select',default:'simulated',options:['simulated','adb','adb_bridge']}, state:{type:'select',default:'on',options:['on','off']}},
      hint: 'Toggle Android flashlight (torch) on/off via ADB' },

    { cat: 'Instruments', type: 'lux_measure', label: 'Lux Measure', icon: '💡', colour: '#f9e2af',
      inputs: [], outputs: [{name:'result', dtype:'dict'},{name:'webcam_lux', dtype:'list'},{name:'android_lux', dtype:'list'},{name:'correlation', dtype:'number'}],
      params: {android_mode:{type:'select',default:'simulated',options:['simulated','adb','adb_bridge']}, n_cycles:{type:'slider',default:3,min:1,max:10,step:1}, torch_on_s:{type:'slider',default:3,min:0.5,max:15,step:0.5}, torch_off_s:{type:'slider',default:3,min:0.5,max:15,step:0.5}},
      hint: 'Parallel lux measurement — webcam + Android light sensor with torch cycling' },

    // ═══════════════════════════════════════════════════════════
    // ANALYSIS — Signal processing & measurements
    // ═══════════════════════════════════════════════════════════

    { cat: 'Analysis', type: 'stats', label: 'Statistics', icon: '📊', colour: '#a6e3a1',
      inputs: [{name:'trace', dtype:'power_trace'}], outputs: [{name:'result', dtype:'dict'}],
      params: {},
      hint: 'Mean, max, min, std, RMS of trace' },

    { cat: 'Analysis', type: 'filter', label: 'Low-Pass Filter', icon: '〰️', colour: '#a6e3a1',
      inputs: [{name:'trace', dtype:'power_trace'}], outputs: [{name:'filtered', dtype:'power_trace'}],
      params: {cutoff_hz:{type:'slider',default:50,min:1,max:10000,step:1}, order:{type:'slider',default:4,min:1,max:10,step:1}},
      hint: 'Butterworth low-pass filter' },

    { cat: 'Analysis', type: 'highpass_filter', label: 'High-Pass Filter', icon: '⫝', colour: '#a6e3a1',
      inputs: [{name:'trace', dtype:'power_trace'}], outputs: [{name:'filtered', dtype:'power_trace'}],
      params: {cutoff_hz:{type:'slider',default:10,min:1,max:10000,step:1}, order:{type:'slider',default:4,min:1,max:10,step:1}},
      hint: 'Butterworth high-pass filter' },

    { cat: 'Analysis', type: 'bandpass_filter', label: 'Band-Pass Filter', icon: '⧫', colour: '#a6e3a1',
      inputs: [{name:'trace', dtype:'power_trace'}], outputs: [{name:'filtered', dtype:'power_trace'}],
      params: {low_hz:{type:'slider',default:10,min:1,max:10000,step:1}, high_hz:{type:'slider',default:100,min:1,max:10000,step:1}, order:{type:'slider',default:4,min:1,max:10,step:1}},
      hint: 'Butterworth band-pass filter' },

    { cat: 'Analysis', type: 'fft_spectrum', label: 'FFT Spectrum', icon: '🌈', colour: '#a6e3a1',
      inputs: [{name:'trace', dtype:'power_trace'}], outputs: [{name:'spectrum', dtype:'dict'},{name:'peaks', dtype:'dict'}],
      params: {window:{type:'select',default:'hann',options:['hann','hamming','blackman','rectangular','kaiser']}, n_peaks:{type:'slider',default:5,min:1,max:50,step:1}},
      hint: 'FFT power spectral density + peak detection' },

    { cat: 'Analysis', type: 'moving_average', label: 'Moving Average', icon: '📉', colour: '#a6e3a1',
      inputs: [{name:'trace', dtype:'power_trace'}], outputs: [{name:'smoothed', dtype:'power_trace'}],
      params: {window_size:{type:'slider',default:50,min:2,max:1000,step:1}, method:{type:'select',default:'sma',options:['sma','ema','median']}},
      hint: 'Simple / exponential / median moving average' },

    { cat: 'Analysis', type: 'derivative', label: 'Derivative', icon: 'Δ', colour: '#a6e3a1',
      inputs: [{name:'trace', dtype:'power_trace'}], outputs: [{name:'dtrace', dtype:'power_trace'}],
      params: {order:{type:'select',default:'1',options:['1','2']}},
      hint: 'First or second derivative (rate of change)' },

    { cat: 'Analysis', type: 'integral', label: 'Integral', icon: '∫', colour: '#a6e3a1',
      inputs: [{name:'trace', dtype:'power_trace'}], outputs: [{name:'result', dtype:'dict'}],
      params: {method:{type:'select',default:'trapezoid',options:['trapezoid','simpson','cumulative']}},
      hint: 'Numerical integration (energy / charge)' },

    { cat: 'Analysis', type: 'threshold', label: 'Threshold Check', icon: '⚠️', colour: '#a6e3a1',
      inputs: [{name:'value', dtype:'any'}], outputs: [{name:'pass', dtype:'bool'}, {name:'value', dtype:'any'}],
      params: {metric:{type:'text',default:'avg_current_a'}, max_val:{type:'number',default:0.01}, min_val:{type:'number',default:0}},
      hint: 'Pass/fail threshold gate' },

    { cat: 'Analysis', type: 'window_slice', label: 'Window / Slice', icon: '✂️', colour: '#a6e3a1',
      inputs: [{name:'trace', dtype:'power_trace'}], outputs: [{name:'sliced', dtype:'power_trace'}],
      params: {start_s:{type:'number',default:0}, end_s:{type:'number',default:1}},
      hint: 'Extract a time window from trace' },

    { cat: 'Analysis', type: 'resample', label: 'Resample', icon: '🔄', colour: '#a6e3a1',
      inputs: [{name:'trace', dtype:'power_trace'}], outputs: [{name:'resampled', dtype:'power_trace'}],
      params: {target_rate_hz:{type:'number',default:1000}, method:{type:'select',default:'linear',options:['linear','nearest','cubic']}},
      hint: 'Resample trace to different rate' },

    { cat: 'Analysis', type: 'edge_detect', label: 'Edge Detect', icon: '📐', colour: '#a6e3a1',
      inputs: [{name:'trace', dtype:'power_trace'}], outputs: [{name:'edges', dtype:'dict'}],
      params: {threshold:{type:'number',default:0.001}, direction:{type:'select',default:'both',options:['rising','falling','both']}, min_width_s:{type:'number',default:0}},
      hint: 'Detect signal edges/transitions' },

    { cat: 'Analysis', type: 'histogram', label: 'Histogram', icon: '▊', colour: '#a6e3a1',
      inputs: [{name:'trace', dtype:'power_trace'}], outputs: [{name:'hist', dtype:'dict'}],
      params: {bins:{type:'slider',default:50,min:5,max:500,step:1}, density:{type:'checkbox',default:false}},
      hint: 'Amplitude distribution histogram' },

    { cat: 'Analysis', type: 'correlate', label: 'Cross-Correlate', icon: '⟷', colour: '#a6e3a1',
      inputs: [{name:'trace_a', dtype:'power_trace'},{name:'trace_b', dtype:'power_trace'}], outputs: [{name:'result', dtype:'dict'}],
      params: {normalize:{type:'checkbox',default:true}},
      hint: 'Cross-correlation between two traces' },

    // ── Vision / Inspection ──────────────────────────────────────
    { cat: 'Vision', type: 'thermal_analyze', label: 'Thermal Analyzer', icon: '🔥', colour: '#f38ba8',
      inputs: [{name:'thermal', dtype:'thermal_frame'}], outputs: [{name:'snapshot', dtype:'dict'}, {name:'heatmap', dtype:'image'}],
      params: {zones:{type:'textarea',default:'[]'}, colormap:{type:'select',default:'inferno',options:['inferno','jet','hot','rainbow','turbo']}},
      hint: 'Zone-based thermal analysis' },

    { cat: 'Vision', type: 'aoi_inspect', label: 'AOI Inspector', icon: '🔍', colour: '#f38ba8',
      inputs: [{name:'frame', dtype:'image'}], outputs: [{name:'result', dtype:'dict'}, {name:'annotated', dtype:'image'}],
      params: {reference:{type:'text',default:''}, tolerance:{type:'slider',default:30,min:1,max:255,step:1}},
      hint: 'Defect detection on PCB frame' },

    { cat: 'Vision', type: 'color_detect', label: 'Color Detect', icon: '🎨', colour: '#f38ba8',
      inputs: [{name:'frame', dtype:'image'}], outputs: [{name:'result', dtype:'dict'},{name:'mask', dtype:'image'}],
      params: {color_space:{type:'select',default:'hsv',options:['hsv','rgb','lab']}, low_h:{type:'slider',default:0,min:0,max:180,step:1}, high_h:{type:'slider',default:180,min:0,max:180,step:1}, low_s:{type:'slider',default:50,min:0,max:255,step:1}, high_s:{type:'slider',default:255,min:0,max:255,step:1}, low_v:{type:'slider',default:50,min:0,max:255,step:1}, high_v:{type:'slider',default:255,min:0,max:255,step:1}},
      hint: 'Detect color ranges in image' },

    { cat: 'Vision', type: 'blob_detect', label: 'Blob Detect', icon: '⬤', colour: '#f38ba8',
      inputs: [{name:'frame', dtype:'image'}], outputs: [{name:'blobs', dtype:'dict'},{name:'annotated', dtype:'image'}],
      params: {min_area:{type:'number',default:100}, max_area:{type:'number',default:10000}, circularity:{type:'slider',default:0.5,min:0,max:1,step:0.01}},
      hint: 'Detect blobs/contours in image' },

    { cat: 'Vision', type: 'template_match', label: 'Template Match', icon: '🧩', colour: '#f38ba8',
      inputs: [{name:'frame', dtype:'image'},{name:'template', dtype:'image'}], outputs: [{name:'matches', dtype:'dict'},{name:'annotated', dtype:'image'}],
      params: {method:{type:'select',default:'ccoeff_normed',options:['ccoeff_normed','ccorr_normed','sqdiff_normed']}, threshold:{type:'slider',default:0.8,min:0,max:1,step:0.01}},
      hint: 'Template matching in image' },

    { cat: 'Vision', type: 'image_resize', label: 'Resize Image', icon: '🔲', colour: '#f38ba8',
      inputs: [{name:'frame', dtype:'image'}], outputs: [{name:'resized', dtype:'image'}],
      params: {width:{type:'number',default:320}, height:{type:'number',default:240}, interpolation:{type:'select',default:'linear',options:['nearest','linear','cubic','area','lanczos']}},
      hint: 'Resize / scale image' },

    { cat: 'Vision', type: 'image_crop', label: 'Crop Image', icon: '✂️', colour: '#f38ba8',
      inputs: [{name:'frame', dtype:'image'}], outputs: [{name:'cropped', dtype:'image'}],
      params: {x:{type:'number',default:0}, y:{type:'number',default:0}, w:{type:'number',default:320}, h:{type:'number',default:240}},
      hint: 'Crop region of interest' },

    { cat: 'Vision', type: 'image_threshold', label: 'Image Threshold', icon: '◻', colour: '#f38ba8',
      inputs: [{name:'frame', dtype:'image'}], outputs: [{name:'binary', dtype:'image'},{name:'stats', dtype:'dict'}],
      params: {method:{type:'select',default:'otsu',options:['otsu','adaptive','binary','triangle']}, threshold:{type:'slider',default:127,min:0,max:255,step:1}, invert:{type:'checkbox',default:false}},
      hint: 'Binarize image (thresholding)' },

    // ═══════════════════════════════════════════════════════════
    // MATH / TRANSFORM
    // ═══════════════════════════════════════════════════════════

    { cat: 'Math', type: 'expression', label: 'Expression', icon: 'ƒ', colour: '#cba6f7',
      inputs: [{name:'a', dtype:'any'},{name:'b', dtype:'any'}], outputs: [{name:'result', dtype:'any'}],
      params: {expr:{type:'text',default:'a + b'}},
      hint: 'Python expression (a, b → result)' },

    { cat: 'Math', type: 'constant', label: 'Constant', icon: '#', colour: '#cba6f7',
      inputs: [], outputs: [{name:'value', dtype:'any'}],
      params: {value:{type:'text',default:'3.14'}, dtype:{type:'select',default:'float',options:['float','int','str','bool','list','dict']}},
      hint: 'Emit a constant value' },

    { cat: 'Math', type: 'multiply', label: 'Multiply', icon: '×', colour: '#cba6f7',
      inputs: [{name:'a', dtype:'number'},{name:'b', dtype:'number'}], outputs: [{name:'result', dtype:'number'}],
      params: {},
      hint: 'a × b' },

    { cat: 'Math', type: 'add', label: 'Add', icon: '+', colour: '#cba6f7',
      inputs: [{name:'a', dtype:'number'},{name:'b', dtype:'number'}], outputs: [{name:'result', dtype:'number'}],
      params: {},
      hint: 'a + b' },

    { cat: 'Math', type: 'subtract', label: 'Subtract', icon: '−', colour: '#cba6f7',
      inputs: [{name:'a', dtype:'number'},{name:'b', dtype:'number'}], outputs: [{name:'result', dtype:'number'}],
      params: {},
      hint: 'a − b' },

    { cat: 'Math', type: 'divide', label: 'Divide', icon: '÷', colour: '#cba6f7',
      inputs: [{name:'a', dtype:'number'},{name:'b', dtype:'number'}], outputs: [{name:'result', dtype:'number'}],
      params: {},
      hint: 'a ÷ b' },

    { cat: 'Math', type: 'abs_val', label: 'Absolute Value', icon: '|x|', colour: '#cba6f7',
      inputs: [{name:'value', dtype:'number'}], outputs: [{name:'result', dtype:'number'}],
      params: {},
      hint: 'Absolute value' },

    { cat: 'Math', type: 'power', label: 'Power', icon: 'xⁿ', colour: '#cba6f7',
      inputs: [{name:'base', dtype:'number'},{name:'exp', dtype:'number'}], outputs: [{name:'result', dtype:'number'}],
      params: {default_exp:{type:'number',default:2}},
      hint: 'base ^ exponent' },

    { cat: 'Math', type: 'log_math', label: 'Logarithm', icon: 'log', colour: '#cba6f7',
      inputs: [{name:'value', dtype:'number'}], outputs: [{name:'result', dtype:'number'}],
      params: {base:{type:'select',default:'e',options:['e','10','2']}},
      hint: 'Natural / base-10 / base-2 log' },

    { cat: 'Math', type: 'trig', label: 'Trigonometry', icon: '∿', colour: '#cba6f7',
      inputs: [{name:'angle', dtype:'number'}], outputs: [{name:'result', dtype:'number'}],
      params: {func:{type:'select',default:'sin',options:['sin','cos','tan','asin','acos','atan']}, unit:{type:'select',default:'radians',options:['radians','degrees']}},
      hint: 'Trig functions' },

    { cat: 'Math', type: 'clamp', label: 'Clamp', icon: '⊏⊐', colour: '#cba6f7',
      inputs: [{name:'value', dtype:'number'}], outputs: [{name:'result', dtype:'number'}],
      params: {min_val:{type:'number',default:0}, max_val:{type:'number',default:1}},
      hint: 'Clamp value to [min, max]' },

    { cat: 'Math', type: 'map_range', label: 'Map Range', icon: '↔', colour: '#cba6f7',
      inputs: [{name:'value', dtype:'number'}], outputs: [{name:'result', dtype:'number'}],
      params: {in_min:{type:'number',default:0}, in_max:{type:'number',default:1023}, out_min:{type:'number',default:0}, out_max:{type:'number',default:3.3}},
      hint: 'Linear range mapping (like Arduino map)' },

    { cat: 'Math', type: 'compare', label: 'Compare', icon: '≷', colour: '#cba6f7',
      inputs: [{name:'a', dtype:'any'},{name:'b', dtype:'any'}], outputs: [{name:'result', dtype:'bool'}],
      params: {op:{type:'select',default:'>',options:['>','<','>=','<=','==','!=']}},
      hint: 'Compare two values' },

    { cat: 'Math', type: 'unit_convert', label: 'Unit Convert', icon: '⟹', colour: '#cba6f7',
      inputs: [{name:'value', dtype:'number'}], outputs: [{name:'result', dtype:'number'}],
      params: {conversion:{type:'select',default:'A_to_uA',options:['A_to_uA','A_to_mA','uA_to_A','mA_to_A','V_to_mV','mV_to_V','W_to_mW','mW_to_W','C_to_F','F_to_C','K_to_C','C_to_K','Hz_to_kHz','kHz_to_MHz','dBm_to_mW','mW_to_dBm','rad_to_deg','deg_to_rad']}},
      hint: 'Common unit conversions' },

    // ═══════════════════════════════════════════════════════════
    // DATA — Manipulation & formatting
    // ═══════════════════════════════════════════════════════════

    { cat: 'Data', type: 'dict_get', label: 'Dict Get', icon: '{}→', colour: '#94e2d5',
      inputs: [{name:'data', dtype:'dict'}], outputs: [{name:'value', dtype:'any'}],
      params: {key:{type:'text',default:'avg_current_a'}, default_val:{type:'text',default:'null'}},
      hint: 'Extract value from dict by key' },

    { cat: 'Data', type: 'dict_set', label: 'Dict Set', icon: '→{}', colour: '#94e2d5',
      inputs: [{name:'data', dtype:'dict'},{name:'value', dtype:'any'}], outputs: [{name:'result', dtype:'dict'}],
      params: {key:{type:'text',default:'my_field'}},
      hint: 'Set a key in dict' },

    { cat: 'Data', type: 'dict_build', label: 'Build Dict', icon: '{ }', colour: '#94e2d5',
      inputs: [{name:'a', dtype:'any'},{name:'b', dtype:'any'}], outputs: [{name:'result', dtype:'dict'}],
      params: {key_a:{type:'text',default:'left'}, key_b:{type:'text',default:'right'}},
      hint: 'Build dict from two inputs' },

    { cat: 'Data', type: 'list_build', label: 'Build List', icon: '[ ]', colour: '#94e2d5',
      inputs: [{name:'a', dtype:'any'},{name:'b', dtype:'any'}], outputs: [{name:'result', dtype:'any'}],
      params: {},
      hint: 'Build list from two inputs' },

    { cat: 'Data', type: 'json_parse', label: 'JSON Parse', icon: '{ }', colour: '#94e2d5',
      inputs: [{name:'text', dtype:'str'}], outputs: [{name:'data', dtype:'any'}],
      params: {},
      hint: 'Parse JSON string to object' },

    { cat: 'Data', type: 'format_string', label: 'Format String', icon: '"…"', colour: '#94e2d5',
      inputs: [{name:'a', dtype:'any'},{name:'b', dtype:'any'}], outputs: [{name:'text', dtype:'str'}],
      params: {template:{type:'text',default:'Value: {a}, Result: {b}'}},
      hint: 'Python f-string template' },

    { cat: 'Data', type: 'type_cast', label: 'Type Cast', icon: '⇄', colour: '#94e2d5',
      inputs: [{name:'value', dtype:'any'}], outputs: [{name:'result', dtype:'any'}],
      params: {to_type:{type:'select',default:'float',options:['float','int','str','bool','list','dict','json_str']}},
      hint: 'Cast value to another type' },

    { cat: 'Data', type: 'pick_field', label: 'Pick Fields', icon: '⊙', colour: '#94e2d5',
      inputs: [{name:'data', dtype:'dict'}], outputs: [{name:'result', dtype:'dict'}],
      params: {fields:{type:'text',default:'avg_current_a,max_current_a'}},
      hint: 'Pick specific fields from dict' },

    // ═══════════════════════════════════════════════════════════
    // I/O — Display, plot, save
    // ═══════════════════════════════════════════════════════════

    { cat: 'I/O', type: 'display', label: 'Display', icon: '🖥️', colour: '#f9e2af',
      inputs: [{name:'data', dtype:'any'}], outputs: [],
      params: {format:{type:'select',default:'auto',options:['auto','json','table','plot']}},
      hint: 'Show value in console' },

    { cat: 'I/O', type: 'plot_trace', label: 'Plot Trace', icon: '📈', colour: '#f9e2af',
      inputs: [{name:'trace', dtype:'power_trace'}], outputs: [],
      params: {title:{type:'text',default:'Power Trace'}, y_label:{type:'text',default:'Current (A)'}, style:{type:'select',default:'lines',options:['lines','markers','lines+markers','bars']}},
      hint: 'Plot time-series chart' },

    { cat: 'I/O', type: 'plot_xy', label: 'Plot X/Y', icon: '📊', colour: '#f9e2af',
      inputs: [{name:'x', dtype:'any'},{name:'y', dtype:'any'}], outputs: [],
      params: {title:{type:'text',default:'XY Plot'}, x_label:{type:'text',default:'X'}, y_label:{type:'text',default:'Y'}, mode:{type:'select',default:'markers',options:['lines','markers','lines+markers']}},
      hint: 'Scatter / line plot from X, Y arrays' },

    { cat: 'I/O', type: 'plot_histogram', label: 'Plot Histogram', icon: '▊', colour: '#f9e2af',
      inputs: [{name:'data', dtype:'any'}], outputs: [],
      params: {title:{type:'text',default:'Histogram'}, bins:{type:'slider',default:50,min:5,max:500,step:1}, color:{type:'text',default:'#89b4fa'}},
      hint: 'Plot histogram chart' },

    { cat: 'I/O', type: 'plot_heatmap', label: 'Plot Heatmap', icon: '🗺️', colour: '#f9e2af',
      inputs: [{name:'data', dtype:'any'}], outputs: [],
      params: {title:{type:'text',default:'Heatmap'}, colorscale:{type:'select',default:'Inferno',options:['Inferno','Viridis','Plasma','Hot','Jet','Blues','RdBu']}},
      hint: 'Plot 2D heatmap' },

    { cat: 'I/O', type: 'gauge_display', label: 'Gauge', icon: '🎯', colour: '#f9e2af',
      inputs: [{name:'value', dtype:'number'}], outputs: [],
      params: {title:{type:'text',default:'Gauge'}, min_val:{type:'number',default:0}, max_val:{type:'number',default:100}, unit:{type:'text',default:''}, green_max:{type:'slider',default:60,min:0,max:100,step:1}, yellow_max:{type:'slider',default:80,min:0,max:100,step:1}},
      hint: 'Gauge / meter display' },

    { cat: 'I/O', type: 'table_display', label: 'Table', icon: '📋', colour: '#f9e2af',
      inputs: [{name:'data', dtype:'any'}], outputs: [],
      params: {max_rows:{type:'slider',default:100,min:1,max:1000,step:1}},
      hint: 'Display data as table' },

    { cat: 'I/O', type: 'save_file', label: 'Save to File', icon: '💾', colour: '#f9e2af',
      inputs: [{name:'data', dtype:'any'}], outputs: [],
      params: {path:{type:'text',default:'output.json'}, fmt:{type:'select',default:'json',options:['json','csv','npy','txt']}},
      hint: 'Write data to file' },

    { cat: 'I/O', type: 'log_message', label: 'Log Message', icon: '📝', colour: '#f9e2af',
      inputs: [{name:'data', dtype:'any'}], outputs: [{name:'data', dtype:'any'}],
      params: {prefix:{type:'text',default:'LOG'}, level:{type:'select',default:'info',options:['info','warning','error','debug']}},
      hint: 'Log pass-through node' },

    { cat: 'I/O', type: 'live_video', label: 'Live Video', icon: '📹', colour: '#f9e2af',
      inputs: [], outputs: [{name:'frame', dtype:'any'}],
      params: {camera_index:{type:'slider',default:0,min:0,max:4,step:1}, width:{type:'slider',default:320,min:160,max:1280,step:160}, height:{type:'slider',default:240,min:120,max:960,step:120}},
      hint: 'Capture webcam frame (rendered in node)' },

    { cat: 'I/O', type: 'waterfall_display', label: 'Waterfall', icon: '🌊', colour: '#f9e2af',
      inputs: [{name:'spectrum', dtype:'any'}], outputs: [],
      params: {title:{type:'text',default:'Waterfall'}, history_rows:{type:'slider',default:32,min:8,max:128,step:8}, colorscale:{type:'select',default:'Inferno',options:['Inferno','Viridis','Plasma','Hot','Jet','Blues']}},
      hint: 'Waterfall / spectrogram display from FFT data' },

    { cat: 'I/O', type: 'assert_check', label: 'Assert', icon: '✓', colour: '#f9e2af',
      inputs: [{name:'condition', dtype:'bool'}], outputs: [{name:'pass', dtype:'bool'}],
      params: {message:{type:'text',default:'Assertion failed!'}, fail_action:{type:'select',default:'log',options:['log','stop','ignore']}},
      hint: 'Assert condition is true' },

    // ═══════════════════════════════════════════════════════════
    // FLOW CONTROL
    // ═══════════════════════════════════════════════════════════

    { cat: 'Flow', type: 'delay', label: 'Delay', icon: '⏱️', colour: '#f5c2e7',
      inputs: [{name:'trigger', dtype:'any'}], outputs: [{name:'trigger', dtype:'any'}],
      params: {seconds:{type:'slider',default:1,min:0.1,max:60,step:0.1}},
      hint: 'Wait N seconds' },

    { cat: 'Flow', type: 'repeat', label: 'Repeat', icon: '🔁', colour: '#f5c2e7',
      inputs: [{name:'input', dtype:'any'}], outputs: [{name:'output', dtype:'any'},{name:'index', dtype:'number'}],
      params: {count:{type:'slider',default:5,min:1,max:100,step:1}},
      hint: 'Execute upstream N times' },

    { cat: 'Flow', type: 'gate', label: 'Gate (If)', icon: '🚦', colour: '#f5c2e7',
      inputs: [{name:'cond', dtype:'bool'},{name:'data', dtype:'any'}], outputs: [{name:'true_out', dtype:'any'},{name:'false_out', dtype:'any'}],
      params: {},
      hint: 'Route data based on condition' },

    { cat: 'Flow', type: 'merge', label: 'Merge', icon: '⊕', colour: '#f5c2e7',
      inputs: [{name:'a', dtype:'any'},{name:'b', dtype:'any'}], outputs: [{name:'merged', dtype:'any'}],
      params: {strategy:{type:'select',default:'dict_merge',options:['dict_merge','list_concat','first_valid']}},
      hint: 'Merge two inputs' },

    { cat: 'Flow', type: 'sequence', label: 'Sequence', icon: '⟶', colour: '#f5c2e7',
      inputs: [{name:'step_1', dtype:'any'},{name:'step_2', dtype:'any'}], outputs: [{name:'last', dtype:'any'}],
      params: {},
      hint: 'Force execution order (step_1 before step_2)' },

    { cat: 'Flow', type: 'null_check', label: 'Null Check', icon: '∅', colour: '#f5c2e7',
      inputs: [{name:'value', dtype:'any'}], outputs: [{name:'value', dtype:'any'},{name:'is_null', dtype:'bool'}],
      params: {default_val:{type:'text',default:'0'}},
      hint: 'Check for null/None, provide default' },

    { cat: 'Flow', type: 'try_catch', label: 'Try/Catch', icon: '🛡️', colour: '#f5c2e7',
      inputs: [{name:'data', dtype:'any'}], outputs: [{name:'data', dtype:'any'},{name:'error', dtype:'str'}],
      params: {},
      hint: 'Error boundary — pass data or catch errors' },

    // ═══════════════════════════════════════════════════════════
    // HARDWARE ACTIONS — Shell, network, bench
    // ═══════════════════════════════════════════════════════════

    { cat: 'Actions', type: 'shell_cmd', label: 'Shell Command', icon: '⌨️', colour: '#fab387',
      inputs: [{name:'trigger', dtype:'any'}], outputs: [{name:'stdout', dtype:'str'},{name:'exit_code', dtype:'number'}],
      params: {command:{type:'text',default:'echo hello'}, timeout_s:{type:'number',default:30}},
      hint: 'Run a shell command' },

    { cat: 'Actions', type: 'http_request', label: 'HTTP Request', icon: '🌐', colour: '#fab387',
      inputs: [{name:'body', dtype:'any'}], outputs: [{name:'response', dtype:'dict'},{name:'status', dtype:'number'}],
      params: {url:{type:'text',default:'http://localhost:5200/api/health'}, method:{type:'select',default:'GET',options:['GET','POST','PUT','DELETE']}, headers:{type:'textarea',default:'{}'}},
      hint: 'Make an HTTP request' },

    { cat: 'Actions', type: 'sleep_test', label: 'Sleep Current Test', icon: '😴', colour: '#fab387',
      inputs: [], outputs: [{name:'trace', dtype:'power_trace'},{name:'verdict', dtype:'dict'}],
      params: {duration_s:{type:'number',default:5}, settle_s:{type:'number',default:1}, max_avg_ua:{type:'number',default:10}},
      hint: 'Full sleep current measurement' },

    { cat: 'Actions', type: 'tx_burst_test', label: 'TX Burst Test', icon: '📡', colour: '#fab387',
      inputs: [], outputs: [{name:'trace', dtype:'power_trace'},{name:'verdict', dtype:'dict'}],
      params: {duration_s:{type:'number',default:3}, interval_ms:{type:'number',default:100}, max_peak_ma:{type:'number',default:50}, max_avg_ma:{type:'number',default:5}},
      hint: 'RF transmit burst profile test' },

    { cat: 'Actions', type: 'gpio_toggle', label: 'GPIO Toggle', icon: '🔀', colour: '#fab387',
      inputs: [{name:'trigger', dtype:'any'}], outputs: [{name:'state', dtype:'bool'}],
      params: {pin:{type:'text',default:'P0.13'}, action:{type:'select',default:'toggle',options:['toggle','high','low','pulse']}, pulse_ms:{type:'number',default:100}},
      hint: 'Toggle GPIO pin via debug probe' },

    { cat: 'Actions', type: 'serial_send', label: 'Serial Send', icon: '🔌', colour: '#fab387',
      inputs: [{name:'data', dtype:'any'}], outputs: [{name:'response', dtype:'str'}],
      params: {port:{type:'text',default:'COM3'}, baudrate:{type:'number',default:115200}, command:{type:'text',default:'AT\\r\\n'}, timeout_s:{type:'number',default:2}},
      hint: 'Send data over serial port' },

    { cat: 'Actions', type: 'load_profile', label: 'Load Profile', icon: '📋', colour: '#fab387',
      inputs: [], outputs: [{name:'profile', dtype:'dict'}],
      params: {path:{type:'text',default:'profiles/sleep_current.json'}},
      hint: 'Load a test profile JSON' },

    { cat: 'Actions', type: 'benchmark_timer', label: 'Benchmark Timer', icon: '⏲️', colour: '#fab387',
      inputs: [{name:'trigger', dtype:'any'}], outputs: [{name:'elapsed_s', dtype:'number'}],
      params: {label:{type:'text',default:'operation'}},
      hint: 'Measure elapsed time' },

    // ═══════════════════════════════════════════════════════════
    // CAN BUS — CAN communication & analysis
    // ═══════════════════════════════════════════════════════════

    { cat: 'CAN Bus', type: 'can_send', label: 'CAN Send', icon: '🔌', colour: '#a6e3a1',
      inputs: [{name:'arb_id', dtype:'number'}, {name:'data', dtype:'string'}],
      outputs: [{name:'sent', dtype:'bool'}],
      params: {interface:{type:'select',default:'virtual',options:['pcan','socketcan','vector','kvaser','ixxat','virtual']}, channel:{type:'text',default:'PCAN_USBBUS1'}, bitrate:{type:'select',default:'500000',options:['125000','250000','500000','1000000']}, arb_id:{type:'text',default:'0x100'}, data:{type:'text',default:'DEADBEEF'}, extended:{type:'checkbox',default:false}},
      hint: 'Send a CAN frame' },

    { cat: 'CAN Bus', type: 'can_receive', label: 'CAN Receive', icon: '📡', colour: '#a6e3a1',
      inputs: [],
      outputs: [{name:'messages', dtype:'array'}, {name:'stats', dtype:'array'}, {name:'n_frames', dtype:'number'}],
      params: {interface:{type:'select',default:'virtual',options:['pcan','socketcan','vector','kvaser','ixxat','virtual']}, channel:{type:'text',default:'PCAN_USBBUS1'}, bitrate:{type:'select',default:'500000',options:['125000','250000','500000','1000000']}, duration_s:{type:'slider',default:2,min:0.5,max:30,step:0.5}, id_filter:{type:'text',default:''}},
      hint: 'Capture CAN frames for a duration' },

    { cat: 'CAN Bus', type: 'can_decode', label: 'CAN Decode', icon: '🔍', colour: '#a6e3a1',
      inputs: [{name:'messages', dtype:'array'}],
      outputs: [{name:'decoded', dtype:'array'}],
      params: {},
      hint: 'Decode CAN frames (CANopen, DBC signals)' },

    { cat: 'CAN Bus', type: 'can_analyze', label: 'CAN Analyze', icon: '🧪', colour: '#a6e3a1',
      inputs: [{name:'arb_id', dtype:'number'}],
      outputs: [{name:'analysis', dtype:'object'}],
      params: {interface:{type:'select',default:'virtual',options:['pcan','socketcan','vector','kvaser','ixxat','virtual']}, channel:{type:'text',default:'PCAN_USBBUS1'}, bitrate:{type:'select',default:'500000',options:['125000','250000','500000','1000000']}, arb_id:{type:'text',default:'0x100'}, duration_s:{type:'slider',default:5,min:1,max:60,step:1}},
      hint: 'Deep RE analysis: counters, CRCs, bit transitions, signals' },

    { cat: 'CAN Bus', type: 'can_replay', label: 'CAN Replay', icon: '⏪', colour: '#a6e3a1',
      inputs: [{name:'messages', dtype:'array'}],
      outputs: [{name:'replayed', dtype:'number'}],
      params: {interface:{type:'select',default:'virtual',options:['pcan','socketcan','vector','kvaser','ixxat','virtual']}, channel:{type:'text',default:'PCAN_USBBUS1'}, bitrate:{type:'select',default:'500000',options:['125000','250000','500000','1000000']}, speed_factor:{type:'slider',default:1,min:0.1,max:10,step:0.1}},
      hint: 'Replay captured CAN traffic back onto the bus' },
  ];

  // ══════════════════════════════════════════════════════════════
  // State
  // ══════════════════════════════════════════════════════════════

  let nextId = 1;
  const blocks = {};    // id → {id, type, x, y, w, h, params, def}
  const wires  = {};    // id → {id, from:{block,port}, to:{block,port}}
  let selected = null;  // block id or null
  let execRunning = false;

  // Canvas pan/zoom
  let panX = 0, panY = 0, zoom = 1;

  // Drag state
  let dragging = null;    // {blockId, offsetX, offsetY}
  let wiring   = null;    // {fromBlock, fromPort, isOutput, startX, startY}

  const svg      = document.getElementById('canvas');
  const wiresG   = document.getElementById('wires-layer');
  const blocksG  = document.getElementById('blocks-layer');
  const tempWire = document.getElementById('temp-wire');


  // Responsive side panels keep the canvas usable on narrow screens.
  const paletteButton = document.getElementById('btn-palette');
  const propsButton = document.getElementById('btn-props');
  const panelBackdrop = document.getElementById('panel-backdrop');

  function setPanel(panel) {
    const paletteOpen = panel === 'palette';
    const propsOpen = panel === 'props';
    document.body.classList.toggle('palette-open', paletteOpen);
    document.body.classList.toggle('props-open', propsOpen);
    paletteButton?.setAttribute('aria-expanded', paletteOpen ? 'true' : 'false');
    propsButton?.setAttribute('aria-expanded', propsOpen ? 'true' : 'false');
    if (panelBackdrop) panelBackdrop.hidden = !(paletteOpen || propsOpen);
  }

  paletteButton?.addEventListener('click', () => setPanel(document.body.classList.contains('palette-open') ? '' : 'palette'));
  propsButton?.addEventListener('click', () => setPanel(document.body.classList.contains('props-open') ? '' : 'props'));
  panelBackdrop?.addEventListener('click', () => setPanel(''));
  window.addEventListener('resize', () => { if (!matchMedia('(max-width: 820px)').matches) setPanel(''); });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && (document.body.classList.contains('palette-open') || document.body.classList.contains('props-open'))) {
      setPanel('');
    }
  });

  // ══════════════════════════════════════════════════════════════
  // Palette rendering
  // ══════════════════════════════════════════════════════════════

  function renderPalette(filter) {
    const list = document.getElementById('palette-list');
    list.innerHTML = '';
    let currentCat = '';
    const lc = (filter || '').toLowerCase();

    for (const def of BLOCK_CATALOGUE) {
      if (lc && !def.label.toLowerCase().includes(lc) &&
          !def.type.toLowerCase().includes(lc) &&
          !def.cat.toLowerCase().includes(lc) &&
          !(def.hint||'').toLowerCase().includes(lc)) continue;

      if (def.cat !== currentCat) {
        currentCat = def.cat;
        const h = document.createElement('div');
        h.className = 'pal-cat';
        h.textContent = currentCat;
        list.appendChild(h);
      }

      const item = document.createElement('div');
      item.className = 'pal-item';
      item.draggable = true;
      item.dataset.type = def.type;
      item.setAttribute('role', 'button');
      item.tabIndex = 0;
      item.setAttribute('aria-label', `Add ${def.label} block — ${def.hint || def.type}`);
      item.innerHTML = `
        <span class="pal-icon" style="background:${def.colour}30;color:${def.colour}">${def.icon}</span>
        <span class="pal-label">${def.label}<br><span class="pal-hint">${def.hint||''}</span></span>
      `;
      item.addEventListener('dragstart', (e) => {
        e.dataTransfer.setData('block-type', def.type);
        e.dataTransfer.effectAllowed = 'copy';
      });
      const addAtCentre = () => {
        const rect = svg.getBoundingClientRect();
        const cx = (rect.width / 2 - panX) / zoom;
        const cy = (rect.height / 2 - panY) / zoom;
        addBlock(def.type, cx - 70, cy - 30);
        if (matchMedia('(max-width: 820px)').matches) setPanel('');
      };
      // Double-click, Enter, or Space adds the component at the canvas centre.
      item.addEventListener('dblclick', addAtCentre);
      item.addEventListener('keydown', event => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        addAtCentre();
      });
      list.appendChild(item);
    }
  }

  document.getElementById('palette-search').addEventListener('input', (e) => {
    renderPalette(e.target.value);
  });

  renderPalette('');

  // ══════════════════════════════════════════════════════════════
  // Canvas: pan & zoom
  // ══════════════════════════════════════════════════════════════

  function applyTransform() {
    blocksG.setAttribute('transform', `translate(${panX},${panY}) scale(${zoom})`);
    wiresG.setAttribute('transform',  `translate(${panX},${panY}) scale(${zoom})`);
  }

  svg.addEventListener('wheel', (e) => {
    e.preventDefault();
    const rect = svg.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const oldZoom = zoom;
    const delta = -e.deltaY * 0.001;
    zoom = Math.min(3, Math.max(0.15, zoom + delta));

    // Zoom towards cursor
    panX = mx - (mx - panX) * (zoom / oldZoom);
    panY = my - (my - panY) * (zoom / oldZoom);
    applyTransform();
  });

  let panning = false, panStartX, panStartY;
  svg.addEventListener('mousedown', (e) => {
    if (e.target.classList.contains('canvas-bg') || e.button === 1) {
      panning = true;
      panStartX = e.clientX - panX;
      panStartY = e.clientY - panY;
      svg.style.cursor = 'grabbing';
      e.preventDefault();
    }
  });
  window.addEventListener('mousemove', (e) => {
    if (panning) {
      panX = e.clientX - panStartX;
      panY = e.clientY - panStartY;
      applyTransform();
    }
  });
  window.addEventListener('mouseup', () => {
    if (panning) { panning = false; svg.style.cursor = ''; }
  });

  // Drop from palette
  document.getElementById('canvas-wrap').addEventListener('dragover', (e) => {
    e.preventDefault(); e.dataTransfer.dropEffect = 'copy';
  });
  document.getElementById('canvas-wrap').addEventListener('drop', (e) => {
    e.preventDefault();
    const type = e.dataTransfer.getData('block-type');
    if (!type) return;
    const rect = svg.getBoundingClientRect();
    const x = (e.clientX - rect.left - panX) / zoom;
    const y = (e.clientY - rect.top  - panY) / zoom;
    addBlock(type, x - 70, y - 20);
  });

  // Deselect on canvas background click
  svg.addEventListener('click', (e) => {
    if (e.target.classList.contains('canvas-bg')) {
      selectBlock(null);
    }
  });

  // ══════════════════════════════════════════════════════════════
  // Block creation & SVG rendering
  // ══════════════════════════════════════════════════════════════

  const BLOCK_W = 160, PORT_SPACING = 22, HEADER_H = 28, PORT_R = 5;

  // Viz-capable blocks get a wider, taller node to hold inline charts
  const VIZ_W = 300, VIZ_CANVAS_H = 180;
  const VIZ_TYPES = new Set([
    'plot_trace','plot_xy','plot_histogram','plot_heatmap',
    'gauge_display','table_display','fft_spectrum',
    'live_video','waterfall_display',
  ]);

  function blockDef(type) {
    return BLOCK_CATALOGUE.find(d => d.type === type);
  }

  function blockHeight(def) {
    const ports = Math.max(def.inputs.length, def.outputs.length, 1);
    const base = HEADER_H + ports * PORT_SPACING + 8;
    if (VIZ_TYPES.has(def.type)) return base + VIZ_CANVAS_H + 8;
    return base;
  }

  function addBlock(type, x, y) {
    const def = blockDef(type);
    if (!def) return;
    const id = 'b' + (nextId++);
    const h = blockHeight(def);
    const w = VIZ_TYPES.has(type) ? VIZ_W : BLOCK_W;
    const params = {};
    for (const [k, v] of Object.entries(def.params || {})) {
      params[k] = v.default;
    }
    blocks[id] = { id, type, x, y, w, h, params, def };
    renderBlock(id);
    selectBlock(id);
    return id;
  }

  function renderBlock(id) {
    const b = blocks[id];
    const def = b.def;
    // Remove existing
    const old = document.getElementById('blk-' + id);
    if (old) old.remove();

    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.id = 'blk-' + id;
    g.classList.add('block-group');
    g.dataset.blockId = id;

    // Body rect
    const body = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    body.classList.add('block-body');
    body.setAttribute('width', b.w);
    body.setAttribute('height', b.h);
    body.setAttribute('fill', 'var(--bg3)');
    g.appendChild(body);

    // Header bar
    const hdr = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    hdr.setAttribute('width', b.w);
    hdr.setAttribute('height', HEADER_H);
    hdr.setAttribute('rx', 6); hdr.setAttribute('ry', 6);
    hdr.setAttribute('fill', def.colour);
    g.appendChild(hdr);
    // Square off bottom corners of header
    const hdr2 = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    hdr2.setAttribute('y', HEADER_H - 6);
    hdr2.setAttribute('width', b.w);
    hdr2.setAttribute('height', 6);
    hdr2.setAttribute('fill', def.colour);
    g.appendChild(hdr2);

    // Icon + label
    const icon = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    icon.classList.add('block-header');
    icon.setAttribute('x', 8); icon.setAttribute('y', 18);
    icon.textContent = def.icon + ' ' + def.label;
    g.appendChild(icon);

    // Input ports
    def.inputs.forEach((p, i) => {
      const py = HEADER_H + PORT_SPACING * (i + 0.5) + 4;
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.classList.add('port', 'input');
      circle.setAttribute('cx', 0); circle.setAttribute('cy', py);
      circle.dataset.blockId = id;
      circle.dataset.portName = p.name;
      circle.dataset.portDir = 'input';
      circle.dataset.dtype = p.dtype;
      g.appendChild(circle);

      const lbl = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      lbl.classList.add('port-label');
      lbl.setAttribute('x', 10); lbl.setAttribute('y', py + 3);
      lbl.textContent = p.name;
      g.appendChild(lbl);
    });

    // Output ports
    def.outputs.forEach((p, i) => {
      const py = HEADER_H + PORT_SPACING * (i + 0.5) + 4;
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.classList.add('port', 'output');
      circle.setAttribute('cx', b.w); circle.setAttribute('cy', py);
      circle.dataset.blockId = id;
      circle.dataset.portName = p.name;
      circle.dataset.portDir = 'output';
      circle.dataset.dtype = p.dtype;
      g.appendChild(circle);

      const lbl = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      lbl.classList.add('port-label');
      lbl.setAttribute('x', b.w - 10); lbl.setAttribute('y', py + 3);
      lbl.setAttribute('text-anchor', 'end');
      lbl.textContent = p.name;
      g.appendChild(lbl);
    });

    g.setAttribute('transform', `translate(${b.x}, ${b.y})`);

    // Drag
    g.addEventListener('mousedown', (e) => {
      if (e.target.classList.contains('port')) return; // port wiring
      dragging = { blockId: id, offsetX: e.offsetX, offsetY: e.offsetY, startMX: e.clientX, startMY: e.clientY };
      selectBlock(id);
      e.stopPropagation();
    });

    // Port wiring — mousedown on port
    g.querySelectorAll('.port').forEach(port => {
      port.addEventListener('mousedown', (e) => {
        e.stopPropagation();
        const blk = blocks[port.dataset.blockId];
        const isOut = port.dataset.portDir === 'output';
        const px = isOut ? blk.x + blk.w : blk.x;
        const py = blk.y + parseFloat(port.getAttribute('cy'));
        wiring = {
          fromBlock: port.dataset.blockId,
          fromPort: port.dataset.portName,
          isOutput: isOut,
          startX: px, startY: py,
        };
        tempWire.style.display = '';
      });
    });

    blocksG.appendChild(g);
  }

  // ── Mouse move: block drag & wire drawing ──────────────────

  window.addEventListener('mousemove', (e) => {
    // Block dragging
    if (dragging && !panning) {
      const dx = (e.clientX - dragging.startMX) / zoom;
      const dy = (e.clientY - dragging.startMY) / zoom;
      const b = blocks[dragging.blockId];
      b.x = b.x + dx;
      b.y = b.y + dy;
      dragging.startMX = e.clientX;
      dragging.startMY = e.clientY;
      const g = document.getElementById('blk-' + b.id);
      g.setAttribute('transform', `translate(${b.x}, ${b.y})`);
      updateWiresFor(b.id);
    }

    // Wire drawing
    if (wiring) {
      const rect = svg.getBoundingClientRect();
      const mx = (e.clientX - rect.left - panX) / zoom;
      const my = (e.clientY - rect.top  - panY) / zoom;
      const sx = wiring.startX, sy = wiring.startY;
      const dx = Math.abs(mx - sx) * 0.5;
      const d = wiring.isOutput
        ? `M${sx},${sy} C${sx+dx},${sy} ${mx-dx},${my} ${mx},${my}`
        : `M${sx},${sy} C${sx-dx},${sy} ${mx+dx},${my} ${mx},${my}`;
      tempWire.setAttribute('d', d);
    }
  });

  window.addEventListener('mouseup', (e) => {
    // Finish wire
    if (wiring) {
      const target = document.elementFromPoint(e.clientX, e.clientY);
      if (target && target.classList.contains('port')) {
        const tBlk  = target.dataset.blockId;
        const tPort = target.dataset.portName;
        const tDir  = target.dataset.portDir;

        // Validate: must connect output→input (or input→output)
        if (wiring.isOutput && tDir === 'input' && tBlk !== wiring.fromBlock) {
          addWire(wiring.fromBlock, wiring.fromPort, tBlk, tPort);
        } else if (!wiring.isOutput && tDir === 'output' && tBlk !== wiring.fromBlock) {
          addWire(tBlk, tPort, wiring.fromBlock, wiring.fromPort);
        }
      }
      tempWire.style.display = 'none';
      tempWire.setAttribute('d', '');
      wiring = null;
    }
    dragging = null;
  });

  // ══════════════════════════════════════════════════════════════
  // Wires
  // ══════════════════════════════════════════════════════════════

  function addWire(fromBlk, fromPort, toBlk, toPort) {
    // Check for duplicate
    for (const w of Object.values(wires)) {
      if (w.to.block === toBlk && w.to.port === toPort) {
        // Input already connected — replace
        removeWire(w.id);
        break;
      }
    }
    const id = 'w' + (nextId++);
    wires[id] = { id, from: {block: fromBlk, port: fromPort}, to: {block: toBlk, port: toPort} };
    renderWire(id);
    updatePortStyles();
  }

  function removeWire(id) {
    const el = document.getElementById('wire-' + id);
    if (el) el.remove();
    delete wires[id];
    updatePortStyles();
  }

  function renderWire(id) {
    const w = wires[id];
    const old = document.getElementById('wire-' + id);
    if (old) old.remove();

    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.id = 'wire-' + id;
    path.classList.add('wire');
    path.dataset.wireId = id;
    path.setAttribute('d', wirePath(w));
    path.setAttribute('marker-end', 'url(#arrow)');

    // Right-click to delete wire
    path.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      removeWire(id);
    });
    // Double click to delete
    path.addEventListener('dblclick', (e) => {
      e.stopPropagation();
      removeWire(id);
    });

    wiresG.appendChild(path);
  }

  function wirePath(w) {
    const fb = blocks[w.from.block], tb = blocks[w.to.block];
    if (!fb || !tb) return '';
    const fromDef = fb.def, toDef = tb.def;

    const fi = fromDef.outputs.findIndex(p => p.name === w.from.port);
    const ti = toDef.inputs.findIndex(p => p.name === w.to.port);
    if (fi < 0 || ti < 0) return '';

    const x1 = fb.x + fb.w;
    const y1 = fb.y + HEADER_H + PORT_SPACING * (fi + 0.5) + 4;
    const x2 = tb.x;
    const y2 = tb.y + HEADER_H + PORT_SPACING * (ti + 0.5) + 4;

    const dx = Math.max(Math.abs(x2 - x1) * 0.4, 40);
    return `M${x1},${y1} C${x1+dx},${y1} ${x2-dx},${y2} ${x2},${y2}`;
  }

  function updateWiresFor(blockId) {
    for (const w of Object.values(wires)) {
      if (w.from.block === blockId || w.to.block === blockId) {
        const el = document.getElementById('wire-' + w.id);
        if (el) el.setAttribute('d', wirePath(w));
      }
    }
  }

  function updatePortStyles() {
    // Mark ports that have connections
    document.querySelectorAll('.port').forEach(p => p.classList.remove('connected'));
    for (const w of Object.values(wires)) {
      // output port
      const fromG = document.getElementById('blk-' + w.from.block);
      if (fromG) {
        fromG.querySelectorAll(`.port.output[data-port-name="${w.from.port}"]`)
             .forEach(p => p.classList.add('connected'));
      }
      // input port
      const toG = document.getElementById('blk-' + w.to.block);
      if (toG) {
        toG.querySelectorAll(`.port.input[data-port-name="${w.to.port}"]`)
           .forEach(p => p.classList.add('connected'));
      }
    }
  }

  // ══════════════════════════════════════════════════════════════
  // Selection & properties panel
  // ══════════════════════════════════════════════════════════════

  function selectBlock(id) {
    document.querySelectorAll('.block-group.selected').forEach(g => g.classList.remove('selected'));
    selected = id;
    if (id) {
      const g = document.getElementById('blk-' + id);
      if (g) g.classList.add('selected');
    }
    renderProps();
    if (id && matchMedia('(max-width: 820px)').matches) setPanel('props');
  }

  function renderProps() {
    const title = document.getElementById('props-title');
    const body  = document.getElementById('props-body');

    if (!selected || !blocks[selected]) {
      title.textContent = 'Properties';
      body.innerHTML = '<p class="hint">Select a block to edit its properties.</p>';
      return;
    }
    const b = blocks[selected];
    const def = b.def;
    title.textContent = def.icon + ' ' + def.label;

    let html = `<div class="prop-row"><label>Block ID</label><input type="text" value="${b.id}" disabled></div>`;
    html += `<div class="prop-row"><label>Type</label><input type="text" value="${b.type}" disabled></div>`;

    for (const [key, meta] of Object.entries(def.params || {})) {
      const val = b.params[key] ?? meta.default ?? '';
      html += `<div class="prop-row"><label>${key}</label>`;

      if (meta.type === 'select') {
        html += `<select data-param="${key}">`;
        for (const opt of meta.options || []) {
          html += `<option value="${opt}"${opt==val?' selected':''}>${opt}</option>`;
        }
        html += '</select>';
      } else if (meta.type === 'checkbox') {
        html += `<input type="checkbox" data-param="${key}" ${val?'checked':''}>`;
      } else if (meta.type === 'textarea') {
        const escaped = typeof val === 'string' ? val : JSON.stringify(val, null, 2);
        html += `<textarea data-param="${key}">${escaped}</textarea>`;
      } else if (meta.type === 'slider') {
        const mn = meta.min ?? 0, mx = meta.max ?? 100, st = meta.step ?? 1;
        html += `<div class="slider-wrap">`;
        html += `<input type="range" class="prop-slider" data-param="${key}" min="${mn}" max="${mx}" step="${st}" value="${val}">`;
        html += `<div class="slider-labels"><span>${mn}</span><span class="slider-val" data-slider-for="${key}">${val}</span><span>${mx}</span></div>`;
        html += `</div>`;
      } else if (meta.type === 'number') {
        html += `<input type="number" step="any" data-param="${key}" value="${val}">`;
      } else {
        html += `<input type="text" data-param="${key}" value="${val}">`;
      }
      html += '</div>';
    }

    // Delete button
    html += `<div style="margin-top:16px"><button class="btn btn-danger" id="btn-delete-block">🗑 Delete Block</button></div>`;

    body.innerHTML = html;

    // Bind change events
    body.querySelectorAll('[data-param]').forEach(el => {
      const evt = el.type === 'checkbox' ? 'change' : 'input';
      el.addEventListener(evt, () => {
        const k = el.dataset.param;
        const meta = def.params[k];
        if (el.type === 'checkbox') {
          b.params[k] = el.checked;
        } else if (meta && (meta.type === 'number' || meta.type === 'slider')) {
          b.params[k] = parseFloat(el.value) || 0;
          // Update slider live value display
          const lbl = body.querySelector(`.slider-val[data-slider-for="${k}"]`);
          if (lbl) lbl.textContent = el.value;
        } else {
          b.params[k] = el.value;
        }
      });
    });

    document.getElementById('btn-delete-block')?.addEventListener('click', () => {
      deleteBlock(selected);
    });
  }

  function deleteBlock(id) {
    // Remove connected wires
    for (const w of Object.values(wires)) {
      if (w.from.block === id || w.to.block === id) removeWire(w.id);
    }
    const el = document.getElementById('blk-' + id);
    if (el) el.remove();
    delete blocks[id];
    if (selected === id) selectBlock(null);
  }

  // ══════════════════════════════════════════════════════════════
  // Keyboard shortcuts
  // ══════════════════════════════════════════════════════════════

  document.addEventListener('keydown', (e) => {
    // Delete selected block
    if ((e.key === 'Delete' || e.key === 'Backspace') && selected && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
      deleteBlock(selected);
      e.preventDefault();
    }
    // Ctrl+Enter → Run
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      runDiagram();
    }
    // Ctrl+S → Save
    if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      saveDiagram();
    }
    // Escape → deselect
    if (e.key === 'Escape') {
      if (wiring) { wiring = null; tempWire.style.display = 'none'; tempWire.setAttribute('d',''); }
      selectBlock(null);
    }
  });

  // ══════════════════════════════════════════════════════════════
  // Serialization
  // ══════════════════════════════════════════════════════════════

  function serialize() {
    return {
      version: 1,
      blocks: Object.values(blocks).map(b => ({
        id: b.id, type: b.type, x: Math.round(b.x), y: Math.round(b.y), params: b.params,
      })),
      wires: Object.values(wires).map(w => ({
        id: w.id, from: w.from, to: w.to,
      })),
    };
  }

  function deserialize(data) {
    // Clear
    clearCanvas();
    if (!data || !data.blocks) return;

    // Find max id
    let maxId = 0;
    for (const bd of data.blocks) {
      const n = parseInt(bd.id.replace(/\D/g,''), 10);
      if (n > maxId) maxId = n;
    }
    for (const wd of data.wires || []) {
      const n = parseInt(wd.id.replace(/\D/g,''), 10);
      if (n > maxId) maxId = n;
    }
    nextId = maxId + 1;

    for (const bd of data.blocks) {
      const def = blockDef(bd.type);
      if (!def) continue;
      const h = blockHeight(def);
      blocks[bd.id] = { id: bd.id, type: bd.type, x: bd.x, y: bd.y, w: BLOCK_W, h, params: bd.params || {}, def };
      renderBlock(bd.id);
    }
    for (const wd of data.wires || []) {
      wires[wd.id] = { id: wd.id, from: wd.from, to: wd.to };
      renderWire(wd.id);
    }
    updatePortStyles();
  }

  function clearCanvas() {
    for (const id of Object.keys(blocks)) {
      const el = document.getElementById('blk-' + id);
      if (el) el.remove();
    }
    for (const id of Object.keys(wires)) {
      const el = document.getElementById('wire-' + id);
      if (el) el.remove();
    }
    for (const k of Object.keys(blocks)) delete blocks[k];
    for (const k of Object.keys(wires))  delete wires[k];
    selectBlock(null);
  }

  // ══════════════════════════════════════════════════════════════
  // Save / Load / Export
  // ══════════════════════════════════════════════════════════════

  async function saveDiagram() {
    const data = serialize();
    try {
      const res = await fetch('/flowlab/api/save', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: 'autosave', diagram: data}),
      });
      const j = await res.json();
      consoleLog('💾 Saved: ' + (j.path || 'ok'));
    } catch (err) {
      consoleLog('❌ Save error: ' + err.message);
    }
  }

  async function loadDiagram() {
    try {
      const res = await fetch('/flowlab/api/load?name=autosave');
      const j = await res.json();
      if (j.diagram) {
        deserialize(j.diagram);
        consoleLog('📂 Loaded diagram (' + (j.diagram.blocks||[]).length + ' blocks)');
      } else {
        consoleLog('📂 No saved diagram found');
      }
    } catch (err) {
      consoleLog('❌ Load error: ' + err.message);
    }
  }

  function exportDiagram() {
    const data = serialize();
    const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = 'flowlab_diagram.json'; a.click();
    URL.revokeObjectURL(url);
    consoleLog('⬇ Exported diagram JSON');
  }

  async function exportPython() {
    const data = serialize();
    if (!data.blocks || data.blocks.length === 0) {
      consoleLog('⚠ Nothing to export — canvas is empty');
      return;
    }
    consoleLog('🐍 Generating Python script...');
    try {
      const res = await fetch('/flowlab/api/export_python', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({diagram: data, name: 'flowlab_test'}),
      });
      const j = await res.json();
      if (j.error) {
        consoleLog('❌ Python export error: ' + j.error);
        return;
      }
      const blob = new Blob([j.source], {type: 'text/x-python'});
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href = url; a.download = (j.name || 'flowlab_test') + '.py'; a.click();
      URL.revokeObjectURL(url);
      const lines = (j.source.match(/\n/g) || []).length + 1;
      consoleLog('🐍 Exported Python script: ' + (j.name || 'flowlab_test') + '.py (' + lines + ' lines)');
    } catch (err) {
      consoleLog('❌ Python export error: ' + err.message);
    }
  }

  // ══════════════════════════════════════════════════════════════
  // Execution
  // ══════════════════════════════════════════════════════════════

  async function runDiagram() {
    if (execRunning) return;
    execRunning = true;
    const statusEl = document.getElementById('exec-status');
    const timeEl   = document.getElementById('exec-time');
    const runBtn   = document.getElementById('btn-run');
    const stopBtn  = document.getElementById('btn-stop');

    statusEl.textContent = 'running'; statusEl.className = 'badge badge-warn';
    runBtn.disabled = true; stopBtn.disabled = false;
    timeEl.textContent = '';

    // Clear block states
    document.querySelectorAll('.block-group').forEach(g => {
      g.classList.remove('running','error');
    });

    consoleLog('\n▶ === Execution started ===');
    const t0 = performance.now();

    try {
      const diagram = serialize();
      const res = await fetch('/flowlab/api/execute', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(diagram),
      });
      const result = await res.json();

      if (result.error) {
        consoleLog('❌ ' + result.error);
        statusEl.textContent = 'error'; statusEl.className = 'badge badge-err';
      } else {
        // Show per-block results
        for (const [bid, bres] of Object.entries(result.block_results || {})) {
          const g = document.getElementById('blk-' + bid);
          if (!g) continue;
          if (bres.error) {
            g.classList.add('error');
            consoleLog(`❌ [${bid}] ${bres.error}`);
          } else {
            g.classList.remove('error');
          }
          // Render inline visualisation if _viz data present
          const outputs = bres.outputs || {};
          const viz = outputs._viz;
          if (viz && blocks[bid]) {
            try { renderVizInNode(bid, viz); } catch(e) { console.warn('viz render', bid, e); }
          }
        }

        // Show outputs
        for (const line of (result.console || [])) {
          consoleLog(line);
        }

        if (result.verdict) {
          consoleLog('🏁 Verdict: ' + result.verdict);
        }

        statusEl.textContent = result.verdict || 'done';
        statusEl.className = 'badge ' + (result.verdict === 'PASS' ? 'badge-ok' : result.verdict === 'FAIL' ? 'badge-err' : 'badge-info');
      }
    } catch (err) {
      consoleLog('❌ Execution failed: ' + err.message);
      statusEl.textContent = 'error'; statusEl.className = 'badge badge-err';
    }

    const elapsed = ((performance.now() - t0) / 1000).toFixed(2);
    timeEl.textContent = elapsed + 's';
    consoleLog(`■ === Done (${elapsed}s) ===\n`);

    execRunning = false;
    runBtn.disabled = false; stopBtn.disabled = true;
  }

  function stopExecution() {
    fetch('/flowlab/api/stop', {method: 'POST'}).catch(() => {});
    consoleLog('⏹ Stop requested');
  }

  // ══════════════════════════════════════════════════════════════
  // In-node visualisation renderer (foreignObject + canvas)
  // ══════════════════════════════════════════════════════════════

  const INFERNO = [[0,0,4],[40,11,84],[101,21,110],[159,42,99],[212,72,66],[245,125,21],[250,186,12],[252,255,164]];
  const VIRIDIS = [[68,1,84],[72,36,117],[65,68,135],[53,95,141],[42,120,142],[33,144,141],[39,173,129],[92,200,99],[170,220,50],[253,231,37]];

  function colorscaleRgb(name, t) {
    // t in [0,1] → [r,g,b]
    const palette = name === 'Viridis' ? VIRIDIS : INFERNO;
    const idx = t * (palette.length - 1);
    const lo = Math.floor(idx), hi = Math.min(lo + 1, palette.length - 1);
    const f = idx - lo;
    return [
      Math.round(palette[lo][0] + (palette[hi][0] - palette[lo][0]) * f),
      Math.round(palette[lo][1] + (palette[hi][1] - palette[lo][1]) * f),
      Math.round(palette[lo][2] + (palette[hi][2] - palette[lo][2]) * f),
    ];
  }

  function renderVizInNode(bid, viz) {
    const b = blocks[bid];
    if (!b) return;
    const g = document.getElementById('blk-' + bid);
    if (!g) return;

    // Remove previous viz overlay
    const prev = g.querySelector('.viz-fo');
    if (prev) prev.remove();

    const ports = Math.max(b.def.inputs.length, b.def.outputs.length, 1);
    const vizY = HEADER_H + ports * PORT_SPACING + 10;
    const vizW = b.w - 8;
    const vizH = VIZ_CANVAS_H;

    const fo = document.createElementNS('http://www.w3.org/2000/svg', 'foreignObject');
    fo.classList.add('viz-fo');
    fo.setAttribute('x', 4);
    fo.setAttribute('y', vizY);
    fo.setAttribute('width', vizW);
    fo.setAttribute('height', vizH);

    const div = document.createElement('div');
    div.className = 'viz-container';
    div.style.cssText = `width:${vizW}px;height:${vizH}px;background:#1e1e2e;border-radius:4px;overflow:hidden;position:relative;`;

    switch (viz.type) {
      case 'trace':   _vizTrace(div, viz, vizW, vizH); break;
      case 'xy':      _vizXY(div, viz, vizW, vizH); break;
      case 'fft':     _vizFFT(div, viz, vizW, vizH); break;
      case 'histogram': _vizHistogram(div, viz, vizW, vizH); break;
      case 'gauge':   _vizGauge(div, viz, vizW, vizH); break;
      case 'heatmap': _vizHeatmap(div, viz, vizW, vizH); break;
      case 'table':   _vizTable(div, viz, vizW, vizH); break;
      case 'video':   _vizVideo(div, viz, vizW, vizH); break;
      case 'waterfall': _vizWaterfall(div, viz, vizW, vizH); break;
      default:
        div.innerHTML = `<div style="color:#cdd6f4;padding:8px;font-size:10px;">Unknown viz type: ${viz.type}</div>`;
    }

    fo.appendChild(div);
    g.appendChild(fo);
  }

  /* ── Trace / line chart ──────────────────────────────── */
  function _vizTrace(div, viz, W, H) {
    const c = _makeCanvas(div, W, H);
    const ctx = c.getContext('2d');
    const x = viz.x || [], y = viz.y || [];
    if (!y.length) { _vizEmpty(div, viz.title || 'Trace'); return; }
    const pad = {t:22, b:14, l:6, r:6};
    _drawChartBg(ctx, W, H, viz.title);
    const yMin = Math.min(...y), yMax = Math.max(...y);
    const range = yMax - yMin || 1;
    const pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
    ctx.strokeStyle = '#89b4fa'; ctx.lineWidth = 1.2;
    ctx.beginPath();
    for (let i = 0; i < y.length; i++) {
      const px = pad.l + (i / (y.length - 1 || 1)) * pw;
      const py = pad.t + ph - ((y[i] - yMin) / range) * ph;
      i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
    }
    ctx.stroke();
    _drawAxisLabels(ctx, W, H, pad, x, yMin, yMax, viz.y_label || '');
  }

  /* ── XY scatter ──────────────────────────────────────── */
  function _vizXY(div, viz, W, H) {
    const c = _makeCanvas(div, W, H);
    const ctx = c.getContext('2d');
    const x = viz.x || [], y = viz.y || [];
    if (!x.length) { _vizEmpty(div, viz.title || 'XY'); return; }
    const pad = {t:22, b:14, l:6, r:6};
    _drawChartBg(ctx, W, H, viz.title);
    const xMin = Math.min(...x), xMax = Math.max(...x);
    const yMin = Math.min(...y), yMax = Math.max(...y);
    const xR = xMax - xMin || 1, yR = yMax - yMin || 1;
    const pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
    const isLine = viz.mode && viz.mode.includes('lines');
    if (isLine) {
      ctx.strokeStyle = '#a6e3a1'; ctx.lineWidth = 1.2; ctx.beginPath();
      for (let i = 0; i < x.length; i++) {
        const px = pad.l + ((x[i] - xMin) / xR) * pw;
        const py = pad.t + ph - ((y[i] - yMin) / yR) * ph;
        i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
      }
      ctx.stroke();
    }
    if (!viz.mode || viz.mode.includes('markers')) {
      ctx.fillStyle = '#f38ba8';
      for (let i = 0; i < x.length; i++) {
        const px = pad.l + ((x[i] - xMin) / xR) * pw;
        const py = pad.t + ph - ((y[i] - yMin) / yR) * ph;
        ctx.beginPath(); ctx.arc(px, py, 2, 0, Math.PI * 2); ctx.fill();
      }
    }
  }

  /* ── FFT spectrum ────────────────────────────────────── */
  function _vizFFT(div, viz, W, H) {
    const c = _makeCanvas(div, W, H);
    const ctx = c.getContext('2d');
    const freq = viz.freq_hz || [], amp = viz.amplitude || [];
    if (!amp.length) { _vizEmpty(div, viz.title || 'FFT'); return; }
    const pad = {t:22, b:14, l:6, r:6};
    _drawChartBg(ctx, W, H, viz.title);
    const yMax = Math.max(...amp) || 1;
    const pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
    // Fill area
    ctx.fillStyle = 'rgba(137,180,250,0.3)';
    ctx.beginPath(); ctx.moveTo(pad.l, pad.t + ph);
    for (let i = 0; i < amp.length; i++) {
      const px = pad.l + (i / (amp.length - 1 || 1)) * pw;
      const py = pad.t + ph - (amp[i] / yMax) * ph;
      ctx.lineTo(px, py);
    }
    ctx.lineTo(pad.l + pw, pad.t + ph); ctx.closePath(); ctx.fill();
    // Line
    ctx.strokeStyle = '#89b4fa'; ctx.lineWidth = 1.2; ctx.beginPath();
    for (let i = 0; i < amp.length; i++) {
      const px = pad.l + (i / (amp.length - 1 || 1)) * pw;
      const py = pad.t + ph - (amp[i] / yMax) * ph;
      i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
    }
    ctx.stroke();
    // Peak markers
    if (viz.peaks) {
      ctx.fillStyle = '#f38ba8'; ctx.font = '8px monospace';
      for (const pk of viz.peaks.slice(0, 3)) {
        const fi = freq.length ? freq.findIndex(f => f >= pk.freq_hz) : 0;
        if (fi < 0) continue;
        const px = pad.l + (fi / (amp.length - 1 || 1)) * pw;
        const py = pad.t + ph - (amp[fi] / yMax) * ph;
        ctx.beginPath(); ctx.arc(px, py, 3, 0, Math.PI * 2); ctx.fill();
        ctx.fillText(`${pk.freq_hz}Hz`, px + 4, py - 2);
      }
    }
  }

  /* ── Histogram ───────────────────────────────────────── */
  function _vizHistogram(div, viz, W, H) {
    const c = _makeCanvas(div, W, H);
    const ctx = c.getContext('2d');
    const counts = viz.bin_counts || [], edges = viz.bin_edges || [];
    if (!counts.length) { _vizEmpty(div, viz.title || 'Histogram'); return; }
    const pad = {t:22, b:14, l:6, r:6};
    _drawChartBg(ctx, W, H, viz.title);
    const maxC = Math.max(...counts) || 1;
    const pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
    const barW = pw / counts.length;
    ctx.fillStyle = viz.color || '#89b4fa';
    for (let i = 0; i < counts.length; i++) {
      const barH = (counts[i] / maxC) * ph;
      ctx.fillRect(pad.l + i * barW, pad.t + ph - barH, Math.max(barW - 1, 1), barH);
    }
  }

  /* ── Gauge / meter ───────────────────────────────────── */
  function _vizGauge(div, viz, W, H) {
    const c = _makeCanvas(div, W, H);
    const ctx = c.getContext('2d');
    _drawChartBg(ctx, W, H, '');
    const cx = W / 2, cy = H * 0.62, r = Math.min(W, H) * 0.38;
    const minV = viz.min || 0, maxV = viz.max || 100;
    const val = Math.max(minV, Math.min(maxV, viz.value || 0));
    const range = maxV - minV || 1;
    const pct = (val - minV) / range;
    // Arc background
    const startA = Math.PI * 0.8, endA = Math.PI * 2.2;
    const totalA = endA - startA;
    // Green / yellow / red zones
    const g_end = startA + totalA * ((viz.green_max - minV) / range);
    const y_end = startA + totalA * ((viz.yellow_max - minV) / range);
    ctx.lineWidth = 10; ctx.lineCap = 'round';
    ctx.strokeStyle = '#a6e3a1'; ctx.beginPath(); ctx.arc(cx, cy, r, startA, Math.min(g_end, endA)); ctx.stroke();
    ctx.strokeStyle = '#f9e2af'; ctx.beginPath(); ctx.arc(cx, cy, r, g_end, Math.min(y_end, endA)); ctx.stroke();
    ctx.strokeStyle = '#f38ba8'; ctx.beginPath(); ctx.arc(cx, cy, r, y_end, endA); ctx.stroke();
    // Needle
    const needleA = startA + totalA * pct;
    ctx.strokeStyle = '#cdd6f4'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(needleA) * r * 0.85, cy + Math.sin(needleA) * r * 0.85);
    ctx.stroke();
    // Value text
    ctx.fillStyle = '#cdd6f4'; ctx.font = 'bold 16px monospace'; ctx.textAlign = 'center';
    ctx.fillText(`${viz.value}${viz.unit || ''}`, cx, cy + r * 0.45);
    ctx.font = '10px sans-serif'; ctx.fillText(viz.title || '', cx, 14);
  }

  /* ── Heatmap ─────────────────────────────────────────── */
  function _vizHeatmap(div, viz, W, H) {
    const c = _makeCanvas(div, W, H);
    const ctx = c.getContext('2d');
    const grid = viz.grid || [];
    if (!grid.length) { _vizEmpty(div, viz.title || 'Heatmap'); return; }
    _drawChartBg(ctx, W, H, viz.title);
    const pad = {t:22, b:4, l:4, r:4};
    const rows = grid.length, cols = grid[0] ? grid[0].length : 0;
    if (!cols) return;
    const cw = (W - pad.l - pad.r) / cols, ch = (H - pad.t - pad.b) / rows;
    let gMin = Infinity, gMax = -Infinity;
    for (const row of grid) for (const v of row) { if (v < gMin) gMin = v; if (v > gMax) gMax = v; }
    const gRange = gMax - gMin || 1;
    for (let r = 0; r < rows; r++) {
      for (let c2 = 0; c2 < cols; c2++) {
        const t = (grid[r][c2] - gMin) / gRange;
        const rgb = colorscaleRgb(viz.colorscale || 'Inferno', t);
        ctx.fillStyle = `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
        ctx.fillRect(pad.l + c2 * cw, pad.t + r * ch, Math.ceil(cw), Math.ceil(ch));
      }
    }
  }

  /* ── Table ───────────────────────────────────────────── */
  function _vizTable(div, viz, W, H) {
    const headers = viz.headers || [], rows = viz.rows || [];
    if (!headers.length) { _vizEmpty(div, 'Table'); return; }
    const tbl = document.createElement('div');
    tbl.style.cssText = 'width:100%;height:100%;overflow:auto;font-size:9px;color:#cdd6f4;padding:2px;';
    let html = '<table style="border-collapse:collapse;width:100%;"><thead><tr>';
    for (const h of headers) html += `<th style="border:1px solid #45475a;padding:1px 3px;background:#313244;font-size:8px;white-space:nowrap;">${h}</th>`;
    html += '</tr></thead><tbody>';
    for (const row of rows.slice(0, 15)) {
      html += '<tr>';
      for (const cell of row) {
        const v = typeof cell === 'number' ? cell.toPrecision(4) : String(cell).slice(0, 12);
        html += `<td style="border:1px solid #45475a;padding:1px 3px;font-size:8px;white-space:nowrap;">${v}</td>`;
      }
      html += '</tr>';
    }
    html += '</tbody></table>';
    if (viz.total_rows > 15) html += `<div style="color:#6c7086;font-size:8px;padding:2px;">…${viz.total_rows} total rows</div>`;
    tbl.innerHTML = html;
    div.appendChild(tbl);
  }

  /* ── Live video ──────────────────────────────────────── */
  function _vizVideo(div, viz, W, H) {
    if (viz.error) {
      div.innerHTML = `<div style="color:#f38ba8;padding:8px;font-size:10px;">📹 ${viz.error}</div>`;
      return;
    }
    const img = document.createElement('img');
    img.src = viz.src || '';
    img.style.cssText = `width:100%;height:100%;object-fit:contain;border-radius:4px;`;
    div.appendChild(img);
  }

  /* ── Waterfall / spectrogram ─────────────────────────── */
  function _vizWaterfall(div, viz, W, H) {
    const c = _makeCanvas(div, W, H);
    const ctx = c.getContext('2d');
    const grid = viz.grid || [];
    if (!grid.length || !grid[0].length) { _vizEmpty(div, viz.title || 'Waterfall'); return; }
    _drawChartBg(ctx, W, H, viz.title);
    const pad = {t:22, b:4, l:4, r:4};
    const cols = grid[0].length;
    const nRows = viz.n_rows || 32;
    // Pad grid to n_rows height (blank rows at top)
    const fullGrid = [];
    for (let i = 0; i < nRows - grid.length; i++) fullGrid.push(new Array(cols).fill(0));
    for (const row of grid) fullGrid.push(row);
    const rows = fullGrid.length;
    const cw = (W - pad.l - pad.r) / cols, ch = (H - pad.t - pad.b) / rows;
    let gMin = Infinity, gMax = -Infinity;
    for (const row of fullGrid) for (const v of row) { if (v < gMin) gMin = v; if (v > gMax) gMax = v; }
    const gRange = gMax - gMin || 1;
    for (let r = 0; r < rows; r++) {
      for (let c2 = 0; c2 < cols; c2++) {
        const t = (fullGrid[r][c2] - gMin) / gRange;
        const rgb = colorscaleRgb(viz.colorscale || 'Inferno', t);
        ctx.fillStyle = `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
        ctx.fillRect(pad.l + c2 * cw, pad.t + r * ch, Math.ceil(cw), Math.ceil(ch));
      }
    }
    // Freq axis label
    const freq = viz.freq_hz || [];
    if (freq.length) {
      ctx.fillStyle = '#6c7086'; ctx.font = '7px monospace';
      ctx.fillText(`0`, pad.l, H - 1);
      ctx.textAlign = 'end';
      ctx.fillText(`${Math.round(freq[freq.length - 1])}Hz`, W - pad.r, H - 1);
    }
  }

  /* ── Canvas helpers ──────────────────────────────────── */
  function _makeCanvas(div, W, H) {
    const c = document.createElement('canvas');
    c.width = W; c.height = H;
    c.style.cssText = 'width:100%;height:100%;';
    div.appendChild(c);
    return c;
  }

  function _drawChartBg(ctx, W, H, title) {
    ctx.fillStyle = '#1e1e2e'; ctx.fillRect(0, 0, W, H);
    // Grid lines
    ctx.strokeStyle = '#313244'; ctx.lineWidth = 0.5;
    for (let x = 0; x < W; x += 40) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
    for (let y = 0; y < H; y += 30) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
    if (title) {
      ctx.fillStyle = '#cdd6f4'; ctx.font = '10px sans-serif'; ctx.textAlign = 'left';
      ctx.fillText(title, 6, 14);
    }
  }

  function _drawAxisLabels(ctx, W, H, pad, x, yMin, yMax, yLabel) {
    ctx.fillStyle = '#6c7086'; ctx.font = '7px monospace';
    ctx.textAlign = 'left';
    ctx.fillText(yMax.toPrecision(3), pad.l, pad.t - 2);
    ctx.fillText(yMin.toPrecision(3), pad.l, H - pad.b + 10);
    if (x.length) {
      ctx.textAlign = 'right';
      const last = x[x.length - 1];
      ctx.fillText(typeof last === 'number' ? last.toFixed(2) : String(last), W - pad.r, H - 1);
    }
  }

  function _vizEmpty(div, title) {
    div.innerHTML = `<div style="color:#6c7086;padding:16px;text-align:center;font-size:10px;">${title || 'No data'}<br>⏳ Run to populate</div>`;
  }

  // ══════════════════════════════════════════════════════════════
  // Console
  // ══════════════════════════════════════════════════════════════

  function consoleLog(msg) {
    const el = document.getElementById('console-output');
    el.textContent += msg + '\n';
    el.scrollTop = el.scrollHeight;
  }

  // ══════════════════════════════════════════════════════════════
  // Button bindings
  // ══════════════════════════════════════════════════════════════

  document.getElementById('btn-run').addEventListener('click', runDiagram);
  document.getElementById('btn-stop').addEventListener('click', stopExecution);
  document.getElementById('btn-clear').addEventListener('click', () => {
    if (Object.keys(blocks).length === 0 || confirm('Clear all blocks and wires?')) {
      clearCanvas(); consoleLog('🗑 Canvas cleared');
    }
  });
  document.getElementById('btn-save').addEventListener('click', saveDiagram);
  document.getElementById('btn-load').addEventListener('click', loadDiagram);
  document.getElementById('btn-export').addEventListener('click', exportDiagram);
  document.getElementById('btn-export-py').addEventListener('click', exportPython);

  // ── HIL buttons ──────────────────────────────────────────────
  document.getElementById('btn-save-hil').addEventListener('click', openSaveHilModal);
  document.getElementById('btn-run-hil').addEventListener('click', runAsHil);
  document.getElementById('btn-import-hil').addEventListener('click', openImportHilModal);
  document.getElementById('btn-editor-core').addEventListener('click', () => {
    window.open('/flowlab/editor-core', '_blank', 'noopener');
  });

  // ── Import button ──────────────────────────────────────────
  document.getElementById('btn-import-py').addEventListener('click', openImportModal);

  // ══════════════════════════════════════════════════════════════
  // HIL Integration — Save as HIL Profile
  // ══════════════════════════════════════════════════════════════

  async function openSaveHilModal() {
    const diagram = serialize();
    if (!diagram.blocks || diagram.blocks.length === 0) {
      consoleLog('⚠ Nothing to export — canvas is empty');
      return;
    }
    // Get preview from server
    try {
      const res = await fetch('/flowlab/api/export_hil', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({diagram}),
      });
      const j = await res.json();
      if (j.error) { consoleLog('❌ ' + j.error); return; }

      document.getElementById('hil-save-preview').textContent = JSON.stringify(j.profile, null, 2);
      document.getElementById('hil-save-name').value = j.profile.name || 'flowlab_export';
      document.getElementById('hil-save-modal').style.display = 'flex';
    } catch (err) {
      consoleLog('❌ HIL export error: ' + err.message);
    }
  }

  document.getElementById('hil-save-confirm-btn').addEventListener('click', async () => {
    const name = document.getElementById('hil-save-name').value.trim() || 'flowlab_export';
    const diagram = serialize();
    try {
      const res = await fetch('/flowlab/api/save_hil', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({diagram, name}),
      });
      const j = await res.json();
      if (j.error) {
        consoleLog('❌ ' + j.error);
      } else {
        consoleLog('🧪 HIL profile saved: ' + j.path);
      }
    } catch (err) {
      consoleLog('❌ Save HIL error: ' + err.message);
    }
    document.getElementById('hil-save-modal').style.display = 'none';
  });

  document.getElementById('hil-save-download-btn').addEventListener('click', () => {
    const previewText = document.getElementById('hil-save-preview').textContent;
    const name = document.getElementById('hil-save-name').value.trim() || 'flowlab_export';
    const blob = new Blob([previewText], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = name + '.json'; a.click();
    URL.revokeObjectURL(url);
    consoleLog('⬇ Downloaded HIL profile: ' + name + '.json');
    document.getElementById('hil-save-modal').style.display = 'none';
  });

  document.getElementById('hil-save-cancel-btn').addEventListener('click', () => {
    document.getElementById('hil-save-modal').style.display = 'none';
  });

  // ══════════════════════════════════════════════════════════════
  // HIL Integration — Run as HIL Test
  // ══════════════════════════════════════════════════════════════

  async function runAsHil() {
    const diagram = serialize();
    if (!diagram.blocks || diagram.blocks.length === 0) {
      consoleLog('⚠ Nothing to run — canvas is empty');
      return;
    }
    consoleLog('\n🚀 === Converting & launching as HIL test ===');
    try {
      const res = await fetch('/flowlab/api/run_hil', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({diagram, name: 'flowlab_hil_run'}),
      });
      const j = await res.json();
      if (j.error) {
        consoleLog('❌ ' + j.error);
        return;
      }
      const steps = (j.profile && j.profile.steps) ? j.profile.steps.length : 0;
      consoleLog('📋 Profile generated: ' + steps + ' steps');
      consoleLog('🏃 Execution: ' + j.execution);
      if (j.message) consoleLog('ℹ ' + j.message);
      if (j.execution === 'started') {
        consoleLog('✅ HIL test started! Monitor at /hil/');
      }
    } catch (err) {
      consoleLog('❌ Run as HIL error: ' + err.message);
    }
  }

  // ══════════════════════════════════════════════════════════════
  // HIL Integration — Import HIL Profile
  // ══════════════════════════════════════════════════════════════

  let selectedHilProfile = null;

  async function openImportHilModal() {
    selectedHilProfile = null;
    document.getElementById('hil-json-input').value = '';
    document.getElementById('hil-file-input').value = '';

    // Load available profiles
    const listEl = document.getElementById('hil-profile-list');
    listEl.innerHTML = '<span style="color:var(--fg-dim);font-size:11px">Loading…</span>';
    document.getElementById('hil-modal').style.display = 'flex';

    try {
      const res = await fetch('/flowlab/api/hil_profiles');
      const j = await res.json();
      listEl.innerHTML = '';

      if (!j.profiles || j.profiles.length === 0) {
        listEl.innerHTML = '<span style="color:var(--fg-dim);font-size:11px">No profiles found in profiles/</span>';
        return;
      }

      for (const p of j.profiles) {
        const el = document.createElement('div');
        el.className = 'profile-item';
        el.innerHTML = `
          <span class="profile-name">${p.name}</span>
          <span class="profile-desc">${p.description || ''}</span>
          <span class="profile-steps">${p.steps} steps</span>
        `;
        el.addEventListener('click', () => {
          listEl.querySelectorAll('.profile-item').forEach(x => x.classList.remove('selected'));
          el.classList.add('selected');
          selectedHilProfile = p.name;
        });
        listEl.appendChild(el);
      }
    } catch (err) {
      listEl.innerHTML = '<span style="color:#f38ba8;font-size:11px">Error loading profiles</span>';
    }
  }

  document.getElementById('hil-import-btn').addEventListener('click', async () => {
    const jsonInput = document.getElementById('hil-json-input').value.trim();
    const fileInput = document.getElementById('hil-file-input');

    let importBody = null;

    // Priority: file > JSON text > selected profile
    if (fileInput.files && fileInput.files.length > 0) {
      try {
        const text = await fileInput.files[0].text();
        const profile = JSON.parse(text);
        importBody = {profile};
      } catch (err) {
        consoleLog('❌ Invalid JSON file: ' + err.message);
        return;
      }
    } else if (jsonInput) {
      try {
        const profile = JSON.parse(jsonInput);
        importBody = {profile};
      } catch (err) {
        consoleLog('❌ Invalid JSON: ' + err.message);
        return;
      }
    } else if (selectedHilProfile) {
      importBody = {name: selectedHilProfile};
    } else {
      consoleLog('⚠ Select a profile, paste JSON, or upload a file');
      return;
    }

    try {
      const res = await fetch('/flowlab/api/import_hil', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(importBody),
      });
      const j = await res.json();
      if (j.error) {
        consoleLog('❌ Import error: ' + j.error);
        return;
      }
      if (j.diagram) {
        // Confirm if canvas is not empty
        if (Object.keys(blocks).length > 0) {
          if (!confirm('Replace current diagram with imported HIL test?')) return;
        }
        deserialize(j.diagram);
        const n = (j.diagram.blocks || []).length;
        consoleLog('📥 Imported HIL profile → ' + n + ' blocks');
      } else {
        consoleLog('⚠ No diagram returned from import');
      }
    } catch (err) {
      consoleLog('❌ Import error: ' + err.message);
    }
    document.getElementById('hil-modal').style.display = 'none';
  });

  document.getElementById('hil-cancel-btn').addEventListener('click', () => {
    document.getElementById('hil-modal').style.display = 'none';
  });

  // Close modals on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.getElementById('hil-modal').style.display = 'none';
      document.getElementById('hil-save-modal').style.display = 'none';
      document.getElementById('tutorial-modal').style.display = 'none';
      document.getElementById('import-modal').style.display = 'none';
    }
  });

  // Close modals on overlay click
  document.getElementById('hil-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) e.currentTarget.style.display = 'none';
  });
  document.getElementById('hil-save-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) e.currentTarget.style.display = 'none';
  });
  document.getElementById('import-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) e.currentTarget.style.display = 'none';
  });

  // ══════════════════════════════════════════════════════════════
  // Import Diagram from .py or .json
  // ══════════════════════════════════════════════════════════════

  let selectedImportDiagram = null;

  async function openImportModal() {
    selectedImportDiagram = null;
    document.getElementById('import-file-input').value = '';

    // Load available saved diagrams
    const listEl = document.getElementById('import-diagram-list');
    listEl.innerHTML = '<span style="color:var(--fg-dim);font-size:11px">Loading…</span>';
    document.getElementById('import-modal').style.display = 'flex';

    try {
      const res = await fetch('/flowlab/api/list');
      const j = await res.json();
      listEl.innerHTML = '';

      if (!j.diagrams || j.diagrams.length === 0) {
        listEl.innerHTML = '<span style="color:var(--fg-dim);font-size:11px">No saved diagrams found</span>';
        return;
      }

      for (const name of j.diagrams) {
        const el = document.createElement('div');
        el.className = 'profile-item';
        el.innerHTML = `<span class="profile-name">${name}</span>`;
        el.addEventListener('click', () => {
          listEl.querySelectorAll('.profile-item').forEach(x => x.classList.remove('selected'));
          el.classList.add('selected');
          selectedImportDiagram = name;
        });
        listEl.appendChild(el);
      }
    } catch (err) {
      listEl.innerHTML = '<span style="color:#f38ba8;font-size:11px">Error loading diagrams</span>';
    }
  }

  document.getElementById('import-confirm-btn').addEventListener('click', async () => {
    const fileInput = document.getElementById('import-file-input');

    // Priority: file upload > selected saved diagram
    if (fileInput.files && fileInput.files.length > 0) {
      const file = fileInput.files[0];
      const formData = new FormData();
      formData.append('file', file);

      try {
        consoleLog('📤 Importing from ' + file.name + '...');
        const res = await fetch('/flowlab/api/import_diagram', {
          method: 'POST',
          body: formData,
        });
        const j = await res.json();
        if (j.error) {
          consoleLog('❌ Import error: ' + j.error);
          return;
        }
        if (j.diagram) {
          if (Object.keys(blocks).length > 0) {
            if (!confirm('Replace current diagram with imported test sequence?')) return;
          }
          deserialize(j.diagram);
          const n = (j.diagram.blocks || []).length;
          consoleLog('📤 Imported from ' + file.name + ' (' + j.source + ') → ' + n + ' blocks');
        }
      } catch (err) {
        consoleLog('❌ Import error: ' + err.message);
      }
    } else if (selectedImportDiagram) {
      try {
        consoleLog('📤 Loading saved diagram: ' + selectedImportDiagram + '...');
        const res = await fetch('/flowlab/api/load?name=' + encodeURIComponent(selectedImportDiagram));
        const j = await res.json();
        if (j.diagram) {
          if (Object.keys(blocks).length > 0) {
            if (!confirm('Replace current diagram with saved diagram?')) return;
          }
          deserialize(j.diagram);
          const n = (j.diagram.blocks || []).length;
          consoleLog('📤 Loaded diagram: ' + selectedImportDiagram + ' → ' + n + ' blocks');
        } else {
          consoleLog('⚠ No diagram data found');
        }
      } catch (err) {
        consoleLog('❌ Load error: ' + err.message);
      }
    } else {
      consoleLog('⚠ Select a saved diagram or upload a .py/.json file');
      return;
    }

    document.getElementById('import-modal').style.display = 'none';
  });

  document.getElementById('import-cancel-btn').addEventListener('click', () => {
    document.getElementById('import-modal').style.display = 'none';
  });

  // ══════════════════════════════════════════════════════════════
  // Tutorial / Component Reference
  // ══════════════════════════════════════════════════════════════

  const TUTORIAL_CATEGORY_INTROS = {
    'Instruments': {
      icon: '🔌', desc: 'Source blocks that generate, capture, or replay data. These are typically the starting nodes of your dataflow.',
      tips: [
        'Instrument blocks have no inputs — they produce data from hardware, files, or simulation.',
        'Connect an Instrument output to Analysis or I/O blocks to process and visualize.',
        'Use Simulated Meter for offline testing before connecting real hardware.',
      ]
    },
    'Analysis': {
      icon: '📊', desc: 'Signal processing and measurement blocks. Apply filters, compute statistics, detect edges, and extract features from traces.',
      tips: [
        'Most Analysis blocks accept a power_trace input and output a processed trace or dict.',
        'Chain multiple filters for complex signal conditioning (e.g. Band-Pass → Moving Average).',
        'Use Statistics as a quick way to get mean/max/min/std/RMS values from any trace.',
      ]
    },
    'Vision': {
      icon: '🔍', desc: 'Image processing and visual inspection blocks for AOI, thermal, and machine vision tasks.',
      tips: [
        'Use AOI Camera or Thermal Camera as the image source.',
        'Chain vision blocks: Camera → Resize → Threshold → Blob Detect for a simple inspection pipeline.',
        'Color Detect sliders make it easy to dial in HSV ranges interactively.',
      ]
    },
    'Math': {
      icon: 'ƒ', desc: 'Mathematical operations, type conversions, and value transformations.',
      tips: [
        'Expression block supports any Python expression — use variables a, b for the two inputs.',
        'Constant block can emit any type: float, int, str, bool, list, or dict.',
        'Use Unit Convert for common engineering conversions (A→uA, V→mV, dBm→mW, etc.).',
      ]
    },
    'Data': {
      icon: '{}→', desc: 'Data manipulation — extract, combine, parse, and format structured data.',
      tips: [
        'Dict Get is your key tool for pulling values out of result dictionaries.',
        'Format String uses Python f-string syntax: {a} and {b} refer to the two inputs.',
        'Type Cast can convert between all Python types including JSON string serialization.',
      ]
    },
    'I/O': {
      icon: '🖥️', desc: 'Output and visualization blocks — display values, plot charts, save files, and log messages.',
      tips: [
        'Display block auto-detects format: dict→JSON, trace→plot, scalar→text.',
        'Gauge block creates a live visual meter — great for monitoring thresholds.',
        'Use Assert block to add pass/fail checks to your test pipeline.',
      ]
    },
    'Flow': {
      icon: '🚦', desc: 'Flow control blocks for sequencing, branching, looping, and error handling.',
      tips: [
        'Delay block pauses execution — useful for hardware settle time.',
        'Gate (If) routes data to true_out or false_out based on a boolean condition.',
        'Try/Catch wraps upstream execution in error handling.',
      ]
    },
    'Actions': {
      icon: '⌨️', desc: 'Hardware interaction blocks — shell commands, HTTP, serial, GPIO, and pre-built test sequences.',
      tips: [
        'Sleep Test and TX Burst Test are complete measurement profiles ready to run.',
        'Shell Command can trigger external tools, flashing, or build scripts.',
        'Serial Send supports AT commands, UART protocols, and debug probes.',
      ]
    },
    'CAN Bus': {
      icon: '🔌', desc: 'CAN bus communication, capture, decoding, and reverse-engineering analysis blocks.',
      tips: [
        'Use CAN Receive to capture traffic, then pipe into CAN Decode for CANopen layer info.',
        'CAN Analyze performs deep reverse-engineering: counter detection, CRC guessing, bit transitions, signal extraction.',
        'CAN Replay re-transmits captured traffic — useful for regression testing and fuzzing.',
        'Supports PCAN, SocketCAN, Vector, Kvaser, IXXAT, and virtual (simulation) interfaces.',
      ]
    }
  };

  function buildTutorialBlockContent(def) {
    let h = `<h4>${def.icon} ${def.label} <span class="tut-badge">${def.type}</span></h4>`;
    h += `<div class="tut-hint">${def.hint}</div>`;

    // Inputs
    if (def.inputs.length) {
      h += '<div class="tut-section"><h5>Inputs</h5>';
      for (const p of def.inputs) h += `<span class="tut-port in">● ${p.name} <small>(${p.dtype})</small></span>`;
      h += '</div>';
    } else {
      h += '<div class="tut-section"><h5>Inputs</h5><span style="font-size:11px;color:var(--fg-dim)">None — this is a source block</span></div>';
    }

    // Outputs
    if (def.outputs.length) {
      h += '<div class="tut-section"><h5>Outputs</h5>';
      for (const p of def.outputs) h += `<span class="tut-port out">● ${p.name} <small>(${p.dtype})</small></span>`;
      h += '</div>';
    }

    // Params
    const params = Object.entries(def.params || {});
    if (params.length) {
      h += '<div class="tut-section"><h5>Parameters</h5>';
      h += '<table class="tut-param-table"><tr><th>Name</th><th>Type</th><th>Default</th><th>Range</th></tr>';
      for (const [k, m] of params) {
        let range = '—';
        if (m.type === 'slider') range = `${m.min} … ${m.max} (step ${m.step})`;
        else if (m.type === 'select') range = (m.options||[]).join(', ');
        const defVal = typeof m.default === 'boolean' ? (m.default ? '✓' : '✗') : m.default;
        h += `<tr><td>${k}</td><td>${m.type}</td><td>${defVal}</td><td>${range}</td></tr>`;
      }
      h += '</table></div>';
    }

    // Usage tip
    const catInfo = TUTORIAL_CATEGORY_INTROS[def.cat];
    h += '<div class="tut-tip">💡 <strong>Category:</strong> ' + def.cat + (catInfo ? ' — ' + catInfo.desc : '') + '</div>';
    return h;
  }

  function buildTutorialCategoryContent(cat) {
    const info = TUTORIAL_CATEGORY_INTROS[cat];
    const items = BLOCK_CATALOGUE.filter(d => d.cat === cat);
    let h = `<h4>${info ? info.icon : '📦'} ${cat}</h4>`;
    h += `<div class="tut-cat-overview"><p>${info ? info.desc : ''}</p>`;
    h += `<p>Contains <strong>${items.length}</strong> components:</p></div>`;

    if (info && info.tips.length) {
      h += '<div class="tut-section"><h5>Tips & Best Practices</h5><ul>';
      for (const t of info.tips) h += `<li>${t}</li>`;
      h += '</ul></div>';
    }

    h += '<div class="tut-section"><h5>Components in this category</h5>';
    for (const d of items) {
      h += `<div style="padding:3px 0;font-size:12px;cursor:pointer" class="tut-cat-link" data-type="${d.type}">${d.icon} <strong>${d.label}</strong> — ${d.hint}</div>`;
    }
    h += '</div>';
    return h;
  }

  function renderTutorialNav(filter) {
    const nav = document.getElementById('tutorial-nav');
    nav.innerHTML = '';
    const lc = (filter || '').toLowerCase();
    let currentCat = '';
    for (const def of BLOCK_CATALOGUE) {
      if (lc && !def.label.toLowerCase().includes(lc) && !def.type.toLowerCase().includes(lc) && !def.cat.toLowerCase().includes(lc) && !def.hint.toLowerCase().includes(lc)) continue;
      if (def.cat !== currentCat) {
        currentCat = def.cat;
        const catDiv = document.createElement('div');
        catDiv.className = 'tut-cat';
        catDiv.textContent = currentCat;
        catDiv.style.cursor = 'pointer';
        catDiv.addEventListener('click', () => {
          nav.querySelectorAll('.tut-item').forEach(i => i.classList.remove('active'));
          document.getElementById('tutorial-content').innerHTML = buildTutorialCategoryContent(currentCat);
          // Bind inline component links
          document.querySelectorAll('.tut-cat-link').forEach(el => {
            el.addEventListener('click', () => {
              const d = BLOCK_CATALOGUE.find(x => x.type === el.dataset.type);
              if (d) {
                document.getElementById('tutorial-content').innerHTML = buildTutorialBlockContent(d);
                nav.querySelectorAll('.tut-item').forEach(i => i.classList.remove('active'));
                const active = nav.querySelector(`.tut-item[data-type="${d.type}"]`);
                if (active) active.classList.add('active');
              }
            });
          });
        });
        nav.appendChild(catDiv);
      }
      const item = document.createElement('div');
      item.className = 'tut-item';
      item.dataset.type = def.type;
      item.textContent = def.icon + ' ' + def.label;
      item.addEventListener('click', () => {
        nav.querySelectorAll('.tut-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        document.getElementById('tutorial-content').innerHTML = buildTutorialBlockContent(def);
      });
      nav.appendChild(item);
    }
  }

  // Tutorial button handler
  document.getElementById('btn-tutorial').addEventListener('click', () => {
    document.getElementById('tutorial-modal').style.display = 'flex';
    document.getElementById('tutorial-search').value = '';
    renderTutorialNav('');
    // Show welcome content
    const content = document.getElementById('tutorial-content');
    let h = '<h4>❓ FlowLab Component Reference</h4>';
    h += '<div class="tut-cat-overview">';
    h += '<p>Welcome to the FlowLab component reference! This guide covers all <strong>' + BLOCK_CATALOGUE.length + '</strong> blocks across <strong>' + Object.keys(TUTORIAL_CATEGORY_INTROS).length + '</strong> categories.</p>';
    h += '<p>Click a <strong>category header</strong> in the sidebar for an overview, or click any <strong>component</strong> for detailed documentation including inputs, outputs, parameters, and usage tips.</p>';
    h += '</div>';
    h += '<div class="tut-section"><h5>Quick Start</h5><ol>';
    h += '<li><strong>Drag</strong> blocks from the left palette onto the canvas</li>';
    h += '<li><strong>Connect</strong> outputs (orange) to inputs (teal) by clicking ports</li>';
    h += '<li><strong>Configure</strong> parameters in the right properties panel — use <em>sliders</em> for quick adjustment</li>';
    h += '<li>Press <strong>▶ Run</strong> (or Ctrl+Enter) to execute the dataflow</li>';
    h += '<li>Results appear in the <strong>Console Output</strong> panel</li>';
    h += '</ol></div>';
    h += '<div class="tut-section"><h5>Categories Overview</h5>';
    for (const [cat, info] of Object.entries(TUTORIAL_CATEGORY_INTROS)) {
      const count = BLOCK_CATALOGUE.filter(d => d.cat === cat).length;
      h += `<div style="padding:4px 0;font-size:12px">${info.icon} <strong>${cat}</strong> (${count} blocks) — ${info.desc}</div>`;
    }
    h += '</div>';
    h += '<div class="tut-section"><h5>Keyboard Shortcuts</h5>';
    h += '<table class="tut-param-table"><tr><th>Key</th><th>Action</th></tr>';
    h += '<tr><td>Ctrl+Enter</td><td>Run diagram</td></tr>';
    h += '<tr><td>Ctrl+S</td><td>Save diagram</td></tr>';
    h += '<tr><td>Delete / Backspace</td><td>Delete selected block</td></tr>';
    h += '<tr><td>Escape</td><td>Deselect / close modals</td></tr>';
    h += '<tr><td>Mouse wheel</td><td>Zoom canvas</td></tr>';
    h += '<tr><td>Right-click wire</td><td>Delete wire</td></tr>';
    h += '</table></div>';
    h += '<div class="tut-tip">💡 <strong>Pro tip:</strong> Use the 🧪 HIL buttons to convert your visual diagram to/from Hardware-In-the-Loop test profiles for automated testing.</div>';
    content.innerHTML = h;
  });

  // Tutorial search
  document.getElementById('tutorial-search').addEventListener('input', (e) => {
    renderTutorialNav(e.target.value);
  });

  // Tutorial close
  document.getElementById('tutorial-close-btn').addEventListener('click', () => {
    document.getElementById('tutorial-modal').style.display = 'none';
  });
  document.getElementById('tutorial-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) e.currentTarget.style.display = 'none';
  });

  // ══════════════════════════════════════════════════════════════
  // Auto-load on startup
  // ══════════════════════════════════════════════════════════════

  loadDiagram();

})();
