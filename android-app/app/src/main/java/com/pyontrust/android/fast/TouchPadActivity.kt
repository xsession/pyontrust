package com.pyontrust.android.fast

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.view.MotionEvent
import android.view.View
import android.widget.FrameLayout
import android.widget.TextView

/**
 * Full-screen touch pad: captures down/move/up with nanoTime timestamps and
 * pushes them into [TouchBus] (in-process, zero USB latency). The running
 * FastTelemetryService drains the bus and streams events to the PC.
 */
class TouchPadActivity : Activity() {

    private var lastEventNs = 0L
    private val counter = StringBuilder("events: 0")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        val root = FrameLayout(this).apply { setBackgroundColor(Color.BLACK) }
        label = TextView(this).apply {
            text = "pyontrust fast touch pad\nTouch anywhere — events stream to FastLink"
            setTextColor(Color.WHITE)
            textSize = 16f
            gravity = android.view.Gravity.CENTER_HORIZONTAL
        }
        root.addView(label!!, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT).apply {
                topMargin = 240
            })

        val pad = View(this).apply {
            setBackgroundColor(Color.rgb(16, 24, 32))
            setOnTouchListener { v, e ->
                handle(e)
                true // consume all events (including moves) for full-rate capture
            }
        }
        root.addView(pad, FrameLayout.LayoutParams(-1, -1).apply { topMargin = 360 })
        setContentView(root)
    }

    private fun handle(e: MotionEvent) {
        val t = System.nanoTime()
        TouchBus.push(TouchBus.Sample(t, e.action, e.x, e.y, e.pressure))
        if (e.action == MotionEvent.ACTION_DOWN || e.action == MotionEvent.ACTION_UP) {
            lastEventNs = t
            counter.setLength(0)
            counter.append("events: ").append(System.currentTimeMillis())
            label?.text = counter.toString()
        }
    }

    private var label: TextView? = null
}
