package com.autoluyin.demo

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.autoluyin.demo.databinding.ActivityMyPerformanceBinding
import kotlinx.coroutines.launch

/**
 * Sprint 11.2 — 个人本月绩效小结。
 * 调用 GET /api/v1/agent/me/performance（PRD §11.4）。
 */
class MyPerformanceActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMyPerformanceBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMyPerformanceBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ApiClient.appContext = applicationContext
        binding.btnBack.setOnClickListener { finish() }

        loadData()
    }

    private fun loadData() {
        binding.progress.visibility = android.view.View.VISIBLE
        binding.dataBlock.visibility = android.view.View.GONE
        binding.errorText.visibility = android.view.View.GONE

        lifecycleScope.launch {
            try {
                val data = ApiClient.get(this@MyPerformanceActivity).getMyPerformance()
                renderData(data)
            } catch (t: Throwable) {
                val msg = t.message ?: ""
                binding.errorText.text = when {
                    msg.contains("401") || msg.contains("403") -> "登录已失效，请回到主页重新登录"
                    else -> "加载失败：$msg"
                }
                binding.errorText.visibility = android.view.View.VISIBLE
            } finally {
                binding.progress.visibility = android.view.View.GONE
            }
        }
    }

    private fun renderData(d: AgentPerformanceResp) {
        binding.dataBlock.visibility = android.view.View.VISIBLE
        binding.agentName.text = d.name
        binding.yearMonth.text = "统计月份：${d.year_month}"
        binding.monthCalls.text = d.month_calls.toString()
        binding.monthConnected.text = d.month_connected.toString()
        binding.monthPromised.text = d.month_promised_cases.toString()
        binding.monthPaid.text = d.month_paid_cases.toString()
        binding.paidAmount.text = "¥${d.month_paid_amount}"

        binding.conversionRate.text = "承诺→缴费转化率：" +
            (d.conversion_rate?.let { "%.1f%%".format(it * 100) } ?: "—")
        binding.minutesUsage.text = "本月通话时长：${d.minutes_used} 分钟" +
            (d.minutes_quota?.let { " / ${it} 分钟" } ?: "")
        binding.rank.text = "租户内排名：第 ${d.rank_in_tenant} 名"
    }
}
