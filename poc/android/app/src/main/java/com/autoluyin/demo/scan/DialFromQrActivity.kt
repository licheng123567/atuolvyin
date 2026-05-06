package com.autoluyin.demo.scan

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.autoluyin.demo.ApiClient
import com.autoluyin.demo.AppConfig
import com.autoluyin.demo.CallWatcherService
import com.autoluyin.demo.DialInfoResp
import com.autoluyin.demo.databinding.ActivityDialFromQrBinding
import kotlinx.coroutines.launch

/**
 * Sprint 12.4 — QR deeplink 落地页。
 *
 * 入口：扫码 Activity 解析到 `autoluyin://dial?call_id=...&token=...` 后用
 * ACTION_VIEW 拉起本 Activity；也支持系统外其他 App / 浏览器直接拉起。
 *
 * 流程：
 *   1. 取 query 参数 call_id + token
 *   2. 调 GET /api/v1/calls/{call_id}/dial-info?token=... （token 一次性，无需 JWT）
 *   3. 渲染业主信息 → 用户点「一键拨号」→ ACTION_CALL → CallWatcherService 接管挂机后的录音上传
 */
class DialFromQrActivity : AppCompatActivity() {

    private lateinit var binding: ActivityDialFromQrBinding
    private var dialInfo: DialInfoResp? = null
    private var caseId: Long = -1L

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityDialFromQrBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ApiClient.appContext = applicationContext

        binding.btnCancel.setOnClickListener { finish() }
        binding.btnDial.setOnClickListener { startDial() }

        val data: Uri? = intent?.data
        if (data == null || data.scheme != "autoluyin" || data.host != "dial") {
            showError("无效的二维码链接")
            return
        }
        val callId = data.getQueryParameter("call_id")?.toLongOrNull()
        val token = data.getQueryParameter("token")
        if (callId == null || token.isNullOrBlank()) {
            showError("二维码缺少必要参数")
            return
        }
        if (AppConfig.backendUrl(this).isNullOrBlank()) {
            showError("请先在「服务器」中配置后端地址")
            return
        }
        loadDialInfo(callId, token)
    }

    private fun loadDialInfo(callId: Long, token: String) {
        binding.progress.visibility = android.view.View.VISIBLE
        binding.infoBlock.visibility = android.view.View.GONE
        binding.errorText.visibility = android.view.View.GONE

        lifecycleScope.launch {
            try {
                val info = ApiClient.get(this@DialFromQrActivity).getDialInfo(callId, token)
                dialInfo = info
                caseId = info.case_id
                renderInfo(info)
            } catch (t: Throwable) {
                Log.w(TAG, "fetch dial-info failed", t)
                val msg = t.message ?: ""
                val display = when {
                    msg.contains("404") -> "二维码已失效或不存在"
                    msg.contains("410") -> "二维码已被使用或已过期，请重新生成"
                    msg.contains("403") -> "无权访问该案件"
                    else -> "获取案件信息失败：$msg"
                }
                showError(display)
            } finally {
                binding.progress.visibility = android.view.View.GONE
            }
        }
    }

    private fun renderInfo(info: DialInfoResp) {
        binding.infoBlock.visibility = android.view.View.VISIBLE
        binding.ownerName.text = info.owner_name
        binding.ownerPhone.text = info.owner_phone_masked
        binding.address.text = info.address ?: "（无地址信息）"
        val debt = info.debt_amount
        val months = info.months_overdue
        binding.debtInfo.text = if (debt != null) {
            "欠 ¥${"%.2f".format(debt)}" + if (months != null) " · 逾期 $months 月" else ""
        } else {
            ""
        }
        binding.debtInfo.visibility = if (debt != null)
            android.view.View.VISIBLE else android.view.View.GONE
    }

    private fun showError(msg: String) {
        binding.errorText.text = msg
        binding.errorText.visibility = android.view.View.VISIBLE
        binding.infoBlock.visibility = android.view.View.GONE
        binding.progress.visibility = android.view.View.GONE
    }

    private fun startDial() {
        val info = dialInfo ?: return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CALL_PHONE)
            != PackageManager.PERMISSION_GRANTED) {
            Toast.makeText(this, "请先授予拨打电话权限", Toast.LENGTH_LONG).show()
            return
        }
        val phone = info.owner_phone
        CallWatcherService.start(this, info.case_id, phone)
        startActivity(Intent(Intent.ACTION_CALL, Uri.parse("tel:$phone")))
        finish()
    }

    companion object { private const val TAG = "DialFromQrActivity" }
}
