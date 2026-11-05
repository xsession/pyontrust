package com.pyontrust.android.fast

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.IBinder
import android.os.SystemClock
import android.os.VibrationEffect
import android.os.Vibrator
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.ArrayBlockingQueue
import kotlin.concurrent.thread

/** In-process zero-latency bridge: TouchPadActivity pushes, the service drains. */
object TouchBus {
    data class Sample(val tNs: Long, val action: Int, val x: Float, val y: Float, val pressure: Float)

    private val queue = ArrayDeque<Sample>()

    @Synchronized fun push(s: Sample) {
        if (queue.size < 8192) queue.addLast(s)
    }

    @Synchronized fun drain(): List<Sample> {
        if (queue.isEmpty()) return emptyList()
        val out = ArrayList<Sample>(queue.size)
        while (true) {
            val s = queue.removeFirstOrNull() ?: break
            out.add(s)
        }
        return out
    }
}

/**
 * Fast telemetry service: streams sensors / touch / audio to a PC over TCP with
 * on-device batching and nanoTime timestamps — no per-sample USB round-trips.
 *
 * Protocol (newline-delimited JSON):
 *  PC -> app : {"cmd":"start","streams":["sensors","touch","audio"],"rate_hz":500}
 *              {"cmd":"stop"} | {"cmd":"vibrate","ms":300} | {"cmd":"tone","freq":1000,"ms":400}
 *              {"cmd":"record","ms":2000} | {"cmd":"status"}
 *  app -> PC : {"type":"ack",...} | {"type":"batch","stream":...,"samples":[[tNs,...],...]}
 *              {"type":"event","kind":"touch_down|touch_up|shock","t_ns":...}
 */
class FastTelemetryService : Service(), SensorEventListener {

    companion object {
        const val PORT = 4780
        const val CHANNEL_ID = "fast_telemetry"
        private const val SAMPLE_RATE = 48000
        private const val FRAME_SAMPLES = 96 // ~2.1 ms of audio per energy frame
    }

    private var serverSocket: ServerSocket? = null
    @Volatile private var client: Socket? = null
    @Volatile private var writer: PrintWriter? = null
    @Volatile private var running = false

    private val sensorManager by lazy { getSystemService(Context.SENSOR_SERVICE) as SensorManager }
    private val vibrator by lazy { getSystemService(Context.VIBRATOR_SERVICE) as Vibrator }

    // ring buffers (single producer per stream, single consumer = flusher)
    private val sensorBuf = ArrayBlockingQueue<LongArray>(16384)   // [tNs, type, x, y, z]
    private val audioBuf = ArrayBlockingQueue<LongArray>(16384)    // [tMs, rms, peak]
    private val eventBuf = ArrayBlockingQueue<JSONObject>(2048)

    @Volatile private var streams: Set<String> = emptySet()
    @Volatile private var audioRecord: AudioRecord? = null
    @Volatile private var recordingWav: WavWriter? = null


    override fun onCreate() {
        super.onCreate()
        createChannel()
        startForeground(1, buildNotification("Fast telemetry ready"))
        running = true
        thread(name = "ft-accept") { acceptLoop() }
        registerSensors()
        thread(name = "ft-flush") { flushLoop() }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_STICKY

    override fun onDestroy() {
        running = false
        unregisterSensors()
        stopAudioCapture()
        try { serverSocket?.close() } catch (_: Exception) {}
        closeClient()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createChannel() {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            nm.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "Fast telemetry", NotificationManager.IMPORTANCE_LOW)
            )
        }
    }

    private fun buildNotification(text: String): Notification {
        val intent = Intent(this, TouchPadActivity::class.java)
        return Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("pyontrust fast telemetry")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setContentIntent(android.app.PendingIntent.getActivity(
                this, 0, intent, android.app.PendingIntent.FLAG_IMMUTABLE))
            .build()
    }

    private fun acceptLoop() {
        val ss = ServerSocket(PORT).also { serverSocket = it }
        ss.reuseAddress = true
        while (running) {
            val sock: Socket = try { ss.accept() } catch (_: Exception) { break }
            client = sock
            writer = java.io.PrintWriter(sock.getOutputStream(), true)
            thread(name = "ft-client") { handleClient(sock) }
        }
    }

    private fun handleClient(sock: Socket) {
        val reader = BufferedReader(InputStreamReader(sock.getInputStream()))
        while (running && !sock.isClosed) {
            val line = try { reader.readLine() } catch (_: Exception) { break } ?: break
            handleCommand(line)
        }
        closeClient()
    }

    private fun closeClient() {
        writer = null
        try { client?.close() } catch (_: Exception) {}
        client = null
    }

    private fun ack(ok: Boolean, msg: String) {
        val w = writer ?: return
        synchronized(w) {
            w.println(JSONObject().put("type", "ack").put("ok", ok).put("msg", msg).toString())
        }
    }

    private fun handleCommand(line: String) {
        val cmd: JSONObject = try { JSONObject(line) } catch (_: Exception) { ack(false, "bad json"); return }
        when (cmd.optString("cmd")) {
            "start" -> {
                val arr = cmd.optJSONArray("streams") ?: JSONArray(listOf("sensors", "touch"))
                streams = (0 until arr.length()).mapTo(mutableSetOf()) { arr.getString(it) }
                if ("audio" in streams) startAudioCapture()
                ack(true, "started: ${streams.joinToString(",")}")
            }
            "stop" -> {
                streams = emptySet()
                stopAudioCapture()
                sensorBuf.clear(); audioBuf.clear(); eventBuf.clear()
                ack(true, "stopped")
            }
            "vibrate" -> vibrate(cmd.optInt("ms", 300))
            "tone" -> thread(name = "ft-tone") { playTone(cmd.optDouble("freq", 1000.0), cmd.optInt("ms", 400)) }
            "sonar_tx" -> thread(name = "ft-sonar") {
                val f0 = cmd.optDouble("f0", 2000.0)
                val f1 = cmd.optDouble("f1", 8000.0)
                playChirp(f0, f1, cmd.optInt("ms", 50))
            }
            "record" -> startMicRecording(cmd.optInt("ms", 2000))
            "sonar" -> {
                val f0 = cmd.optDouble("f0", 2000.0)
                val f1 = cmd.optDouble("f1", 8000.0)
                thread(name = "ft-sonar-full") {
                    runSonar(f0, f1, cmd.optInt("tx_ms", 50),
                        cmd.optInt("rec_ms", 400), cmd.optInt("delay_ms", 80))
                }
            }
            "status" -> ack(true, statusJson().toString())
            else -> ack(false, "unknown cmd")
        }
    }


    // ── sensors ────────────────────────────────────────────────────────
    private fun registerSensors() {
        for (type in intArrayOf(
            Sensor.TYPE_ACCELEROMETER, Sensor.TYPE_GYROSCOPE,
            Sensor.TYPE_LIGHT, Sensor.TYPE_PRESSURE,
        )) {
            val s = sensorManager.getDefaultSensor(type) ?: continue
            sensorManager.registerListener(this, s, SensorManager.SENSOR_DELAY_FASTEST)
        }
    }

    private fun unregisterSensors() {
        try { sensorManager.unregisterListener(this) } catch (_: Exception) {}
    }

    override fun onSensorChanged(event: SensorEvent) {
        val t = System.nanoTime()
        val v = floatArrayOf(
            event.values.getOrElse(0) { 0f },
            event.values.getOrElse(1) { 0f },
            event.values.getOrElse(2) { 0f },
        )
        sensorBuf.offer(longArrayOf(t, event.sensor.type.toLong(),
            (v[0] * 1e6).toLong(), (v[1] * 1e6).toLong(), (v[2] * 1e6).toLong()))
        if (event.sensor.type == Sensor.TYPE_ACCELEROMETER) {
            val mag = kotlin.math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
            if (mag > 25.0 && t - lastShockNs > 300_000_000L) { // ~2.5 g spike, 300 ms cooldown
                lastShockNs = t
                eventBuf.offer(JSONObject().put("type", "event").put("kind", "shock")
                    .put("t_ns", t).put("mag_m_s2", mag.toDouble()))
            }
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}

    // ── flusher: batched low-latency writes (single writer thread) ─────
    private var lastShockNs = 0L

    private fun flushLoop() {
        while (running) {
            val w = writer
            if (w != null && streams.isNotEmpty()) {
                sendBatches(w)
            }
            Thread.sleep(10) // event latency budget: <= ~10 ms + socket write
        }
    }

    private fun sendBatches(w: java.io.PrintWriter) {
        synchronized(w) {
            while (true) {
                val ev = eventBuf.poll() ?: break
                w.println(ev.toString())
            }
            if ("sensors" in streams && sensorBuf.isNotEmpty()) {
                val out = ArrayList<LongArray>(256)
                while (out.size < 256) {
                    val s = sensorBuf.poll() ?: break
                    out.add(s)
                }
                emitBatch(w, "sensors", out)
            }
            if ("touch" in streams) {
                val ts = TouchBus.drain()
                if (ts.isNotEmpty()) {
                    for (t in ts) {
                        val kind = when (t.action) {
                            android.view.MotionEvent.ACTION_DOWN -> "touch_down"
                            android.view.MotionEvent.ACTION_UP -> "touch_up"
                            else -> null
                        }
                        if (kind != null) {
                            w.println(JSONObject().put("type", "event").put("kind", kind)
                                .put("t_ns", t.tNs).put("x", t.x.toDouble())
                                .put("y", t.y.toDouble()).toString())
                        }
                    }
                    val arr = JSONArray()
                    for (t in ts) {
                        arr.put(JSONArray().put(t.tNs).put(t.action)
                            .put(t.x.toDouble()).put(t.y.toDouble()).put(t.pressure.toDouble()))
                    }
                    w.println(JSONObject().put("type", "batch").put("stream", "touch")
                        .put("n", ts.size).put("samples", arr).toString())
                }
            }
            if ("audio" in streams && audioBuf.isNotEmpty()) {
                val out = ArrayList<LongArray>(256)
                while (out.size < 256) {
                    val s = audioBuf.poll() ?: break
                    out.add(s)
                }
                emitBatch(w, "audio", out)
            }
        }
    }

    private fun emitBatch(w: java.io.PrintWriter, stream: String, rows: List<LongArray>) {
        val arr = JSONArray()
        for (r in rows) {
            val row = JSONArray()
            for (v in r) row.put(v.toDouble())
            arr.put(row)
        }
        w.println(JSONObject().put("type", "batch").put("stream", stream)
            .put("n", rows.size).put("samples", arr).toString())
    }


    // ── audio: mic energy stream + raw WAV recording + speaker tone ────
    private fun startAudioCapture() {
        if (audioRecord != null) return
        val minBuf = AudioRecord.getMinBufferSize(SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val rec = try {
            AudioRecord(MediaRecorder.AudioSource.MIC, SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, minBuf * 2)
        } catch (_: SecurityException) { ack(false, "RECORD_AUDIO permission missing"); return }
        if (rec.state != AudioRecord.STATE_INITIALIZED) { rec.release(); return }
        audioRecord = rec
        rec.startRecording()
        thread(name = "ft-audio") {
            val buf = ShortArray(FRAME_SAMPLES)
            while (running && audioRecord == rec) {
                val n = try { rec.read(buf, 0, buf.size) } catch (_: Exception) { break }
                if (n <= 0) continue
                var sumSq = 0.0; var peak = 0.0
                for (i in 0 until n) {
                    val x = buf[i].toDouble() / 32768.0
                    sumSq += x * x
                    if (x > peak) peak = x
                }
                audioBuf.offer(longArrayOf(
                    SystemClock.elapsedRealtime(),
                    (kotlin.math.sqrt(sumSq / n) * 1e4).toLong(), // rms * 1e4
                    (peak * 1e4).toLong(),                        // peak * 1e4
                ))
            }
        }
    }

    private fun stopAudioCapture() {
        audioRecord?.let { try { it.stop(); it.release() } catch (_: Exception) {} }
        audioRecord = null
    }

    private fun playTone(freqHz: Double, ms: Int) {
        val track = android.media.AudioTrack(
            android.media.AudioManager.STREAM_MUSIC, SAMPLE_RATE,
            AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT, minBufSize(),
            android.media.AudioTrack.MODE_STREAM)
        val n = (SAMPLE_RATE * ms / 1000).toInt()
        val pcm = ShortArray(n) { i -> (Math.sin(2.0 * Math.PI * freqHz * i / SAMPLE_RATE) * 12000).toInt().toShort() }
        track.play()
        track.write(pcm, 0, n)
        try { Thread.sleep(ms.toLong()) } catch (_: Exception) {}
        track.stop(); track.release()
    }

    private fun minBufSize(): Int = android.media.AudioTrack.getMinBufferSize(
        SAMPLE_RATE, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT).coerceAtLeast(4096)

    /** Linear FM chirp (f0 -> f1 over ms) — the sonar transmit waveform. */
    private fun playChirp(f0: Double, f1: Double, ms: Int) {
        val n = (SAMPLE_RATE * ms / 1000).toInt()
        val pcm = ShortArray(n)
        var phase = 0.0
        for (i in 0 until n) {
            val instF = f0 + (f1 - f0) * i / n.toDouble()
            phase += 2.0 * Math.PI * instF / SAMPLE_RATE
            pcm[i] = (Math.sin(phase) * 14000).toInt().toShort()
        }
        val track = android.media.AudioTrack(
            android.media.AudioManager.STREAM_MUSIC, SAMPLE_RATE,
            AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT, minBufSize(),
            android.media.AudioTrack.MODE_STREAM)
        track.play()
        track.write(pcm, 0, n)
        try { Thread.sleep(ms.toLong()) } catch (_: Exception) {}
        track.stop(); track.release()
    }

    private fun startMicRecording(ms: Int) {
        val dir = getExternalFilesDir(null) ?: filesDir
        val file = java.io.File(dir, "rec_${System.currentTimeMillis()}.wav")
        val minBuf = AudioRecord.getMinBufferSize(SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val rec = try {
            AudioRecord(MediaRecorder.AudioSource.MIC, SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, minBuf * 2)
        } catch (_: SecurityException) { ack(false, "RECORD_AUDIO permission missing"); return }
        if (rec.state != AudioRecord.STATE_INITIALIZED) { rec.release(); return }
        val writer = WavWriter(file, SAMPLE_RATE)
        recordingWav = writer
        thread(name = "ft-rec") {
            rec.startRecording()
            val buf = ShortArray(2048)
            val total = (SAMPLE_RATE * ms / 1000).toInt()
            var written = 0
            while (written < total && running) {
                val n = try { rec.read(buf, 0, buf.size) } catch (_: Exception) { break }
                if (n <= 0) continue
                writer.writePcm(buf, 0, n)
                written += n
            }
            rec.stop(); rec.release()
            writer.close()
            ack(true, "recorded ${file.absolutePath}")
        }
    }

    /**
     * Full sonar ping with device-side timing (no PC round-trips in the critical path):
     * start mic recording -> after delay_ms play chirp on a separate thread -> stop.
     * The ack carries the WAV path; correlation on the PC self-calibrates the offset.
     */
    private fun runSonar(f0: Double, f1: Double, txMs: Int, recMs: Int, delayMs: Int) {
        val dir = getExternalFilesDir(null) ?: filesDir
        val file = java.io.File(dir, "sonar_${System.currentTimeMillis()}.wav")
        val minBuf = AudioRecord.getMinBufferSize(SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val rec = try {
            AudioRecord(MediaRecorder.AudioSource.MIC, SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, minBuf * 2)
        } catch (_: SecurityException) { ack(false, "RECORD_AUDIO permission missing"); return }
        if (rec.state != AudioRecord.STATE_INITIALIZED) { rec.release(); return }

        thread(name = "ft-sonar-tx") {
            Thread.sleep(delayMs.toLong())
            playChirp(f0, f1, txMs)
        }
        val writer = WavWriter(file, SAMPLE_RATE)
        rec.startRecording()
        val buf = ShortArray(2048)
        val total = (SAMPLE_RATE * recMs / 1000).toInt()
        var written = 0
        while (written < total && running) {
            val n = try { rec.read(buf, 0, buf.size) } catch (_: Exception) { break }
            if (n <= 0) continue
            writer.writePcm(buf, 0, n)
            written += n
        }
        rec.stop(); rec.release()
        writer.close()
        ack(true, "sonar ${file.absolutePath}")
    }

    private fun vibrate(ms: Int) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator.vibrate(VibrationEffect.createOneShot(ms.toLong(), VibrationEffect.DEFAULT_AMPLITUDE))
        } else {
            @Suppress("DEPRECATION") vibrator.vibrate(ms.toLong())
        }
        ack(true, "vibrated ${ms}ms")
    }

    private fun statusJson(): JSONObject = JSONObject()
        .put("port", PORT)
        .put("streams", streams.toList())
        .put("sensor_buf", sensorBuf.size())
        .put("audio_buf", audioBuf.size())
        .put("client_connected", client != null && !client!!.isClosed)

}

/** Minimal 16-bit mono WAV writer (44-byte header + PCM). */
class WavWriter(private val file: java.io.File, private val sampleRate: Int) {
    private val out = java.io.BufferedOutputStream(java.io.FileOutputStream(file))
    private var dataBytes = 0L

    fun writePcm(pcm: ShortArray, offset: Int, count: Int) {
        for (i in offset until offset + count) {
            val v = pcm[i].toInt()
            out.write(v and 0xFF); out.write((v shr 8) and 0xFF)
        }
        dataBytes += (count * 2).toLong()
    }

    fun close() {
        out.flush()
        // write header at the end (file is small enough; simplest correct approach: rewrite)
        out.close()
        val bytes = file.readBytes()
        java.io.File(file.absolutePath + ".tmp").delete()
        val fos = java.io.FileOutputStream(file)
        val header = ByteArray(44)
        fun putStr(off: Int, s: String) { for (i in s.indices) header[off + i] = s[i].code.toByte() }
        fun putInt(off: Int, v: Long) { for (i in 0..3) header[off + i] = ((v shr (8 * i)) and 0xFF).toByte() }
        fun putShort(off: Int, v: Int) { header[off] = (v and 0xFF).toByte(); header[off + 1] = ((v shr 8) and 0xFF).toByte() }
        putStr(0, "RIFF"); putInt(4, (36 + dataBytes))
        putStr(8, "WAVE"); putStr(12, "fmt ")
        putInt(16, 16); putShort(20, 1); putShort(22, 1)
        putInt(24, sampleRate.toLong()); putInt(28, (sampleRate * 2).toLong())
        putShort(32, 2); putShort(34, 16)
        putStr(36, "data"); putInt(40, dataBytes)
        fos.write(header); fos.write(bytes); fos.close()
    }
}

