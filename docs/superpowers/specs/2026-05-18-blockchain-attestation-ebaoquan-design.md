# 区块链存证接入（易保全证据保全）设计文档

> 状态：设计已与用户确认（2026-05-18），待用户复审后转实施计划。

## 背景与目标

区块链存证当前是纯 mock：`app/services/blockchain.py` 的 `submit_attestation()` 用本地 SHA-256 算法生成确定性假 `tx_hash` + 自增 `block_height`，从不真实上链。`BlockchainConfig` 平台配置表 + `/super/blockchain-config` 超管页虽已存在，但 `provider` 枚举是 `antchain/fisco-bcos/mock`，从未对接真实服务。唯一存证触发点是 `app/services/evidence_bundle.py`：生成案件法务存证包时给通话录音的 hash 上链。

**目标**：接入第三方「易保全证据保全」(ebaoquan.org) API，让案件法务存证包里的关键数据真实上链；并把上链数据范围从「仅录音」扩展为「录音 + 转写 + AI 分析」。易保全账号凭证由超级管理员在后台配置。

## 范围

**纳入**：
- 把 `submit_attestation()` 的 mock 上链替换为真实易保全 `createEvidenceHash` 调用（配置驱动，mock 仍是默认 / dev / 测试分支）。
- 上链数据范围扩展：生成案件存证包时，对每通电话的**录音 + 转写 + AI 分析**各做一次存证（现仅录音）。
- 易保全 `createEvidenceHash` 成功后同步 best-effort 补查保全备案号（`queryEvidenceDetail`）。
- 超级管理员配置易保全：`appKey` + `appKeySecret` + 服务地址（沙箱/生产）+ 启用开关。

**不在范围**：
- 上链时机不变 —— 仍在「生成案件法务存证包」时触发，不做数据产生即时上链（不接 call-end / ASR-complete 事件钩子）。
- 易保全《保全证书》PDF 下载（`downPreservationCert`）—— 不接。
- 易保全文件保全（`createEvidenceFile`，上传整个文件）—— 不接，只用 HASH 保全。
- 公开核验端点 `GET /api/v1/public/verify/{tx_hash}` —— 不改（继续服务 mock 存证；易保全存证由易保全平台凭保全备案号核验）。
- 删除证据 / 数据存证（`/api/data/*`）等其余易保全端点。
- antchain / fisco-bcos —— 历史 `provider` 枚举值保留但不实现，等同 mock。

## 第三方 API（易保全证据保全 ebaoquan.org）

- 文档：证据保全 API 接入文档 v2.0.5。
- 服务地址（`$SERVICE_URL`）：沙箱 `https://bs.sandbox.ebaoquan.org`、生产 `https://bs.ebaoquan.org`。
- 鉴权：`appKey`（公钥标识）+ `sign`（签名）。
- 签名算法（§4.1）：所有参数（排除 `sign`、排除文件参数）按参数名 ASCII 升序，以 `key1=value1&key2=value2` 拼成 `stringA`；`stringSignTemp = stringA + appKeySecret`；`sign = MD5(stringSignTemp)` 全大写。签名参数不做 UrlEncode。
- HASH 保全 `POST $SERVICE_URL/api/createEvidenceHash`（form-urlencoded）：
  - 入参：`appKey`、`sign`、`fileHash`（string(128)，文件 SHA-512 hex）、`name`（string(50)，证据名称）、`description`（string(50)，可选，证据备注）、`type`（证据类型：`1`图片/`2`文档/`3`音频/`4`视频/`99`其他）。
  - 响应：`{"success":bool,"message":str,"code":int,"data":{"evidenceId":long}}`，`code==0` 为成功。
- 证据详情 `POST $SERVICE_URL/api/queryEvidenceDetail`（form-urlencoded）：
  - 入参：`appKey`、`sign`、`evidenceId`。
  - 响应 `data`：`{evidenceId, fileHash, name, description, createTime, type, preservationId}`。`preservationId` 即保全备案号。
- 保全 hash 算法（§5）：文件二进制 → SHA-512 → 16 进制小写 hex（128 字符）。
- 错误编码（§6）：`6000001` appKey 不正确、`6000002` sign 不正确、`6001001/6001002` 账户未认证、`6201001~6201004` createEvidenceHash 参数错误、`6202001` 查询参数错误、`6002002` 系统错误 等。

## 架构

照搬代码库既有范式：
- 「配置驱动外部服务分发」—— `blockchain.py` 现有 `_resolve_provider(db)` 读 active `BlockchainConfig`。
- 「客户端模块」—— 短信通道 `app/services/sms_center.py`（独立 HTTP seam、永不抛异常、返回结果对象、`httpx.MockTransport` 可测）。
- 「超管配置外部服务」—— `BlockchainConfig` 单行平台配置 + `/super/blockchain-config` 超管 GET/PUT + 前端 `pages/super/blockchain-config/`。

### ① 数据模型

**`BlockchainConfig`（`app/models/platform.py`，扩展）** 新增一列：

| 列 | 类型 | 说明 |
|----|------|------|
| `app_key` | `String(128)`, nullable | 易保全公钥标识（`appKey`），非密钥，明文存 |

`appKeySecret` 复用既有 `api_key_enc`（AES 密文，与现状同）。`api_endpoint` 存易保全服务地址。`provider` 取值新增 `"ebaoquan"`。

**`BlockchainAttestation`（`app/models/blockchain_attestation.py`，扩展）**：

| 列 | 变更 |
|----|------|
| `tx_hash` | `String(64)` 改 nullable（易保全分支留 NULL；mock 仍填、仍 unique）|
| `block_height` | `BigInteger` 改 nullable（易保全分支留 NULL）|
| `data_sha512` | 新增 `String(128)`, nullable —— 送易保全的 SHA-512 hex |
| `provider_evidence_id` | 新增 `BigInteger`, nullable —— 易保全 `evidenceId` |
| `preservation_id` | 新增 `BigInteger`, nullable —— 易保全保全备案号 |

`status` 现有 check 约束 `confirmed/failed/pending` 不变。`data_type` 现有 check `call_recording/transcript/analysis/evidence_bundle` 不变（转写/分析已在枚举内）。

Alembic 迁移：单个 revision 同时改 `blockchain_config` 与 `blockchain_attestation` 两表，接当前 head。`tx_hash`/`block_height` 由 NOT NULL → NULL 是安全变更（无需回填）；新列均 nullable 无需回填。

### ② 易保全客户端 `app/services/ebaoquan.py`（新建）

纯 HTTP seam，不碰 DB，永不抛异常。

```python
@dataclass
class EbaoquanHashResult:
    ok: bool
    evidence_id: int | None
    error: str | None

@dataclass
class EbaoquanDetailResult:
    ok: bool
    preservation_id: int | None
    error: str | None
```

公开函数：
- `sign_params(params: dict[str, str], app_key_secret: str) -> str` —— §4.1 签名算法：排除 `sign`，按 key ASCII 升序拼 `k=v&k=v`，尾接 `app_key_secret`，`MD5` 全大写。纯函数。
- `create_evidence_hash(*, base_url, app_key, app_key_secret, file_hash, name, description, evidence_type, timeout=10.0) -> EbaoquanHashResult` —— 构造参数 + 签名 → `httpx.Client`（同步带超时）POST `{base_url}/api/createEvidenceHash`（`data=` form-urlencoded）→ 解析 `code==0` → `evidence_id`；否则 `ok=False, error=易保全 message 或 code`。httpx 异常 → `ok=False, error="ERR_EBAOQUAN_HTTP"`。
- `query_evidence_detail(*, base_url, app_key, app_key_secret, evidence_id, timeout=10.0) -> EbaoquanDetailResult` —— POST `{base_url}/api/queryEvidenceDetail` → 解析 `data.preservationId`。

`name`/`description` 截断到 50 字由调用方（`blockchain.py`）负责，客户端不截断。

### ③ 存证编排 `app/services/blockchain.py`（重构）

`_resolve_provider(db)` 改为 `_resolve_config(db) -> BlockchainConfig | None`（返回整行，调用方需要 `app_key`/密钥）。

`submit_attestation` 签名改为接收原始字节（当前唯一调用方为 `evidence_bundle.py`）：

```python
def submit_attestation(
    db, *,
    tenant_id: int,
    data: bytes,
    data_type: str,                  # call_recording / transcript / analysis / evidence_bundle
    title: str,                      # 易保全证据名称（调用方传，内部截断 50 字）
    description: str | None = None,  # 易保全证据备注（内部截断 50 字）
    payload_metadata: dict | None = None,
    call_id: int | None = None,
    legal_case_id: int | None = None,
) -> BlockchainAttestation
```

内部：算 `sha256 = sha256(data)`、`sha512 = sha512(data)`。分发：
- **mock 分支**（无 active 配置 / `provider != "ebaoquan"` / `provider="ebaoquan"` 但 `is_active=False`）：现行为不变 —— `chain_provider` 取配置 `provider` 或 `"mock"`，`tx_hash=_gen_tx_hash(...)`、`block_height=_next_block_height(db)`、`data_sha512` 也落库、`status="confirmed"`。
- **易保全分支**（`provider="ebaoquan"` + `is_active=True`）：
  - 缺 `app_key` 或 `api_key_enc` → 不发 HTTP，`status="failed"`、失败原因记 `"ERR_BLOCKCHAIN_NOT_CONFIGURED"`、写回 `BlockchainConfig.last_failure_at/reason`。
  - 否则 `evidence_type = _EBAOQUAN_TYPE[data_type]`（`call_recording→3`、`transcript→2`、`analysis→2`、`evidence_bundle→99`），调 `ebaoquan.create_evidence_hash(file_hash=sha512, name=title[:50], description=(description or "")[:50], ...)`。
    - `ok=True`：`provider_evidence_id=evidence_id`、`status="confirmed"`；再 best-effort 调 `query_evidence_detail` → 成功则 `preservation_id` 写入，失败则留 NULL（不降级）。`tx_hash`/`block_height` 留 NULL。
    - `ok=False`：`status="failed"`、失败信息记入 attestation 的 `payload_metadata`，写回 `BlockchainConfig.last_failure_at/reason`。

`submit_attestation` 永不因 provider 失败抛异常；内部断言错误（如空 `data`）仍可抛。失败时也落一条 `status="failed"` 的 `BlockchainAttestation`（记录上链尝试）。`db.flush()`，调用方负责 commit。

### ④ 存证包接线 `app/services/evidence_bundle.py`（改造）

现状：每通电话只在有 `recording_sha` 时调一次 `submit_attestation`。改造：
- 录音、转写、分析**三类各调一次** `submit_attestation`（仅当该类数据存在）：
  - 录音：`data=audio`、`data_type="call_recording"`、`title=f"案件{case.id}通话{call.id}录音"`。
  - 转写：`data=transcript.full_text.encode("utf-8")`、`data_type="transcript"`、`title=f"案件{case.id}通话{call.id}转写"`。
  - 分析：`data=analysis_payload 的 JSON bytes`、`data_type="analysis"`、`title=f"案件{case.id}通话{call.id}AI分析"`。
- `_attestation_to_blockchain_meta(att)` 改为兼容易保全字段：输出 `provider/status/data_type/transaction_id(tx_hash 或 None)/block_height/evidence_id/preservation_id/submitted_at/verify_url`。`verify_url` 仅 mock（有 `tx_hash`）时给 `/verify/{tx_hash}`，易保全时为 `None`。
- `attestation.json` 的 `blockchain` 字段从单对象 → **列表**（每元素一个 data_type 的 meta）。
- 单条上链失败（`status="failed"`）不抛错、不阻断 ZIP 生成，meta 里 `status="failed"` 体现。
- **存证字节必须与写入 ZIP 的字节完全一致** —— 传给 `submit_attestation` 的 `data` 即写入 `recording.{ext}` / `transcript.txt` / `analysis.json` 的同一份 bytes，保证 `data_sha256` 与 ZIP 内文件 hash 一致、可被独立核验。

### ⑤ 超管 API + Schema

`app/schemas/platform.py`：
- `BlockchainConfigIn`：`provider` Literal 加 `"ebaoquan"`；新增 `app_key: str | None = Field(None, max_length=128)`。
- `BlockchainConfigOut`：新增 `app_key: str | None`（公钥可回显）。`appKeySecret` 仍只回 `has_api_key`。

`app/api/super_config.py`：`_config_to_out` 带上 `app_key`；`put_blockchain_config` upsert 时写 `app_key`（与 `api_endpoint` 同款，直接覆盖）。守卫 `require_roles(*SUPER_ROLES)` 不变。

### ⑥ 前端

`frontend/src/pages/super/blockchain-config/index.tsx`（已存在，小改）：
- `provider` 下拉加「易保全」选项。
- 新增 `app_key` 文本输入框（appKey 公钥）。
- 既有 `api_key` 框语义为 `appKeySecret`，label/占位调整（占位提示「已配置则留空不改」）。
- endpoint 输入加提示：沙箱 `https://bs.sandbox.ebaoquan.org` / 生产 `https://bs.ebaoquan.org`。
- 保存仍调 `PUT /super/blockchain-config`。

## 错误处理

- `submit_attestation` 对 provider 失败永不抛异常 —— 落 `status="failed"` 记录、写 `BlockchainConfig.last_failure_*`，由 `evidence_bundle` 照常生成 ZIP。
- 不新增 HTTP 错误码（存证包端点仍 200）。
- `ebaoquan.py` 客户端 httpx 异常 / 非 0 `code` 统一转 `EbaoquanXxxResult(ok=False, error=...)`，不抛。
- 内部失败原因字符串：`ERR_BLOCKCHAIN_NOT_CONFIGURED`（缺凭证）、`ERR_EBAOQUAN_HTTP`（网络异常）、易保全 `message`/`code`（业务失败）。

## 测试

- 模型 + 迁移：`blockchain_config.app_key`、`blockchain_attestation` 新列建表；`tx_hash`/`block_height` 可空。
- `sign_params`：文档 §4.1 示例向量 —— `appKey=a7ce728fbec40519` + `param1/2/3=paramValue1/2/3` + secret `d5207ae9f7bee0692a1e4014f90e1af0` → `2523044EB55944A10324AAAA3DCCEB75`。
- SHA-512：文档 §5 向量 —— `"1234567890"` → `12b03226a6d8be9c6e8cd5e55dc6c7920caaa39df14aab92d5e3ea9340d1c8a4d3d0b8e4314f1f6ef131ba4bf1ceb9186ab87c801af0d5c95b1befb8cedae2b9`。
- `ebaoquan.create_evidence_hash` / `query_evidence_detail`：`httpx.MockTransport` 模拟 `code=0` 成功、`code≠0` 失败、httpx 异常；断言请求体含正确 `sign`。
- `submit_attestation`：
  - mock 分支 → `status="confirmed"`、有 `tx_hash`/`block_height`、不发 HTTP（现行为回归）。
  - 易保全分支成功 → `confirmed`、`provider_evidence_id` 写入、`preservation_id` 经补查写入、`tx_hash` 为 NULL。
  - 易保全分支补查失败 → 仍 `confirmed`、`preservation_id` 为 NULL。
  - 易保全分支 `createEvidenceHash` 失败 → `status="failed"`、`BlockchainConfig.last_failure_*` 写回。
  - `provider="ebaoquan"` 激活但缺凭证 → `failed` + `ERR_BLOCKCHAIN_NOT_CONFIGURED`。
- `evidence_bundle`：一通有录音+转写+分析的电话 → 生成 3 条 attestation；其中一条易保全失败 → ZIP 仍生成、`attestation.json` 的 `blockchain` 列表含 `failed` 项。
- 超管 API：`GET` 空/有配置；`PUT` upsert 写 `app_key`；`BlockchainConfigOut` 不泄漏 `appKeySecret`（只 `has_api_key`）；非超管 403。
- 前端：blockchain-config 页渲染 + 含 `app_key` 的表单提交（mirror 现有页测试）。
- 后端 testcontainers；外部 HTTP 全程 `httpx.MockTransport`（禁止打真实易保全）。

## 风险

- `preservationId` 可能由易保全异步生成 —— 若 `createEvidenceHash` 成功后立即 `queryEvidenceDetail` 拿不到备案号，`preservation_id` 留 NULL，不影响 `confirmed` 状态；法务需要时可凭 `evidenceId` 再查。
- `appKeySecret` 以 AES 密文存库（复用 `BlockchainConfig.api_key_enc`），`.env` 的 `autoluyin_aes_key` 是解密前提 —— 与既有约束一致。
- 易保全 `name`/`description` 限 50 字，调用方截断；中文按字符计。
- 录音文件可能较大 —— `submit_attestation` 收 `data: bytes`，`evidence_bundle` 本就已把录音读入内存（`storage.get_bytes`），无额外内存开销。
- 历史 mock 存证（`tx_hash` 非空）不受影响；公开核验端点继续服务 mock 存证。
