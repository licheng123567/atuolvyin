package com.autoluyin.demo

import android.content.Intent
import android.os.Bundle
import android.text.InputType
import android.widget.EditText
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.autoluyin.demo.databinding.ActivitySettingsBinding

/**
 * Sprint 11.3 — 个人设置入口。当前仅含：后端地址、登出、设备信息、版本信息。
 */
class SettingsActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySettingsBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySettingsBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.btnBack.setOnClickListener { finish() }
        binding.btnChangeServer.setOnClickListener { showBackendUrlDialog() }
        binding.btnLogout.setOnClickListener { confirmLogout() }

        render()
    }

    override fun onResume() {
        super.onResume()
        render()
    }

    private fun render() {
        binding.serverUrl.text = AppConfig.backendUrl(this) ?: "（未配置）"
        binding.loginStatus.text =
            if (AppConfig.jwtToken(this) != null) "已登录" else "未登录"
        binding.deviceInfo.text = buildString {
            append("设备 ID：${DeviceId.get(this@SettingsActivity)}\n")
            append("型号：${RecordingScanner.deviceModel()}\n")
            append(RecordingScanner.osVersion())
        }
        binding.aboutText.text =
            "autoluyin-demo  v${BuildConfig.VERSION_NAME} (build ${BuildConfig.VERSION_CODE})"
    }

    private fun showBackendUrlDialog() {
        val input = EditText(this).apply {
            inputType = InputType.TYPE_TEXT_VARIATION_URI
            hint = "例如 http://192.168.1.10:18000"
            setText(AppConfig.backendUrl(this@SettingsActivity).orEmpty())
        }
        AlertDialog.Builder(this)
            .setTitle("修改后端地址")
            .setMessage("修改后将自动登出，需要重新登录")
            .setView(input)
            .setPositiveButton("保存") { _, _ ->
                val v = input.text.toString().trim()
                if (v.isBlank() || !(v.startsWith("http://") || v.startsWith("https://"))) {
                    showToast("地址必须以 http:// 或 https:// 开头"); return@setPositiveButton
                }
                AppConfig.saveBackendUrl(this, v)
                AppConfig.clearJwtToken(this)
                ApiClient.invalidate()
                render()
                showToast("已保存，请回到主页重新登录")
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun confirmLogout() {
        if (AppConfig.jwtToken(this) == null) {
            showToast("当前未登录"); return
        }
        AlertDialog.Builder(this)
            .setTitle("退出登录")
            .setMessage("退出后需要重新输入手机号 + 密码")
            .setPositiveButton("退出") { _, _ ->
                AppConfig.clearJwtToken(this)
                ApiClient.invalidate()
                render()
                // 回到 MainActivity 让登录弹窗重新拉起
                startActivity(
                    Intent(this, MainActivity::class.java)
                        .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)
                )
                finish()
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun showToast(s: String) =
        android.widget.Toast.makeText(this, s, android.widget.Toast.LENGTH_SHORT).show()
}
