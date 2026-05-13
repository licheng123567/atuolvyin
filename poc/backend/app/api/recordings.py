"""录音访问接口：

  GET /api/recordings/{call_id}              在线试听（带 Range，便于网页 audio 拖动）；
                                              内部走签名 URL，调用方可直接给 <audio> 用。
  GET /api/recordings/raw?key=...&exp=...&token=...
                                              真实文件流；ASR 和 Web 试听都走这里。
                                              token 为 HMAC，无需登录鉴权。

非 local 后端（MinIO/OSS）由各自服务直接提供 URL，本路由仅 local 模式生效。
"""

import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.signing import verify_token
from app.core.storage import LocalFileStorage, storage

router = APIRouter()


@router.get("/{call_id}")
def listen(call_id: int, db: Session = Depends(get_db)):
    """业务接口：根据 call_log_id 拿到一个对外可访问的录音 URL。
    Web 后台和 App 都用这个接口，<audio src="..."> 即可在线播放。
    """
    row = db.execute(
        text("""
        SELECT object_key, public_url FROM recording_file
        WHERE call_log_id = :c
        ORDER BY id DESC LIMIT 1
    """),
        {"c": call_id},
    ).fetchone()
    if not row:
        raise HTTPException(404, "recording not found")
    object_key, stored_url = row[0], row[1]

    # 重新签发短期 URL（local 模式下 stored_url 写库时已带 token，但已过期可能性大；
    # MinIO/OSS 模式下 stored_url 是一次性的，统一重签更稳）
    fresh_url = storage.get_url(object_key)
    return {"url": fresh_url, "stored_url": stored_url}


@router.get("/raw")
def serve_raw(
    request: Request,
    key: str = Query(...),
    exp: int = Query(...),
    token: str = Query(...),
):
    """本地存储模式下的实际文件流；带 HMAC 校验和 Range 支持，给 <audio> 拖动用。"""
    if not isinstance(storage, LocalFileStorage):
        # 非 local 模式，直接重定向到对象存储 URL
        return RedirectResponse(storage.get_url(key))

    if not verify_token(key, token, exp):
        raise HTTPException(403, "invalid or expired token")

    path = storage.local_path(key)
    if not os.path.isfile(path):
        raise HTTPException(404, "file missing")

    # FileResponse 已自动支持 Range 头，<audio> 拖动可用
    return FileResponse(
        path,
        media_type=_guess_mime(path),
        headers={"Accept-Ranges": "bytes"},
    )


def _guess_mime(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower()
    return {
        "m4a": "audio/mp4",
        "aac": "audio/mp4",
        "mp3": "audio/mpeg",
        "amr": "audio/amr",
        "wav": "audio/wav",
        "3gp": "audio/3gpp",
        "ogg": "audio/ogg",
    }.get(ext, "application/octet-stream")
