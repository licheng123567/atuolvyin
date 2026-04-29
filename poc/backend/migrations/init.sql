-- 自动外呼录音 PoC 数据库初始化
-- 执行点：Postgres 容器首次启动时挂到 /docker-entrypoint-initdb.d/

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 业主
CREATE TABLE owner (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    phone       TEXT NOT NULL UNIQUE,
    building    TEXT,
    room        TEXT,
    tags        JSONB DEFAULT '[]'::jsonb,
    history     JSONB DEFAULT '[]'::jsonb,        -- 历史联系摘要
    do_not_call BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 工作机
CREATE TABLE device (
    id              BIGSERIAL PRIMARY KEY,
    device_id       TEXT NOT NULL UNIQUE,         -- App 端生成的设备指纹
    brand           TEXT,                          -- xiaomi / huawei / oppo / vivo
    model           TEXT,
    os_version      TEXT,
    agent_name      TEXT,                          -- 绑定的坐席
    agent_phone     TEXT,                          -- 工作机本机号
    recording_dir   TEXT,                          -- 适配命中后回写
    last_self_check TIMESTAMPTZ,
    self_check_ok   BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 外呼任务
CREATE TABLE task (
    id           BIGSERIAL PRIMARY KEY,
    owner_id     BIGINT REFERENCES owner(id),
    type         TEXT NOT NULL CHECK (type IN ('vote', 'collection')),
    payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- vote.payload:        {motion_id, motion_title, options:[{id,label}]}
    -- collection.payload:  {amount, months, due_date}
    priority     INT DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','in_progress','done','failed','dropped')),
    assigned_to  BIGINT REFERENCES device(id),
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_task_assigned_status ON task(assigned_to, status);

-- 通话日志
CREATE TABLE call_log (
    id                       BIGSERIAL PRIMARY KEY,
    task_id                  BIGINT REFERENCES task(id),
    device_id                BIGINT REFERENCES device(id),
    caller_phone             TEXT,                 -- 坐席工作机号
    callee_phone             TEXT,                 -- 业主号
    started_at               TIMESTAMPTZ,
    ended_at                 TIMESTAMPTZ,
    duration_sec             INT,
    status                   TEXT NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending','uploaded','transcribed','extracted','no_recording','failed')),
    recording_match_status   TEXT,                 -- matched / not_found / manual
    created_at               TIMESTAMPTZ DEFAULT NOW()
);

-- 录音文件
CREATE TABLE recording_file (
    id            BIGSERIAL PRIMARY KEY,
    call_log_id   BIGINT REFERENCES call_log(id) ON DELETE CASCADE,
    object_key    TEXT NOT NULL,                   -- MinIO 对象 key
    public_url    TEXT,                            -- ASR 拉取用
    src_path      TEXT,                            -- 端侧原路径
    size_bytes    BIGINT,
    duration_sec  INT,
    format        TEXT,
    match_method  TEXT,                            -- name_match / mediastore / manual
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 文字稿
CREATE TABLE transcript (
    id           BIGSERIAL PRIMARY KEY,
    call_log_id  BIGINT REFERENCES call_log(id) ON DELETE CASCADE,
    full_text    TEXT,
    segments     JSONB,                            -- [{speaker, start_ms, end_ms, text}]
    asr_model    TEXT,
    asr_raw      JSONB,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- 结构化抽取结果
CREATE TABLE extraction (
    id           BIGSERIAL PRIMARY KEY,
    call_log_id  BIGINT REFERENCES call_log(id) ON DELETE CASCADE,
    type         TEXT NOT NULL,                    -- vote / collection
    fields       JSONB NOT NULL,
    confidence   NUMERIC(4,3),
    llm_model    TEXT,
    needs_review BOOLEAN DEFAULT FALSE,
    review_note  TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- 投票结果（最终）
CREATE TABLE vote_record (
    id               BIGSERIAL PRIMARY KEY,
    owner_id         BIGINT REFERENCES owner(id),
    motion_id        TEXT NOT NULL,
    choice           TEXT NOT NULL,                -- 同意 / 反对 / 弃权 / 未明确
    source           TEXT NOT NULL,                -- call / h5
    evidence_call_id BIGINT REFERENCES call_log(id),
    note             TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(owner_id, motion_id)
);

-- 催收承诺
CREATE TABLE collection_promise (
    id               BIGSERIAL PRIMARY KEY,
    owner_id         BIGINT REFERENCES owner(id),
    amount           NUMERIC(10,2),
    promise_date     DATE,
    status           TEXT NOT NULL DEFAULT 'open'
                     CHECK (status IN ('open','paid','overdue','cancelled')),
    excuse_category  TEXT,
    evidence_call_id BIGINT REFERENCES call_log(id),
    note             TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- 应用运行时配置（全局 + 按设备覆盖）
CREATE TABLE app_config (
    scope       TEXT NOT NULL,                     -- 'global' 或 设备 device_id
    key         TEXT NOT NULL,
    value       JSONB NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (scope, key)
);

-- 默认全局配置（坐席 App 启动后会拉取）
INSERT INTO app_config(scope, key, value) VALUES
    ('global', 'scan_timeout_sec', '30'::jsonb),
    ('global', 'upload_max_size_mb', '50'::jsonb),
    ('global', 'self_check_interval_min', '60'::jsonb),
    ('global', 'prompt_version', '"v1"'::jsonb),
    ('global', 'candidate_dirs', '[
        "MIUI/sound_recorder/call_rec",
        "MIUI/sound_recorder/call_recordings",
        "Recordings/call",
        "Recordings/Call",
        "Recordings/CallRecordings",
        "Sounds/CallRecord",
        "record/Call",
        "Recordings/Call Recordings",
        "记录/通话录音",
        "Music/Recordings/Call Recordings",
        "Recorder/call"
    ]'::jsonb);

-- 质检告警
CREATE TABLE qc_alert (
    id           BIGSERIAL PRIMARY KEY,
    call_log_id  BIGINT REFERENCES call_log(id),
    rule         TEXT NOT NULL,
    severity     TEXT NOT NULL,                    -- info / warn / critical
    detail       TEXT,
    handled      BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ===== 种子数据（联调用）=====
INSERT INTO owner(name, phone, building, room, history) VALUES
    ('张三', '13800138001', 'A栋', '101', '[]'::jsonb),
    ('李四', '13800138002', 'A栋', '202', '[{"date":"2026-03-15","summary":"上次承诺月底交"}]'::jsonb),
    ('王五', '13800138003', 'B栋', '303', '[]'::jsonb);

INSERT INTO device(device_id, brand, model, agent_name, agent_phone) VALUES
    ('demo-mi-001', 'xiaomi', 'Redmi K70', '坐席小赵', '13900139001');

INSERT INTO task(owner_id, type, payload, priority, assigned_to) VALUES
    (1, 'collection',
     '{"amount": 3600, "months": "2025-10~2026-03", "due_date": "2026-03-31"}'::jsonb,
     10, 1),
    (2, 'collection',
     '{"amount": 1800, "months": "2026-01~2026-03", "due_date": "2026-03-31"}'::jsonb,
     20, 1),
    (3, 'vote',
     '{"motion_id":"M-2026-001","motion_title":"电梯改造方案","options":[{"id":"yes","label":"同意"},{"id":"no","label":"反对"},{"id":"abstain","label":"弃权"}]}'::jsonb,
     5, 1);
