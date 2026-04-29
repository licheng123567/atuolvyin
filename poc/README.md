# autoluyin · PoC

外呼录音采集 + 云端 ASR + LLM 抽取的最小可跑工程。
后端：FastAPI + PostgreSQL + MinIO + 阿里云 DashScope ASR + DeepSeek LLM。
端侧：Android（Kotlin），针对小米 / Redmi（MIUI / HyperOS）做了录音目录适配。

## 0. 目录

```
poc/
├── docker-compose.yml         # postgres + minio + backend
├── .env.example               # 拷贝成 .env 后填 API key
├── backend/                   # FastAPI 后端
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── migrations/init.sql    # 建表 + 种子数据
│   └── app/
│       ├── main.py
│       ├── core/              # config / db / storage
│       ├── api/               # devices / tasks / calls
│       ├── services/          # asr_dashscope / llm_deepseek
│       └── workers/pipeline.py
└── android/                   # Android Studio 工程（Kotlin）
    └── app/src/main/java/com/autoluyin/demo/
        ├── MainActivity.kt        # 任务列表 + 一键拨号 + 业务表单
        ├── CallWatcherService.kt  # 通话状态监听 + 录音匹配 + 上传
        ├── RecordingScanner.kt    # 多厂商录音目录扫描器
        └── Api.kt                 # Retrofit + Moshi
```

## 部署顺序与配置层

**先上服务器，再打 APK。** APK 不再硬编码后端地址，首次启动让管理员或坐席输入。

三层配置：

| 层 | 配什么 | 在哪配 | 改动是否要重打 APK |
|----|------|------|-------------------|
| L1 后端地址 | 服务器 URL（如 https://api.your-domain.com）| App 首次启动弹窗输入；存 SharedPreferences | 否 |
| L2 业务运行时配置 | 录音扫描超时、候选目录、上传上限、prompt 版本 | DB 表 `app_config`；APK 自检后调 `GET /api/devices/{id}/config` 拉取 | 否 |
| L3 第三方 API key | DashScope / DeepSeek key | **仅服务端 .env**，永不下发 APK | 否 |

### 生产部署：Caddy 自动 HTTPS（推荐）

`docker-compose.prod.yml` 已提供，与 base compose 合并使用：

```bash
# 1) 改 caddy/Caddyfile：把 your-domain.com 换成你的备案域名，admin 邮箱改对
# 2) 改 .env：POSTGRES_PASSWORD、MINIO_ROOT_PASSWORD、RECORDING_SIGN_SECRET 全部改成长随机串
# 3) 服务器安全组只放 22 / 80 / 443
# 4) 启动：
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

生产覆盖做了什么：

| 项 | base（开发） | prod 覆盖 |
|----|------------|----------|
| Caddy 反代 | 无 | 加了，自动 Let's Encrypt + HTTP/3 |
| Postgres 5432 | 暴露公网 | 撤销，只在 docker 网内 |
| Backend 8000 | 暴露公网 | 撤销，只经 Caddy |
| MinIO 9000 数据口 | 暴露公网 | 撤销，只经 Caddy（`recording.your-domain.com`）|
| **MinIO 9001 控制台** | 暴露公网 | **彻底关闭**，仅可经 SSH tunnel 本地访问 |
| Backend 启动方式 | `--reload`（绑源码） | `--workers 2`（无热重载，跑生产）|
| 重启策略 | 默认 | `unless-stopped` |

**MinIO 控制台访问方式（开发者）**：
```bash
ssh -L 9001:localhost:9001 user@your-server
# 然后浏览器 http://localhost:9001
```

> 用 `STORAGE_BACKEND=local` 或 `oss` 时，Caddyfile 里 `recording.your-domain.com` 那段保持注释；用 `minio` 才打开。

### 阿里云轻量应用服务器（PoC 阶段，无需 HTTPS）
```bash
# 1) 阿里云控制台开 2C4G 轻量应用服务器，华东 2（与 DashScope 同区，ASR 拉取最快）
#    系统：Ubuntu 22.04
# 2) 安全组放行：22（SSH）、80、443、8000（PoC 直接暴露 8000，备案后切 80/443）
# 3) 装 docker compose
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker

# 4) 拉代码
git clone <your-repo> /opt/autoluyin && cd /opt/autoluyin/poc
cp .env.example .env && vi .env   # 填 DASHSCOPE_API_KEY / DEEPSEEK_API_KEY
#    MINIO_PUBLIC_HOST 填这台服务器的公网 IP，例如 47.xx.xx.xx:9000

# 5) 起服务
docker compose up -d --build

# 6) 健康检查
curl http://<你的公网IP>:18000/health
```

> 备案下来后接 Caddy 自动 HTTPS：
> ```
> api.your-domain.com {
>     reverse_proxy localhost:8000
> }
> recording.your-domain.com {
>     reverse_proxy localhost:9000
> }
> ```
> `MINIO_PUBLIC_HOST` 改成 `recording.your-domain.com`。

## 三档"本地化"，看你想要哪种

`.env` 默认 `ASR_BACKEND=mock` + `LLM_BACKEND=mock` + `STORAGE_BACKEND=local`，**零云依赖、零 API key**，docker compose up 起来就能跑通端到端链路。

| 模式 | ASR | LLM | 云依赖 | API key | 适合场景 |
|------|-----|-----|--------|--------|---------|
| **mock（默认）** | 假文字稿（按 task type 选投票/催收两份预设）| 假抽取结果 | 0 | 不需要 | 跑通主链路、Demo、CI |
| 本地 Ollama | mock 或 ngrok+真 ASR | Ollama 跑 Qwen 2.5 / DeepSeek-R1 蒸馏版 | 0 | 不需要 | 真 LLM、隐私敏感 |
| 真云 API | DashScope（需 ngrok 或公网 IP）| DeepSeek 云 | 是 | 需要 | 性能基线、生产 |

### Mac 上 Ollama 一行启动
```bash
brew install ollama
ollama pull qwen2.5:7b      # ~4.7GB，M 系 Mac 几分钟
ollama serve                # 跑在 localhost:11434
```
然后改 `.env`：
```
LLM_BACKEND=api
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_MODEL=qwen2.5:7b
LLM_API_KEY=ollama
```
重启 backend 即可。`host.docker.internal` 是 docker for Mac 让容器访问宿主机的标准方式。

### Android 端连本机 Mac 后端
1. Mac 终端 `ifconfig | grep "inet "` 拿到内网 IP（如 `192.168.1.20`）；
2. 手机和 Mac 连同一 WiFi；
3. APK 首次启动输入 `http://192.168.1.20:18000`；
4. macOS 防火墙弹窗放行 backend 端口；
5. 完成。**不用任何公网 IP / ngrok / 云服务器**，可离线开发。

> 默认 mock 模式下，ASR/LLM 都是本机进程，录音 URL 是不是公网可达完全无所谓——主链路跑通了再考虑接真 ASR。

## 录音存储：三选一

`STORAGE_BACKEND` 一个开关切换，业务代码无感知。

| 选择 | 何时用 | 启动 | 通话 1 万通的成本 |
|------|-------|------|------------------|
| **`local`（默认）** | PoC、单机、几千通以内 | `docker compose up -d` | 0（用服务器磁盘）|
| `minio` | 自托管多机、爱 S3 协议 | `docker compose --profile minio up -d` | 0（自运维）|
| `oss` | 生产规模化 | `docker compose up -d` + 配 `.env` | 几块钱/月 |

### local 模式工作原理
- 录音落到 `/data/recordings/`（compose 卷 `recordings_data`，宿主机数据持久化）；
- FastAPI 暴露 `/api/recordings/raw?key=...&exp=...&token=...`，HMAC 签名鉴权；
- ASR 通过签名 URL 拉录音，**不需要任何对象存储**；
- 在线试听：Web 后台 / App 调 `GET /api/recordings/{call_id}` 拿到一个新鲜的签名 URL，直接 `<audio src="...">` 即可。

`local` 模式的注意事项：
- 服务器磁盘要够；按 m4a 单声道 16k 估算 1 通 5 分钟约 ~600KB，1 万通 ≈ 6 GB；
- `LOCAL_STORAGE_PUBLIC_BASE` 必须 ASR 能访问到（公网 IP / 域名 / ngrok）；
- 生产环境别忘了改 `RECORDING_SIGN_SECRET`（`openssl rand -hex 32`）。

### 切换到阿里云 OSS（生产推荐）
1. 控制台开 OSS Bucket，**ACL 私有**，区域选 `cn-hangzhou`（与 DashScope 同区）；
2. RAM 子账号生成 AK/SK，只给该 Bucket 的 `oss:PutObject` / `oss:GetObject`；
3. `.env`：
   ```
   STORAGE_BACKEND=oss
   OSS_ACCESS_KEY_ID=...
   OSS_ACCESS_KEY_SECRET=...
   OSS_ENDPOINT=oss-cn-hangzhou-internal.aliyuncs.com
   OSS_BUCKET=autoluyin-recordings
   ```
4. `docker compose up -d` 重启 backend，无需任何业务代码改动。

## 1. 启动云端

```bash
cd poc
cp .env.example .env
# 编辑 .env，填入：
#   DASHSCOPE_API_KEY  → https://dashscope.console.aliyun.com/
#   DEEPSEEK_API_KEY   → https://platform.deepseek.com/
#   MINIO_PUBLIC_HOST  → 让阿里 ASR 能拉到的可达地址
#                        本机调试常用：ngrok http 9000，然后填 ngrok 给的域名

# 默认（STORAGE_BACKEND=local，文件存服务器磁盘）：
docker compose up -d --build

# 想用 MinIO：
docker compose --profile minio up -d --build

# 想用阿里云 OSS：改 .env 里 STORAGE_BACKEND=oss，再 up -d 即可

docker compose logs -f backend       # 看启动日志
```

启动后：

| 服务 | 地址 |
|------|------|
| 后端 API | http://localhost:18000  （Swagger: /docs；端口可在 .env 改 BACKEND_HOST_PORT）|
| 录音在线试听 | GET /api/recordings/{call_id} → 返回签名 URL，前端 `<audio>` 直接放 |
| MinIO 控制台（仅 minio profile）| http://localhost:19001  （minioadmin / minioadmin_dev） |
| PostgreSQL | localhost:25432  （autoluyin / autoluyin_dev） |

> 默认避开了 8000 / 5432 / 9000 / 9001 这些常见占用端口；如果你机器上 18000 / 25432 / 19000 / 19001 也冲突，改 `.env` 里 `*_HOST_PORT` 即可，容器内端口不变。

> **MINIO_PUBLIC_HOST 的重要性**：DashScope 的 Paraformer 文件转写要主动 GET 录音 URL。`localhost:9000` 在 ASR 服务器侧不可达。本机联调请用 ngrok / frp 或在公网 OSS 试。

种子数据已在 `init.sql` 写入：
- 1 台演示设备 `device_id = demo-mi-001`，绑定坐席 `13900139001`；
- 3 条任务（2 条催收 + 1 条投票）。

## 2. 运行 Android Demo

### 2.1 准备
1. **样机要求**：小米 / Redmi，HyperOS 或 MIUI 14+，**系统设置 → 电话 → 通话录音 → 自动录音 = 全部通话**。
2. Android Studio Hedgehog+ 打开 `poc/android/`，直接 Run 到机器。后端地址不再写死，APK 是通用包。

### 2.2 装机后第一次操作
1. 打开 App → 自动请求权限（拨号、电话状态、读音频）；
2. **首次启动弹出后端地址输入框**：
   - 调试期：填 `http://<服务器内网或公网IP>:18000`
   - 生产期：填 `https://api.your-domain.com`
   - 后续要改：点顶栏「服务器」按钮即可，**无需重装**；
3. 点 **「授权文件」**：跳转到系统设置开启「允许查看所有文件」（MIUI 必须，否则读不到 `/storage/emulated/0/MIUI/sound_recorder/call_rec/`）；
4. 点 **「自检」**：顶部状态栏会显示已命中的录音目录，自检完成后会自动从后端拉取运行时配置（候选目录、超时阈值等）；
5. 点 **「刷新任务」**：拉到 3 条种子任务。

### 2.3 后台调整运行时配置（不重打 APK）
直接修改数据库即可，下一次自检时所有 App 自动刷新：
```sql
-- 例：把扫描超时从 30s 调到 45s
UPDATE app_config SET value='45'::jsonb, updated_at=NOW()
WHERE scope='global' AND key='scan_timeout_sec';

-- 例：给某台设备单独追加候选目录
INSERT INTO app_config(scope, key, value) VALUES
  ('demo-mi-001', 'candidate_dirs',
   '["MIUI/sound_recorder/call_rec","NewVendor/CallRec"]'::jsonb)
ON CONFLICT (scope, key) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW();
```

### 2.3 联调一次完整通话
1. 把任务里的 `phone` 字段改成你自己愿意打的号码（直接改 `init.sql` 重启 postgres，或用 Swagger 改一下 `task` 表）；
2. 在 App 里点「呼叫」→ 系统拨号盘弹出 → 接通 → 说几句 → 挂机；
3. 通知栏会依次出现："通话中" → "挂机，匹配录音…" → "上传完成 #N"；
4. 弹窗让你选投票/催收结果；
5. 后端 `docker compose logs -f backend` 里能看到 ASR 任务提交、LLM 抽取完成；
6. 用 `curl http://localhost:8000/api/calls/N` 看完整结果（含 `full_text`、`extraction_fields`）。

## 3. 端到端时序

```
坐席点呼叫
  ├─ App: CallWatcherService.start(taskId, phone)
  └─ App: ACTION_CALL → 系统拨号盘
                              ↓ OFFHOOK
        TelephonyCallback ── 记录 startedAt
                              ↓ IDLE
        TelephonyCallback ── 记录 endedAt
                              ↓
        RecordingScanner 30s 轮询匹配
                              ↓
        OkHttp 上传 → /api/calls/upload
                              ↓
        FastAPI: MinIO put_object + DB insert
                              ↓
        BackgroundTasks → workers.pipeline.process_call
                              ├─ DashScope Paraformer 异步转写 + 轮询
                              ├─ 写 transcript
                              ├─ DeepSeek chat extraction
                              └─ 写 extraction
                              ↓
        坐席填表单 → /api/calls/{id}/business
                              ↓
        写 vote_record / collection_promise + task=done
```

## 4. PoC 验收门槛（Sprint 0 出口）

- [ ] 在小米实机上 ≥ 95% 概率挂机后 30 秒内匹配到正确录音文件并上传；
- [ ] 上传后 90 秒内拿到 ASR 文字稿；
- [ ] 投票/催收两类 prompt 在 5 个真实样例上结构化抽取字段全部到位；
- [ ] 录音匹配失败时有降级提示，不中断坐席工作流；
- [ ] 自检不通过时呼叫按钮禁用。

## 5. 已知限制 / 待办

- 仅适配小米录音目录第一梯队，华为/OPPO/vivo 真机到位后扩 `RecordingScanner.candidateDirs`；
- 上传暂未做断点续传与压缩；弱网场景需 WorkManager + 持久化队列；
- 录音文件目前没做端到端加密，正式版应在端侧用 KMS 加密 + 传输 TLS；
- 自检暂未读取系统"通话录音"开关具体值——MIUI 没有公开 API，目前用"录音目录是否非空"近似判断；
- 业务表单还没接微信支付链接生成；催收 H5 / 短信通道留空。

## 6. 接下来的扩展点

- **机型适配回归**：建一个 `tests/recording_match/` 目录，存各机型录音文件样本，跑离线匹配测试；
- **n8n 流水线**：把 `workers/pipeline.py` 拆成 n8n 节点（上传 → ASR webhook → LLM → DB），便于产品/运营调参；
- **管理后台**：用 Refine + shadcn 写 Web 端，复用 FastAPI 接口。
