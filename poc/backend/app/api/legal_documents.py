"""Sprint 11.6 — Legal document upload / list / download / delete (PRD §L2136).

Endpoints:
  POST   /api/v1/legal/cases/{lcid}/documents             upload (multipart)
  GET    /api/v1/legal/cases/{lcid}/documents             list
  GET    /api/v1/legal/documents/{doc_id}/download        signed URL
  DELETE /api/v1/legal/documents/{doc_id}                 soft delete (sets deleted_at)
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.core.storage import storage
from app.models.legal_document import LegalDocument
from app.models.user import UserAccount
from app.models.work import LegalCase
from app.schemas.legal_document import (
    LegalDocumentCategory,
    LegalDocumentDownloadOut,
    LegalDocumentOut,
)

router = APIRouter()

LEGAL_ROLES = ("legal", "admin")

ALLOWED_MIME_PREFIXES = (
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument",
    "image/",
    "text/",
)
MAX_DOC_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_CATEGORIES = ("contract", "judgment", "notice", "evidence", "other")


def _tenant_id(payload: dict) -> int:
    tid = payload.get("tenant_id")
    if not tid:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "需要租户上下文"},
        )
    return int(tid)


def _user_id(payload: dict) -> int:
    uid = payload.get("user_id")
    if not uid:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token 缺少 user_id"},
        )
    return int(uid)


def _doc_to_out(d: LegalDocument, uploader_name: str | None) -> LegalDocumentOut:
    return LegalDocumentOut(
        id=d.id,
        legal_case_id=d.legal_case_id,
        name=d.name,
        category=d.category,
        mime_type=d.mime_type,
        size_bytes=d.size_bytes,
        uploaded_by=d.uploaded_by,
        uploaded_by_name=uploader_name,
        created_at=d.created_at,
    )


def _ensure_legal_case(db: Session, legal_case_id: int, tenant_id: int) -> LegalCase:
    lc = db.get(LegalCase, legal_case_id)
    if lc is None or lc.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "法务案件不存在"},
        )
    return lc


# ── Upload ──────────────────────────────────────────────────────────


@router.post(
    "/cases/{legal_case_id}/documents",
    response_model=LegalDocumentOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def upload_document(
    legal_case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File(...)],
    category: Annotated[LegalDocumentCategory, Form(...)],
    name: Annotated[str | None, Form()] = None,
) -> LegalDocumentOut:
    tenant_id = _tenant_id(payload)
    user_id = _user_id(payload)
    _ensure_legal_case(db, legal_case_id, tenant_id)

    if category not in ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_VALIDATION", "message": "category 不合法"},
        )

    mime = file.content_type or ""
    if mime and not any(mime.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_INVALID_MIME", "message": f"不支持的文件类型: {mime}"},
        )

    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_EMPTY_FILE", "message": "上传文件为空"},
        )
    if len(raw) > MAX_DOC_SIZE:
        raise HTTPException(
            status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "ERR_FILE_TOO_LARGE", "message": "文件超过 50MB 限制"},
        )

    filename = name or file.filename or f"document_{uuid.uuid4().hex[:8]}"
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    object_key = (
        f"legal_docs/{tenant_id}/{legal_case_id}/{uuid.uuid4().hex}.{ext}"
    )
    try:
        storage.put_object(object_key, raw, mime or "application/octet-stream")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail={"code": "ERR_STORAGE_FAILURE", "message": "文件存储失败"},
        ) from exc

    doc = LegalDocument(
        tenant_id=tenant_id,
        legal_case_id=legal_case_id,
        name=filename,
        category=category,
        object_key=object_key,
        mime_type=mime or None,
        size_bytes=len(raw),
        uploaded_by=user_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    uploader = db.get(UserAccount, user_id)
    return _doc_to_out(doc, uploader.name if uploader else None)


# ── List ────────────────────────────────────────────────────────────


@router.get(
    "/cases/{legal_case_id}/documents",
    response_model=list[LegalDocumentOut],
)
async def list_documents(
    legal_case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    category: str | None = Query(None),
) -> list[LegalDocumentOut]:
    tenant_id = _tenant_id(payload)
    _ensure_legal_case(db, legal_case_id, tenant_id)

    stmt = (
        select(LegalDocument, UserAccount.name)
        .outerjoin(UserAccount, UserAccount.id == LegalDocument.uploaded_by)
        .where(LegalDocument.tenant_id == tenant_id)
        .where(LegalDocument.legal_case_id == legal_case_id)
        .where(LegalDocument.deleted_at.is_(None))
        .order_by(LegalDocument.id.desc())
    )
    if category:
        stmt = stmt.where(LegalDocument.category == category)

    rows = db.execute(stmt).all()
    return [_doc_to_out(d, uname) for d, uname in rows]


# ── Download (signed URL) ───────────────────────────────────────────


@router.get(
    "/documents/{doc_id}/download",
    response_model=LegalDocumentDownloadOut,
)
async def get_document_download(
    doc_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalDocumentDownloadOut:
    tenant_id = _tenant_id(payload)
    doc = db.get(LegalDocument, doc_id)
    if doc is None or doc.tenant_id != tenant_id or doc.deleted_at is not None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "文件不存在"},
        )

    try:
        url = storage.get_url(doc.object_key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail={"code": "ERR_STORAGE_FAILURE", "message": "无法生成下载链接"},
        ) from exc

    return LegalDocumentDownloadOut(
        download_url=url,
        name=doc.name,
        mime_type=doc.mime_type,
        size_bytes=doc.size_bytes,
        expires_in_sec=3600,
    )


# ── Soft delete ─────────────────────────────────────────────────────


@router.delete(
    "/documents/{doc_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def delete_document(
    doc_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    tenant_id = _tenant_id(payload)
    doc = db.get(LegalDocument, doc_id)
    if doc is None or doc.tenant_id != tenant_id or doc.deleted_at is not None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "文件不存在"},
        )
    doc.deleted_at = datetime.now(UTC)
    db.commit()
