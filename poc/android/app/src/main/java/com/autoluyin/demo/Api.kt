package com.autoluyin.demo

import android.content.Context
import com.autoluyin.demo.auth.AuthErrorInterceptor
import com.squareup.moshi.JsonClass
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import retrofit2.http.*
import java.io.File
import java.util.concurrent.TimeUnit

// ── Data classes ──────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class CaseItem(
    val id: Long,
    val stage: String,
    val amount_owed: String?,
    val months_overdue: Int?,
    val owner: OwnerInfo,
)

@JsonClass(generateAdapter = true)
data class OwnerInfo(
    val name: String,
    val phone: String?,       // non-null for agent_internal
    val phone_masked: String,
    val building: String?,
    val room: String?,
)

@JsonClass(generateAdapter = true)
data class CasesResponse(
    val items: List<CaseItem>,
    val total: Int,
)

@JsonClass(generateAdapter = true)
data class UploadResp(val call_id: Long, val status: String)

@JsonClass(generateAdapter = true)
data class SelfCheckReq(
    val device_id: String,
    val recording_dir_ok: Boolean,
    val recording_toggle_on: Boolean,
    val permissions_ok: Boolean,
)

@JsonClass(generateAdapter = true)
data class SelfCheckResp(
    val can_call: Boolean,
    // v1.6 — 失败项列表："recording_dir" / "recording_toggle" / "permissions"
    val fail_reasons: List<String> = emptyList(),
)

@JsonClass(generateAdapter = true)
data class PushRegPatchRequest(
    val device_id: String,
    val push_reg_id: String,
    val push_provider: String,
)

@JsonClass(generateAdapter = true)
data class PushRegPatchResponse(
    val device_id: String,
    val push_reg_id_set: Boolean,
)

@JsonClass(generateAdapter = true)
data class LoginReq(
    val phone: String,
    val password: String,
    val device_type: String = "app",  // Sprint 15.1 — 多设备踢出
)

@JsonClass(generateAdapter = true)
data class LoginResp(val access_token: String, val token_type: String)

@JsonClass(generateAdapter = true)
data class RegisterDeviceRequest(
    val device_id: String,
    val brand: String?,
    val model: String?,
    val os_version: String?,
    val push_reg_id: String? = null,
    val push_provider: String? = "xiaomi",
)

@JsonClass(generateAdapter = true)
data class RegisterDeviceResponse(
    val status: String? = null,
    // Sprint 12: backend now returns push_reg_id_set so the client can confirm
    // the MiPush token actually reached the server.
    val push_reg_id_set: Boolean? = null,
    val device_id: String? = null,
)

// Sprint 14.2 — App 内拨号 dial-start (PRD §10.1 / §11.6)
@JsonClass(generateAdapter = true)
data class DialStartReq(
    val case_id: Long,
    val device_id: String,
)

@JsonClass(generateAdapter = true)
data class DialStartResp(
    val call_id: Long,
    val recording_mode: String, // live | post (已冻结)
    val status: String,         // "dialing"
)

@JsonClass(generateAdapter = true)
data class HeartbeatResp(
    val call_id: Long,
    val status: String,
    val last_heartbeat_at: String,
)

// Sprint 12.4 — QR dial info response (consumed once per token, no JWT needed)
@JsonClass(generateAdapter = true)
data class DialInfoResp(
    val call_id: Long,
    val case_id: Long,
    val owner_name: String,
    val owner_phone_masked: String,
    val owner_phone: String, // 明文（token 一次性消费 + audit 流水）
    val address: String?,
    val debt_amount: Double?,
    val months_overdue: Int?,
)

// Sprint 11.4 — agent personal performance
@JsonClass(generateAdapter = true)
data class AgentPerformanceResp(
    val user_id: Long,
    val name: String,
    val year_month: String,
    val month_calls: Int,
    val month_connected: Int,
    val month_promised_cases: Int,
    val month_paid_cases: Int,
    val month_paid_amount: String,
    val conversion_rate: Double?,
    val minutes_used: Int,
    val minutes_quota: Int?,
    val rank_in_tenant: Int,
)

// ── API interface ─────────────────────────────────────────────

interface BackendApi {
    @POST("/api/v1/auth/login")
    suspend fun login(@Body body: LoginReq): LoginResp

    @POST("/api/v1/devices/self-check")
    suspend fun selfCheck(@Body body: SelfCheckReq): SelfCheckResp

    @GET("/api/v1/devices/config")
    suspend fun deviceConfig(@Query("device_id") deviceId: String): Map<String, Any?>

    @GET("/api/v1/agent/cases")
    suspend fun myCases(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 50,
    ): CasesResponse

    @POST("/api/v1/devices/register")
    suspend fun registerDevice(
        @Header("Authorization") authHeader: String,
        @Body body: RegisterDeviceRequest,
    ): RegisterDeviceResponse

    @PATCH("/api/v1/devices/push-reg")
    suspend fun patchPushReg(
        @Header("Authorization") authHeader: String,
        @Body body: PushRegPatchRequest,
    ): PushRegPatchResponse

    @POST("api/v1/calls/{call_id}/suggestions/{suggestion_id}/feedback")
    suspend fun postSuggestionFeedback(
        @Header("Authorization") authHeader: String,
        @Path("call_id") callId: Long,
        @Path("suggestion_id") suggestionId: String,
        @Body body: Map<String, String>,
    ): retrofit2.Response<Unit>

    @PATCH("api/v1/calls/{call_id}/tag")
    suspend fun patchCallTag(
        @Header("Authorization") authHeader: String,
        @Path("call_id") callId: Long,
        @Body body: Map<String, @JvmSuppressWildcards Any>,
    ): retrofit2.Response<Unit>

    // Sprint 12.4 — QR dial info: token in query string is the auth credential
    // (one-shot, 10-min TTL). No Authorization header required.
    @GET("/api/v1/calls/{call_id}/dial-info")
    suspend fun getDialInfo(
        @Path("call_id") callId: Long,
        @Query("token") token: String,
    ): DialInfoResp

    // Sprint 11.4 — agent personal performance dashboard
    @GET("/api/v1/agent/me/performance")
    suspend fun getMyPerformance(): AgentPerformanceResp

    // Sprint 14.2 — App 内拨号同步 PC (PRD §11.6)
    @POST("/api/v1/calls/dial-start")
    suspend fun dialStart(@Body body: DialStartReq): DialStartResp

    @POST("/api/v1/calls/{call_id}/heartbeat")
    suspend fun callHeartbeat(@Path("call_id") callId: Long): HeartbeatResp

    @Multipart
    @POST("/api/v1/calls/upload")
    suspend fun uploadRecording(
        @Part("case_id") caseId: okhttp3.RequestBody,
        @Part("device_id") deviceId: okhttp3.RequestBody,
        @Part("callee_phone") calleePhone: okhttp3.RequestBody,
        @Part("started_at") startedAt: okhttp3.RequestBody,
        @Part("ended_at") endedAt: okhttp3.RequestBody,
        @Part("duration_sec") durationSec: okhttp3.RequestBody,
        @Part file: MultipartBody.Part,
    ): UploadResp
}

// ── Auth interceptor ──────────────────────────────────────────

class AuthInterceptor(private val ctx: Context) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = AppConfig.jwtToken(ctx)
        val request = if (token != null) {
            chain.request().newBuilder()
                .addHeader("Authorization", "Bearer $token")
                .build()
        } else {
            chain.request()
        }
        return chain.proceed(request)
    }
}

// ── ApiClient ─────────────────────────────────────────────────

object ApiClient {
    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()

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
                val http = OkHttpClient.Builder()
                    .connectTimeout(15, TimeUnit.SECONDS)
                    .readTimeout(60, TimeUnit.SECONDS)
                    .writeTimeout(120, TimeUnit.SECONDS)
                    .addInterceptor(AuthInterceptor(ctx))           // 前置：加 Bearer token
                    .addInterceptor(AuthErrorInterceptor())         // v2.0 Task 8 — 后置：401 → AuthEventBus
                    .build()
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
        synchronized(this) { current = null; currentBaseUrl = null }
    }

    /**
     * Convenience accessor used by code that doesn't have a Context handy
     * (e.g. coroutines in RealtimeCallActivity). Throws if backend URL not configured.
     */
    lateinit var appContext: android.content.Context

    val service: BackendApi get() = get(appContext)

    val BASE_URL: String get() = currentBaseUrl ?: ""

    fun textPart(s: String) = s.toRequestBody("text/plain".toMediaType())

    fun filePart(name: String, file: File, mime: String): MultipartBody.Part =
        MultipartBody.Part.createFormData(name, file.name, file.asRequestBody(mime.toMediaType()))
}
