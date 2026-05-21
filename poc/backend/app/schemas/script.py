from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_SCENE_PATTERN = r"^(opening|objection_handling|promise_confirm|closing)$"


class ScriptTemplateCreate(BaseModel):
    title: str = Field(..., max_length=128)
    scene: str = Field("objection_handling", pattern=_SCENE_PATTERN)
    trigger_intent: str = Field(..., max_length=64)
    content: str
    notes: str | None = None
    # v1.5.7 — 项目级生效范围（None=本物业全项目通用）
    project_id: int | None = None


class ScriptTemplateUpdate(BaseModel):
    title: str | None = Field(None, max_length=128)
    scene: str | None = Field(None, pattern=_SCENE_PATTERN)
    trigger_intent: str | None = Field(None, max_length=64)
    content: str | None = None
    notes: str | None = None
    project_id: int | None = None


class ScriptTemplateOut(BaseModel):
    id: int
    tenant_id: int | None = None
    provider_id: int | None = None
    project_id: int | None = None
    project_name: str | None = None  # v1.5.7 — 派生字段，前端展示项目名
    title: str
    scene: str = "objection_handling"
    trigger_intent: str
    content: str
    notes: str | None = None
    version: int
    is_active: bool
    usage_count: int
    adoption_rate: float | None = None
    conversion_rate: float | None = None
    score_grade: str | None = None
    created_at: datetime
    updated_at: datetime
    # v1.4 S16.5 — 派生字段（前端展示来源）
    source: Literal["platform", "tenant", "provider"] = "platform"
    model_config = ConfigDict(from_attributes=True)


class ScriptVersionOut(BaseModel):
    version: int
    title: str
    trigger_intent: str
    content: str
    notes: str | None = None
    edited_by: int | None = None
    edited_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RollbackIn(BaseModel):
    to_version: int


class ImportResultOut(BaseModel):
    success: int
    skipped: int
    failed: int
    errors: list[str]


class SupervisorLabelCreate(BaseModel):
    label: Literal["good", "bad"]
    note: str | None = None

    @model_validator(mode="after")
    def note_required_for_bad(self) -> SupervisorLabelCreate:
        if self.label == "bad" and not self.note:
            raise ValueError("差话术标注必须填写点评")
        return self


class SupervisorLabelOut(BaseModel):
    feedback_id: int
    call_id: int
    suggestion_text: str
    supervisor_label: str | None = None
    supervisor_note: str | None = None
    script_template_id: int | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SuggestionConfigOut(BaseModel):
    sensitivity: int
    max_per_push: int


class SuggestionConfigUpdate(BaseModel):
    sensitivity: int = Field(..., ge=1, le=5)
    max_per_push: int = Field(..., ge=1, le=10)


class ScriptEffectivenessItem(BaseModel):
    """Sprint 8.2 — aggregated effectiveness signal for one script template."""

    template_id: int
    title: str
    trigger_intent: str
    is_active: bool
    total_shown: int
    total_adopted: int
    adoption_rate: float | None = None
    total_supervised: int
    total_good: int
    good_ratio: float | None = None
    composite_score: float | None = None
    composite_grade: Literal["A", "B", "C", "D"] | None = None
    # v0.6.0 — AI 评分(0-100,基于回款率 70% + 采用率 30%)+ 样本数 + 最近更新
    ai_score: float | None = None
    ai_score_sample_count: int | None = None
    ai_score_updated_at: datetime | None = None


class ScriptEffectivenessOut(BaseModel):
    period_days: int
    items: list[ScriptEffectivenessItem]
