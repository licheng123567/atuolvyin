"""Sprint 16.4 — 法律文书模板 schema (PRD §20.4)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LegalDocumentTemplateOut(BaseModel):
    id: int
    tenant_id: int | None
    package_type: str
    slug: str
    title: str
    body_md: str
    enabled: bool
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LegalDocumentRenderOut(BaseModel):
    id: int
    order_id: int
    template_id: int
    title: str
    body_md: str
    rendered_at: datetime
    rendered_by: int | None
    version: int

    model_config = {"from_attributes": True}
