"""ASR mock：返回预设文字稿，零依赖跑通主链路。

不需要任何 API key、不需要公网 URL、不需要 GPU。
"""

_TRANSCRIPT_COLLECTION = (
    "[坐席] 喂您好，请问是张先生吗？我是阳光花园物业的小赵，本次通话将被录音用于服务质量。\n"
    "[业主] 嗯你说。\n"
    "[坐席] 张先生您好，我们核对下您去年第四季度到今年三月份的物业费，一共 3600 元还没缴。\n"
    "[业主] 我知道我知道，最近手头紧，月底发了工资就交。\n"
    "[坐席] 好的张先生，那我登记您 4 月 30 号之前缴清，到时候我会再跟您确认一下。\n"
    "[业主] 行行行，挂了。"
)

_TRANSCRIPT_VOTE = (
    "[坐席] 喂您好，请问是李先生吗？我是阳光花园物业的小赵，本次通话将被录音用于服务质量。\n"
    "[业主] 你说。\n"
    "[坐席] 我们小区电梯改造方案投票，您是同意还是反对？\n"
    "[业主] 当然同意了，旧电梯天天卡。\n"
    "[坐席] 好的，给您登记同意，谢谢配合。"
)


def transcribe(audio_url: str, hint_task_type: str | None = None) -> dict:
    is_vote = hint_task_type == "vote"
    text = _TRANSCRIPT_VOTE if is_vote else _TRANSCRIPT_COLLECTION
    segments = []
    for i, line in enumerate(text.split("\n")):
        if not line.strip():
            continue
        speaker = 0 if line.startswith("[坐席]") else 1
        clean = line.split("] ", 1)[-1] if "] " in line else line
        segments.append(
            {
                "speaker": speaker,
                "start_ms": i * 4000,
                "end_ms": i * 4000 + 3500,
                "text": clean,
            }
        )
    return {
        "full_text": text,
        "segments": segments,
        "model": "mock",
        "raw": {"note": "ASR_BACKEND=mock 假数据；切到 dashscope 接真 ASR"},
    }
