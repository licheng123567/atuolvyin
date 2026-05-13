"""Sprint 11.6 — LegalDocument schemas (PRD §L2136)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

LegalDocumentCategory = Literal["contract", "judgment", "notice", "evidence", "other"]


class LegalDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    legal_case_id: int
    name: str
    category: str
    mime_type: str | None
    size_bytes: int
    uploaded_by: int
    uploaded_by_name: str | None = None
    created_at: datetime


class LegalDocumentDownloadOut(BaseModel):
    """Download response — returns a signed URL the browser can hit directly,
    or `inline_bytes_b64` for very small files (deferred — MVP uses URL only)."""

    download_url: str
    name: str
    mime_type: str | None
    size_bytes: int
    expires_in_sec: int
