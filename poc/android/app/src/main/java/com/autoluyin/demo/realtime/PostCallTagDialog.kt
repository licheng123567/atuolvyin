package com.autoluyin.demo.realtime

import android.app.AlertDialog
import android.app.Dialog
import android.os.Bundle
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.Spinner
import android.widget.Toast
import androidx.fragment.app.DialogFragment
import com.autoluyin.demo.ApiClient
import com.autoluyin.demo.AppConfig
import com.autoluyin.demo.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class PostCallTagDialog : DialogFragment() {

    companion object {
        private const val ARG_CALL_ID = "call_id"
        private const val ARG_INTENT = "intent"
        private const val ARG_DATE = "promise_date"
        private const val ARG_AMOUNT = "promise_amount"
        private const val ARG_SUMMARY = "summary"

        private val INTENT_OPTIONS = listOf(
            "promise_pay" to "承诺缴费",
            "refuse" to "拒绝缴费",
            "dispute" to "对欠费有异议",
            "no_answer" to "无人接听",
            "wrong_number" to "错号",
        )

        fun newInstance(callId: Long, tag: AudioStreamClient.TagPayload) =
            PostCallTagDialog().apply {
                arguments = Bundle().apply {
                    putLong(ARG_CALL_ID, callId)
                    tag.intent?.let { putString(ARG_INTENT, it) }
                    tag.promiseDate?.let { putString(ARG_DATE, it) }
                    tag.promiseAmount?.let { putDouble(ARG_AMOUNT, it) }
                    tag.summary?.let { putString(ARG_SUMMARY, it) }
                }
            }
    }

    override fun onCreateDialog(savedInstanceState: Bundle?): Dialog {
        val view = layoutInflater.inflate(R.layout.dialog_post_call_tag, null)
        val intentSpinner = view.findViewById<Spinner>(R.id.intentSpinner)
        val dateInput = view.findViewById<EditText>(R.id.promiseDateInput)
        val amountInput = view.findViewById<EditText>(R.id.promiseAmountInput)
        val notesInput = view.findViewById<EditText>(R.id.notesInput)
        val btnCancel = view.findViewById<Button>(R.id.btnCancel)
        val btnSubmit = view.findViewById<Button>(R.id.btnSubmit)

        intentSpinner.adapter = ArrayAdapter(
            requireContext(), android.R.layout.simple_spinner_item,
            INTENT_OPTIONS.map { it.second },
        )

        // Pre-fill from AI tag payload
        val args = requireArguments()
        args.getString(ARG_INTENT)?.let { code ->
            val idx = INTENT_OPTIONS.indexOfFirst { it.first == code }
            if (idx >= 0) intentSpinner.setSelection(idx)
        }
        dateInput.setText(args.getString(ARG_DATE, ""))
        if (args.containsKey(ARG_AMOUNT)) amountInput.setText(args.getDouble(ARG_AMOUNT).toString())
        notesInput.setText(args.getString(ARG_SUMMARY, ""))

        btnCancel.setOnClickListener { dismiss() }
        btnSubmit.setOnClickListener {
            val intentCode = INTENT_OPTIONS[intentSpinner.selectedItemPosition].first
            val date = dateInput.text.toString().ifBlank { null }
            val amount = amountInput.text.toString().toDoubleOrNull()
            val notes = notesInput.text.toString().ifBlank { null }
            submit(args.getLong(ARG_CALL_ID), intentCode, date, amount, notes)
        }

        return AlertDialog.Builder(requireContext()).setView(view).create()
    }

    private fun submit(
        callId: Long, intent: String, promiseDate: String?,
        promiseAmount: Double?, notes: String?,
    ) {
        val token = AppConfig.token(requireContext()) ?: return
        CoroutineScope(Dispatchers.IO).launch {
            val body = buildMap<String, Any> {
                put("intent", intent)
                promiseDate?.let { put("promise_date", it) }
                promiseAmount?.let { put("promise_amount", it) }
                notes?.let { put("notes", it) }
            }
            val resp = runCatching {
                ApiClient.service.patchCallTag(
                    authHeader = "Bearer $token",
                    callId = callId,
                    body = body,
                )
            }
            withContext(Dispatchers.Main) {
                if (resp.isSuccess) {
                    Toast.makeText(requireContext(), "已提交", Toast.LENGTH_SHORT).show()
                    requireActivity().finish()
                } else {
                    Toast.makeText(requireContext(), "提交失败", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }
}
