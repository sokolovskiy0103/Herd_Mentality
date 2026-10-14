package com.sokolovskiy.herd

import android.Manifest
import android.annotation.SuppressLint
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback

class MainActivity : ComponentActivity() {

    private lateinit var web: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.statusBarColor = Color.parseColor("#1B1230")
        window.navigationBarColor = Color.parseColor("#1B1230")

        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }

        web = WebView(this).apply {
            setBackgroundColor(Color.parseColor("#1B1230"))
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.mediaPlaybackRequiresUserGesture = false
            webChromeClient = WebChromeClient()
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest) = false
            }
        }
        setContentView(web)

        startForegroundService(Intent(this, GameService::class.java))

        // Starting the server touches the network: do it off the UI thread.
        Thread {
            val server = HerdHost.ensure(this)
            runOnUiThread {
                web.loadUrl("http://127.0.0.1:${server.port}/host#${server.hostToken}")
            }
        }.start()

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                // Keep the game running; leave via the notification's "Завершити гру".
                moveTaskToBack(true)
            }
        })
    }

    override fun onDestroy() {
        web.destroy()
        super.onDestroy()
    }
}
