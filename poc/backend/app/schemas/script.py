from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScriptTemplateCreate(BaseModel):
    title: str = Field(..., max_length=128)
    trigger_intent: str = Field(..., max_length=64)
    content: str
    notes: Optional[str] = None


class ScriptTemplateUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=128)
    trigger_intent: Optional[str] = Field(None, max_length=64)
    content: Optional[str] = None
    notes: Optional[str] = None


class ScriptTemplateOut(BaseModel):
    id: int
    tenant_id: Optional[int] = None
    title: str
    trigger_intent: str
    content: str
    notes: Optional[str] = None
    version: int
    is_active: bool
    usage_count: int
    adoption_rate: Optional[float] = None
    conversion_rate: Optional[float] = None
    score_grade: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ScriptVersionOut(BaseModel):
    version: int
    title: str
    trigger_intent: str
    content: str
    notes: Optional[str] = None
    edited_by: Optional[int] = None
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
    note: Optional[str] = None

    @model_validator(mode="after")
    def note_required_for_bad(self) -> "SupervisorLabelCreate":
        if self.label == "bad" and not self.note:
            raise ValueError("差话术标注必须填写点评")
        return self


class SupervisorLabelOut(BaseModel):
    feedback_id: int
    call_id: int
    suggestion_text: str
    supervisor_label: Optional[str] = None
    supervisor_note: Optional[str] = None
    script_template_id: Optional[int] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SuggestionConfigOut(BaseModel):
    sensitivity: int
    max_per_push: int


class SuggestionConfigUpdate(BaseModel):
    sensitivity: int = Field(..., ge=1, le=5)
    max_per_push: int = Field(..., ge=1, le=10)
