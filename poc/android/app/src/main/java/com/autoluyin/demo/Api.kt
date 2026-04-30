package com.autoluyin.demo

import android.content.Context
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
data class SelfCheckResp(val can_call: Boolean)

@JsonClass(generateAdapter = true)
data class LoginReq(val phone: String, val password: String)

@JsonClass(generateAdapter = true)
data class LoginResp(val access_token: String, val token_type: String)

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
                    .addInterceptor(AuthInterceptor(ctx))
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

    fun textPart(s: String) = s.toRequestBody("text/plain".toMediaType())

    fun filePart(name: String, file: File, mime: String): MultipartBody.Part =
        MultipartBody.Part.createFormData(name, file.name, file.asRequestBody(mime.toMediaType()))
}
