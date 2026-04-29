package com.autoluyin.demo

import android.Manifest
import android.content.*
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.Settings
import android.text.InputType
import android.view.LayoutInflater
import android.view.ViewGroup
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.autoluyin.demo.databinding.ActivityMainBinding
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val adapter = TaskAdapter(::onCallClick)

    private val uploadDoneReceiver = object : BroadcastReceiver() {
        override fun onReceive(c: Context?, i: Intent?) {
            val callId = i?.getLongExtra("call_log_id", -1) ?: -1
            val taskId = i?.getLongExtra("task_id", -1) ?: -1
            if (callId > 0) showBusinessDialog(callId, taskId)
        }
    }

    private val permLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
            ensureBackendUrlThen { doSelfCheck() }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.tasks.layoutManager = LinearLayoutManager(this)
        binding.tasks.adapter = adapter

        binding.btnSelfCheck.setOnClickListener { ensurePermsThenCheck() }
        binding.btnRefresh.setOnClickListener { loadTasks() }
        binding.btnGrantStorage.setOnClickListener { openManageAllFiles() }
        binding.btnServerUrl.setOnClickListener { showBackendUrlDialog() }

        ensurePermsThenCheck()
    }

    override fun onResume() {
        super.onResume()
        ContextCompat.registerReceiver(
            this, uploadDoneReceiver,
            IntentFilter("com.autoluyin.demo.UPLOAD_DONE"),
            ContextCompat.RECEIVER_NOT_EXPORTED
        )
    }

    override fun onPause() {
        unregisterReceiver(uploadDoneReceiver)
        super.onPause()
    }

    // ---------- 后端地址 ----------
    private fun ensureBackendUrlThen(next: () -> Unit) {
        val url = AppConfig.backendUrl(this)
        if (url.isNullOrBlank()) {
            showBackendUrlDialog(onSaved = next)
        } else {
            renderHeader()
            next()
        }
    }

    private fun showBackendUrlDialog(onSaved: (() -> Unit)? = null) {
        val input = EditText(this).apply {
            inputType = InputType.TYPE_TEXT_VARIATION_URI
            hint = "例如 http://192.168.1.10:8000 或 https://api.your-domain.com"
            setText(AppConfig.backendUrl(this@MainActivity).orEmpty())
        }
        AlertDialog.Builder(this)
            .setTitle("配置后端地址")
            .setMessage("管理员告知的服务器地址；已上线后改地址不需要重装 App")
            .setView(input)
            .setPositiveButton("保存") { _, _ ->
                val v = input.text.toString().trim()
                if (v.isBlank() || !(v.startsWith("http://") || v.startsWith("https://"))) {
                    toast("地址必须以 http:// 或 https:// 开头"); return@setPositiveButton
                }
                AppConfig.saveBackendUrl(this, v)
                renderHeader()
                onSaved?.invoke() ?: doSelfCheck()
            }
            .setNegativeButton("取消", null)
            .show()
    }

    // ---------- 权限 ----------
    private fun ensurePermsThenCheck() {
        val needed = mutableListOf(
            Manifest.permission.CALL_PHONE,
            Manifest.permission.READ_PHONE_STATE,
            Manifest.permission.READ_CALL_LOG,
        )
        if (Build.VERSION.SDK_INT >= 33) {
            needed += Manifest.permission.READ_MEDIA_AUDIO
            needed += Manifest.permission.POST_NOTIFICATIONS
        } else {
            needed += Manifest.permission.READ_EXTERNAL_STORAGE
        }
        val missing = needed.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) permLauncher.launch(missing.toTypedArray())
        else ensureBackendUrlThen { doSelfCheck() }
    }

    private fun openManageAllFiles() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            startActivity(Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                Uri.parse("package:$packageName")))
        }
    }

    // ---------- 自检 + 拉运行时配置 ----------
    private fun doSelfCheck() {
        renderHeader()
        val recDirs = RecordingScanner.listDirsExisting()
        val dirOk = recDirs.isNotEmpty() && (Build.VERSION.SDK_INT < Build.VERSION_CODES.R
                || Environment.isExternalStorageManager())

        lifecycleScope.launch {
            try {
                val api = ApiClient.get(this@MainActivity)
                val resp = api.selfCheck(SelfCheckReq(
                    device_id = DeviceId.get(this@MainActivity),
                    brand = RecordingScanner.deviceBrand(),
                    model = RecordingScanner.deviceModel(),
                    os_version = RecordingScanner.osVersion(),
                    recording_dir_ok = dirOk,
                    recording_toggle_on = recDirs.isNotEmpty(),
                    permissions_ok = true,
                ))
                // 拉取后台运行时配置（候选目录、超时、prompt 版本…）
                runCatching {
                    val cfg = api.deviceConfig(DeviceId.get(this@MainActivity))
                    AppConfig.applyRuntime(this@MainActivity, cfg)
                }
                renderHeader()

                binding.btnRefresh.isEnabled = resp.can_call
                if (resp.can_call) loadTasks()
                else toast("自检未通过，呼叫禁用")
            } catch (t: Throwable) {
                toast("自检失败: ${t.message}")
            }
        }
    }

    private fun renderHeader() {
        val recDirs = RecordingScanner.listDirsExisting()
        binding.statusText.text = buildString {
            append("后端：${AppConfig.backendUrl(this@MainActivity) ?: "未配置"}\n")
            append("设备：${RecordingScanner.deviceModel()}\n")
            append(RecordingScanner.osVersion()).append("\n")
            append("命中录音目录：${recDirs.joinToString().ifEmpty { "无（请检查系统通话录音是否开启）" }}\n")
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R
                && !Environment.isExternalStorageManager()) {
                append("⚠️ 需要授予「所有文件访问权限」才能读 MIUI 录音目录\n")
            }
        }
    }

    private fun loadTasks() {
        lifecycleScope.launch {
            try {
                val list = ApiClient.get(this@MainActivity)
                    .todayTasks(DeviceId.get(this@MainActivity))
                adapter.submit(list)
            } catch (t: Throwable) {
                toast("加载任务失败: ${t.message}")
            }
        }
    }

    // ---------- 一键拨号 ----------
    private fun onCallClick(t: TaskItem) {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CALL_PHONE)
            != PackageManager.PERMISSION_GRANTED) {
            toast("请先授予拨打电话权限"); return
        }
        if (AppConfig.backendUrl(this) == null) {
            toast("请先配置后端地址"); showBackendUrlDialog(); return
        }
        CallWatcherService.start(this, t.id, t.phone)
        startActivity(Intent(Intent.ACTION_CALL, Uri.parse("tel:${t.phone}")))
    }

    // ---------- 业务表单 ----------
    private fun showBusinessDialog(callId: Long, taskId: Long) {
        val task = adapter.findById(taskId) ?: return
        when (task.type) {
            "vote" -> showVoteDialog(callId, task)
            "collection" -> showCollectionDialog(callId, task)
        }
    }

    private fun showVoteDialog(callId: Long, t: TaskItem) {
        @Suppress("UNCHECKED_CAST")
        val opts = (t.payload["options"] as? List<Map<String, Any?>>) ?: emptyList()
        val labels = opts.map { it["label"]?.toString() ?: "?" }.toTypedArray()
        var picked = 0
        AlertDialog.Builder(this)
            .setTitle("登记投票表态：${t.payload["motion_title"]}")
            .setSingleChoiceItems(labels, 0) { _, w -> picked = w }
            .setPositiveButton("提交") { _, _ ->
                submitBiz(callId, mapOf("choice" to labels[picked]))
            }.show()
    }

    private fun showCollectionDialog(callId: Long, t: TaskItem) {
        val items = arrayOf("立即缴", "承诺缴", "推托", "拒缴", "失联")
        var picked = 0
        AlertDialog.Builder(this)
            .setTitle("催收结果（业主：${t.name}）")
            .setSingleChoiceItems(items, 0) { _, w -> picked = w }
            .setPositiveButton("提交") { _, _ ->
                submitBiz(callId, mapOf("intent" to items[picked]))
            }.show()
    }

    private fun submitBiz(callId: Long, payload: Map<String, Any?>) {
        lifecycleScope.launch {
            try {
                ApiClient.get(this@MainActivity).submitBusiness(callId, payload)
                toast("已提交"); loadTasks()
            } catch (t: Throwable) { toast("提交失败: ${t.message}") }
        }
    }

    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_SHORT).show()
}

class TaskAdapter(
    private val onCall: (TaskItem) -> Unit,
) : RecyclerView.Adapter<TaskAdapter.VH>() {

    private val items = mutableListOf<TaskItem>()

    fun submit(list: List<TaskItem>) {
        items.clear(); items.addAll(list); notifyDataSetChanged()
    }
    fun findById(id: Long) = items.firstOrNull { it.id == id }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_task, parent, false)
        return VH(v)
    }
    override fun onBindViewHolder(h: VH, p: Int) = h.bind(items[p])
    override fun getItemCount() = items.size

    inner class VH(v: android.view.View) : RecyclerView.ViewHolder(v) {
        private val title: TextView = v.findViewById(R.id.title)
        private val sub: TextView = v.findViewById(R.id.sub)
        private val btn: android.widget.Button = v.findViewById(R.id.btnCall)
        fun bind(t: TaskItem) {
            val tag = if (t.type == "vote") "[投票]" else "[催收]"
            title.text = "$tag ${t.name}（${t.building ?: ""}${t.room ?: ""}）"
            sub.text = if (t.type == "collection")
                "欠 ${t.payload["amount"]} / ${t.payload["months"]}"
            else "议题：${t.payload["motion_title"]}"
            btn.text = "呼叫 ${t.phone}"
            btn.setOnClickListener { onCall(t) }
        }
    }
}
