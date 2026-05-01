from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://autoluyin:autoluyin_dev@postgres:5432/autoluyin"

    jwt_secret_key: str = "dev-secret-change-in-prod-must-be-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 1440  # 24 hours

    # AES-256-GCM key for phone number encryption (64 hex chars = 32 bytes)
    autoluyin_aes_key: str = ""

    # ==== 录音存储后端：local / minio / oss ====
    storage_backend: str = "local"   # "local" | "minio" | "oss"

    # 本地文件存储
    local_storage_root: str = "/data/recordings"           # 容器内挂载点
    local_storage_public_base: str = "http://localhost:8000"  # ASR 拉录音的对外可达地址
    recording_sign_secret: str = "change-me-in-prod"       # HMAC 签名密钥

    # MinIO（自托管 S3 兼容）
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin_dev"
    minio_bucket: str = "recordings"
    minio_secure: bool = False
    minio_public_host: str = "localhost:9000"

    # 阿里云 OSS
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_endpoint: str = "oss-cn-hangzhou.aliyuncs.com"   # 与 DashScope 同区可走内网
    oss_bucket: str = ""
    oss_use_signed_url: bool = True       # True=ACL私有 + 签名URL（推荐）；False=公共读
    oss_signed_url_expires_sec: int = 3600

    # ==== ASR / LLM 后端选择 ====
    asr_backend: str = "mock"        # "mock" | "dashscope"
    llm_backend: str = "mock"        # "mock" | "api"（OpenAI 兼容协议，含 DeepSeek/Ollama/Qwen）

    # ASR：阿里云 DashScope
    dashscope_api_key: str = ""
    dashscope_asr_model: str = "paraformer-v2"

    # LLM：OpenAI 兼容协议
    # 云 DeepSeek：base_url=https://api.deepseek.com  model=deepseek-chat
    # 本地 Ollama：base_url=http://host.docker.internal:11434/v1  model=qwen2.5:7b
    llm_api_key: str = "sk-placeholder"
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"

    # 兼容旧字段（一段时间后清理）
    deepseek_api_key: str = ""
    deepseek_base_url: str = ""
    deepseek_model: str = ""

    # ==== 实时流式 ASR / 推送 / 实时 LLM ====
    streaming_asr_backend: str = "mock"  # "mock" | "dashscope"

    mipush_backend: str = "mock"  # "mock" | "xiaomi"
    mipush_app_secret: str = ""
    mipush_package_name: str = "com.autoluyin.demo"

    realtime_llm_debounce_sec: int = 5
    realtime_llm_timeout_sec: int = 20
    realtime_llm_silence_ms: int = 1500


settings = Settings()
