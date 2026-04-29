"""
批量录音分析脚本（并行版）
用法：python3 batch_analyze.py
输出：batch_results.xlsx
"""
import os, re, time, subprocess, json, logging, threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

# ── 配置 ──────────────────────────────────────────────
DASHSCOPE_KEY = "sk-3dd8821bf3014436b20e50147123b3a8"
TASK_TYPE     = "vote"   # vote / collection
WORKERS       = 5        # 并发数

AUDIO_DIRS = [
    "/tmp/recordings1",
    "/tmp/recordings2/录音2",
    "/tmp/recordings3/录音3",
]

dashscope.api_key = DASHSCOPE_KEY

_llm_lock = threading.Lock()

def make_llm():
    return OpenAI(
        api_key=DASHSCOPE_KEY,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

# ── 提示词 ──────────────────────────────────────────────
VOTE_SYSTEM = """你是物业投票通话分析助手。根据通话文字稿，抽取业主的投票意向。
严格输出 JSON，字段：
{
  "choice": "同意" | "反对" | "弃权" | "未明确" | "无效通话",
  "reason": "关键依据（≤50字）",
  "confidence": 0~1,
  "needs_review": true/false
}
无效通话：无人接听/对方是空号/明显噪音无语音内容。不要输出 JSON 以外的内容。"""

COLLECTION_SYSTEM = """你是物业费催收通话分析助手。根据通话文字稿，抽取催收结果。
严格输出 JSON，字段：
{
  "intent": "立即缴" | "承诺缴" | "推托" | "拒缴" | "失联" | "无效通话",
  "promise_date": "YYYY-MM-DD 或 null",
  "excuse_category": "房屋质量" | "服务不满" | "经济困难" | "其他" | null,
  "confidence": 0~1,
  "needs_review": true/false
}
无效通话：无人接听/空号/噪音。不要输出 JSON 以外的内容。"""

# ── 文件名解析 ──────────────────────────────────────────────
def parse_filename(name: str) -> tuple[str, str]:
    digits = re.sub(r"[^\d]", "", name)
    m = re.search(r"1[3-9]\d{9}", digits)
    phone = m.group() if m else digits[:11] if len(digits) >= 11 else digits
    dm = re.search(r"(2026\d{4})", digits)
    date_str = dm.group()[:8] if dm else ""
    if date_str:
        try:
            date_str = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
        except:
            pass
    return phone, date_str

# ── ASR ──────────────────────────────────────────────
def asr(file_path: str) -> str:
    try:
        pcm = subprocess.check_output(
            ["ffmpeg", "-i", file_path, "-ar", "16000", "-ac", "1", "-f", "s16le", "-"],
            stderr=subprocess.DEVNULL, timeout=60,
        )
    except Exception as e:
        return f"[ffmpeg错误: {e}]"

    sentences, done, err = [], [False], [None]

    class CB(RecognitionCallback):
        def on_close(self): done[0] = True
        def on_complete(self): done[0] = True
        def on_error(self, r): err[0] = r; done[0] = True
        def on_event(self, r: RecognitionResult):
            s = r.get_sentence()
            if s and RecognitionResult.is_sentence_end(s):
                t = s.get("text", "").strip()
                if t: sentences.append(t)
        def on_open(self): pass

    rec = Recognition(model="paraformer-realtime-v2", format="pcm",
                      sample_rate=16000, callback=CB())
    rec.start()
    for i in range(0, len(pcm), 3200):
        rec.send_audio_frame(pcm[i:i+3200])
        time.sleep(0.005)
    rec.stop()

    deadline = time.time() + 15
    while not done[0] and time.time() < deadline:
        time.sleep(0.2)

    return " ".join(sentences) if sentences else "[无语音内容]"

# ── LLM ──────────────────────────────────────────────
def llm_extract(transcript: str, task_type: str) -> dict:
    system = VOTE_SYSTEM if task_type == "vote" else COLLECTION_SYSTEM
    llm = make_llm()
    try:
        resp = llm.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"通话内容：\n{transcript}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        return json.loads(resp.choices[0].message.content or "{}")
    except Exception as e:
        return {"error": str(e)}

# ── 单文件处理 ──────────────────────────────────────────────
def process_file(args):
    i, total, fp = args
    phone, date = parse_filename(fp.name)
    logger.info("[%d/%d] %s", i, total, fp.name)
    text = asr(str(fp))
    result = llm_extract(text, TASK_TYPE)
    return {
        "序号": i,
        "文件名": fp.name,
        "手机号": phone,
        "日期": date,
        "转写文本": text,
        "意图/结果": result.get("choice") or result.get("intent", ""),
        "关键依据": result.get("reason", ""),
        "承诺日期": result.get("promise_date", ""),
        "置信度": result.get("confidence", ""),
        "需复核": result.get("needs_review", ""),
        "原始JSON": json.dumps(result, ensure_ascii=False),
    }

# ── 主流程 ──────────────────────────────────────────────
def collect_files():
    files = []
    for d in AUDIO_DIRS:
        for f in Path(d).iterdir():
            if f.suffix.lower() in {".mp3", ".m4a", ".amr", ".wav", ".aac"}:
                files.append(f)
    return sorted(files)

_save_lock = threading.Lock()

def _save(rows):
    try:
        import openpyxl
    except ImportError:
        subprocess.check_call(["pip3", "install", "openpyxl", "-q"])
        import openpyxl

    sorted_rows = sorted(rows, key=lambda r: r["序号"])
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "分析结果"
    headers = ["序号","文件名","手机号","日期","转写文本","意图/结果","关键依据","承诺日期","置信度","需复核","原始JSON"]
    ws.append(headers)
    for r in sorted_rows:
        ws.append([r.get(h,"") for h in headers])
    ws.column_dimensions["E"].width = 60
    ws.column_dimensions["G"].width = 40
    wb.save("/Users/shuo/AI/autoluyin/batch_results.xlsx")

def main():
    files = collect_files()
    total = len(files)
    logger.info("共找到 %d 个录音文件，并发数 %d", total, WORKERS)

    rows = []
    completed = 0
    args_list = [(i+1, total, fp) for i, fp in enumerate(files)]

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(process_file, a): a for a in args_list}
        for fut in as_completed(futures):
            try:
                row = fut.result()
                rows.append(row)
            except Exception as e:
                a = futures[fut]
                logger.error("处理失败 %s: %s", a[2].name, e)
            completed += 1
            if completed % 50 == 0:
                with _save_lock:
                    _save(rows)
                logger.info("已完成 %d/%d，保存中...", completed, total)

    _save(rows)
    logger.info("全部完成，共 %d 条，结果保存到 batch_results.xlsx", len(rows))

if __name__ == "__main__":
    main()
