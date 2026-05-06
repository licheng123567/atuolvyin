package com.autoluyin.demo.scan

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import com.autoluyin.demo.databinding.ActivityQrScanBinding
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import java.util.concurrent.Executors

/**
 * Sprint 12.4 — 扫码拨号入口。
 *
 * 用 CameraX preview + ML Kit barcode scanning 解析二维码。
 * 期望识别到 `autoluyin://dial?call_id=...&token=...` 形态的 deeplink，
 * 解析后构造 ACTION_VIEW Intent 拉起 DialFromQrActivity（也可由系统按
 * AndroidManifest 的 intent-filter 自动路由）。
 */
class QrScanActivity : AppCompatActivity() {

    private lateinit var binding: ActivityQrScanBinding
    private val analyzerExecutor = Executors.newSingleThreadExecutor()
    private val scanner = BarcodeScanning.getClient()
    @Volatile private var consumed = false

    private val permLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) startCamera()
        else {
            Toast.makeText(this, "需要相机权限以扫码", Toast.LENGTH_SHORT).show()
            finish()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityQrScanBinding.inflate(layoutInflater)
        setContentView(binding.root)
        binding.btnCancel.setOnClickListener { finish() }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
            == PackageManager.PERMISSION_GRANTED) {
            startCamera()
        } else {
            permLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    private fun startCamera() {
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            val provider = providerFuture.get()
            val preview = Preview.Builder().build().also {
                it.setSurfaceProvider(binding.previewView.surfaceProvider)
            }
            val analysis = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()
            analysis.setAnalyzer(analyzerExecutor) { imageProxy ->
                if (consumed) {
                    imageProxy.close()
                    return@setAnalyzer
                }
                val media = imageProxy.image
                if (media == null) {
                    imageProxy.close()
                    return@setAnalyzer
                }
                val input = InputImage.fromMediaImage(
                    media, imageProxy.imageInfo.rotationDegrees,
                )
                scanner.process(input)
                    .addOnSuccessListener { barcodes ->
                        for (b in barcodes) {
                            handleBarcode(b)
                            if (consumed) break
                        }
                    }
                    .addOnFailureListener { e ->
                        Log.w(TAG, "barcode scan failed", e)
                    }
                    .addOnCompleteListener { imageProxy.close() }
            }

            try {
                provider.unbindAll()
                provider.bindToLifecycle(
                    this, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis,
                )
            } catch (e: Exception) {
                Log.e(TAG, "camera bind failed", e)
                Toast.makeText(this, "相机初始化失败", Toast.LENGTH_SHORT).show()
                finish()
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun handleBarcode(b: Barcode) {
        val raw = b.rawValue ?: return
        if (!raw.startsWith("autoluyin://dial")) {
            // Ignore unrelated QR codes silently — keep scanning
            return
        }
        consumed = true
        val uri = Uri.parse(raw)
        val intent = Intent(Intent.ACTION_VIEW, uri).apply {
            // Internal target — ensures it's our DialFromQrActivity even if user
            // has another autoluyin:// handler (defensive).
            setPackage(packageName)
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        runOnUiThread {
            startActivity(intent)
            finish()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        analyzerExecutor.shutdown()
        scanner.close()
    }

    companion object { private const val TAG = "QrScanActivity" }
}
