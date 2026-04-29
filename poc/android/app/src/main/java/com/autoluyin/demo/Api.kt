package com.autoluyin.demo

import android.content.Context
import com.squareup.moshi.JsonClass
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import retrofit2.http.*
import java.io.File
import java.util.concurrent.TimeUnit

@JsonClass(generateAdapter = true)
data class TaskItem(
    val id: Long,
    val type: String,
    val payload: Map<String, Any?>,
    val priority: Int,
    val owner_id: Long,
    val name: String,
    val phone: String,
    val building: String?,
    val room: String?,
    val history: List<Map<String, Any?>>?,
)

@JsonClass(generateAdapter = true)
data class UploadResp(val call_log_id: Long, val recording_url: String)

@JsonClass(generateAdapter = true)
data class SelfCheckReq(
    val device_id: String,
    val brand: String,
    val model: String,
    val os_version: String,
    val recording_dir_ok: Boolean,
    val recording_toggle_on: Boolean,
    val permissions_ok: Boolean,
)

@JsonClass(generateAdapter = true)
data class SelfCheckResp(val can_call: Boolean)

interface BackendApi {
    @POST("/api/devices/self-check")
    suspend fun selfCheck(@Body body: SelfCheckReq): SelfCheckResp

    @GET("/api/devices/{device_id}/config")
    suspend fun deviceConfig(@Path("device_id") deviceId: String): Map<String, Any?>

    @GET("/api/tasks/today")
    suspend fun todayTasks(@Query("device_id") deviceId: String): List<TaskItem>

    @Multipart
    @POST("/api/calls/upload")
    suspend fun uploadRecording(
        @Part("task_id") taskId: okhttp3.RequestBody,
        @Part("device_id") deviceId: okhttp3.RequestBody,
        @Part("callee_phone") calleePhone: okhttp3.RequestBody,
        @Part("started_at") startedAt: okhttp3.RequestBody,
        @Part("ended_at") endedAt: okhttp3.RequestBody,
        @Part("duration_sec") durationSec: okhttp3.RequestBody,
        @Part("src_path") srcPath: okhttp3.RequestBody,
        @Part("match_method") matchMethod: okhttp3.RequestBody,
        @Part file: MultipartBody.Part,
    ): UploadResp

    @POST("/api/calls/{id}/business")
    suspend fun submitBusiness(
        @Path("id") callId: Long,
        @Body payload: Map<String, Any?>,
    ): Map<String, Any?>
}

/**
 * 动态 base URL：当用户在 UI 改了后端地址或扫激活码后，调用 [invalidate] 重建实例。
 */
object ApiClient {
    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
    private val http = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(120, TimeUnit.SECONDS)
        .build()

    @Volatile private var current: BackendApi? = null
    @Volatile private var currentBaseUrl: String? = null

    fun get(ctx: Context): BackendApi {
        val configured = AppConfig.backendUrl(ctx)
            ?: error("backend url not configured; let user set it first")
        val cached = current
        if (cached != null && configured == currentBaseUrl) return cached
        return synchronized(this) {
            val again = current
            if (again != null && configured == currentBaseUrl) again
            else {
                val built = Retrofit.Builder()
                    .baseUrl(if (configured.endsWith("/")) configured else "$configured/")
                    .client(http)
                    .addConverterFactory(MoshiConverterFactory.create(moshi))
                    .build()
                    .create(BackendApi::class.java)
                current = built
                currentBaseUrl = configured
                built
            }
        }
    }

    fun invalidate() {
        synchronized(this) {
            current = null
            currentBaseUrl = null
        }
    }

    fun textPart(s: String) = s.toRequestBody("text/plain".toMediaType())

    fun filePart(name: String, file: File, mime: String): MultipartBody.Part =
        MultipartBody.Part.createFormData(
            name, file.name,
            file.asRequestBody(mime.toMediaType()),
        )
}
