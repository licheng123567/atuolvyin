import pytest
from decimal import Decimal

from app.schemas.case import CaseImportRow
from app.schemas.user import UserCreateRequest
from app.schemas.call import CallMinuteQuotaStatus


def test_case_import_valid_phone():
    row = CaseImportRow(name="张三", phone="13800138001", amount_owed=Decimal("1200"))
    assert row.phone == "13800138001"


def test_case_import_invalid_phone():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CaseImportRow(name="张三", phone="12345")


def test_user_create_strips_whitespace():
    req = UserCreateRequest(name="  李四  ", phone="13900139001", role="agent_internal")
    assert req.name == "李四"


def test_quota_exhausted_flag():
    status = CallMinuteQuotaStatus(
        tenant_id=1, year_month="2026-04",
        used_minutes=100, quota=100, remaining=0,
        pct_used=1.0, is_exhausted=True
    )
    assert status.is_exhausted is True


def test_quota_no_limit():
    status = CallMinuteQuotaStatus(
        tenant_id=1, year_month="2026-04",
        used_minutes=500, quota=None, remaining=None,
        pct_used=None, is_exhausted=False
    )
    assert status.quota is None
    assert not status.is_exhausted


def test_script_schemas_import_and_validate():
    from app.schemas.script import (
        ScriptTemplateCreate, ScriptTemplateUpdate, ScriptTemplateOut,
        ScriptVersionOut, ImportResultOut,
        SupervisorLabelCreate, SuggestionConfigOut, SuggestionConfigUpdate,
    )
    obj = ScriptTemplateCreate(title="T", trigger_intent="其他", content="内容")
    assert obj.title == "T"

    label = SupervisorLabelCreate(label="bad", note="有问题")
    assert label.label == "bad"

    # bad 话术必须有 note
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        SupervisorLabelCreate(label="bad")


def test_suggestion_feedbackin_accepts_script_template_id():
    from app.schemas.call import SuggestionFeedbackIn
    fb = SuggestionFeedbackIn(action="adopt", script_template_id=5)
    assert fb.script_template_id == 5
    fb2 = SuggestionFeedbackIn(action="ignore")
    assert fb2.script_template_id is None
