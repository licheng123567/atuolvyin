"""v1.9.5 — 案件证据包 ZIP 构建（按 CollectionCase）。

复用方：
- 旧版 GET /api/v1/legal/cases/{legal_case_id}/evidence-bundle（按 LegalCase）
- 新版 GET /api/v1/legal/internal-orders/{order_id}/evidence-bundle（按 LegalConversionOrder）

ZIP 结构：
  case_{case_id}/
    case_summary.json
    calls/call_{id}/
      recording.{ext}        ← 原始录音（如有 object_key）
      transcript.txt          ← ASR 全文
      transcript.segments.json
      analysis.json           ← 摘要 + 关键片段
      attestation.json        ← SHA256 + 区块链 tx_id
    legal_internal_actions.json   ← v1.9.5 新增：物业法务处理流水（如有）
    letters/letter_{action_id}/   ← v1.9.5 新增：律师函/催告函附件
      {filename}                ← 盖章版 PDF/JPG（如已上传）
      action_meta.json          ← 模板/律所/起草时间
    bundle_manifest.json
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.storage import storage
from app.models.call import AnalysisResult, CallRecord, Transcript
from app.models.case import CollectionCase, OwnerProfile
from app.models.legal_internal import (
    InternalLegalLetterTemplate,
    LegalInternalAction,
    PartnerLawFirm,
)
from app.models.tenant import Tenant
from app.models.user import UserAccount
from app.services import blockchain as blockchain_svc


def _ext_from_object_key(object_key: str) -> str:
    if "." in object_key:
        return object_key.rsplit(".", 1)[-1]
    return "bin"


def _attestation_to_blockchain_meta(att: Any) -> dict[str, Any]:
    return {
        "data_type": att.data_type,
        "provider": att.chain_provider,
        "endpoint": att.chain_endpoint,
        "status": att.status,
        "transaction_id": att.tx_hash,
        "block_height": att.block_height,
        "evidence_id": att.provider_evidence_id,
        "preservation_id": att.preservation_id,
        "submitted_at": att.submitted_at.isoformat() if att.submitted_at else None,
        "verify_url": f"/verify/{att.tx_hash}" if att.tx_hash else None,
    }


def build_evidence_bundle_zip(
    db: Session,
    *,
    tenant_id: int,
    case: CollectionCase,
    owner: OwnerProfile,
    case_summary_extra: dict[str, Any] | None = None,
    user_id: int | None = None,
    legal_case_id: int | None = None,
    legal_order_id: int | None = None,
    owner_phone_display: str | None = None,
) -> tuple[io.BytesIO, str]:
    """构建案件证据包 ZIP。

    Args:
        case_summary_extra: 写入 case_summary.json 的额外字段（如 legal_stage / law_firm）
        legal_case_id: 旧版 LegalCase.id（写入 manifest，便于追溯）
        legal_order_id: v1.9.0 LegalConversionOrder.id（写入 manifest）
        owner_phone_display: 调用方决定的电话展示串（明文或脱敏），写入 case_summary.json

    Returns:
        (BytesIO 数据流, 建议文件名)
    """
    tenant = db.get(Tenant, tenant_id)
    generated_at = datetime.now(UTC)

    calls = (
        db.execute(
            select(CallRecord)
            .where(CallRecord.tenant_id == tenant_id)
            .where(CallRecord.case_id == case.id)
            .order_by(CallRecord.id.asc())
        )
        .scalars()
        .all()
    )

    files_index: list[dict[str, Any]] = []
    base_dir = f"case_{case.id}"
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:

        def _write(path: str, data: bytes) -> None:
            zf.writestr(path, data)
            files_index.append(
                {
                    "path": path,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size": len(data),
                }
            )

        # ── case_summary.json ────────────────────────────
        case_summary: dict[str, Any] = {
            "owner_name": owner.name,
            "owner_phone_masked": owner_phone_display,
            "address": " ".join(p for p in (owner.building, owner.room) if p) or None,
            "amount_owed": str(case.amount_owed) if case.amount_owed is not None else None,
            "months_overdue": case.months_overdue,
            "case_stage": case.stage,
        }
        if case_summary_extra:
            case_summary.update(case_summary_extra)
        _write(
            f"{base_dir}/case_summary.json",
            json.dumps(case_summary, ensure_ascii=False, indent=2).encode("utf-8"),
        )

        # ── 通话录音 + 转写 + AI + 区块链 ──────────────
        for call in calls:
            call_dir = f"{base_dir}/calls/call_{call.id}"

            recording_sha: str | None = None
            recording_bytes: bytes | None = None
            recording_skipped = False
            recording_skip_reason: str | None = None
            if call.object_key:
                try:
                    audio = storage.get_bytes(call.object_key)
                except Exception as exc:
                    raise HTTPException(
                        status_code=http_status.HTTP_502_BAD_GATEWAY,
                        detail={
                            "code": "ERR_BUNDLE_IO",
                            "message": f"读取录音失败 (call_id={call.id})",
                        },
                    ) from exc
                ext = _ext_from_object_key(call.object_key)
                _write(f"{call_dir}/recording.{ext}", audio)
                recording_sha = hashlib.sha256(audio).hexdigest()
                recording_bytes = audio
            else:
                recording_skipped = True
                recording_skip_reason = "object_key 为空，未上传录音"
                files_index.append(
                    {
                        "path": f"{call_dir}/recording",
                        "skipped": True,
                        "reason": recording_skip_reason,
                    }
                )

            transcript = db.execute(
                select(Transcript).where(Transcript.call_id == call.id)
            ).scalar_one_or_none()
            transcript_sha: str | None = None
            transcript_bytes: bytes | None = None
            if transcript and transcript.full_text:
                transcript_bytes = transcript.full_text.encode("utf-8")
                _write(f"{call_dir}/transcript.txt", transcript_bytes)
                transcript_sha = files_index[-1]["sha256"]
                if transcript.segments:
                    _write(
                        f"{call_dir}/transcript.segments.json",
                        json.dumps(transcript.segments, ensure_ascii=False, indent=2).encode(
                            "utf-8"
                        ),
                    )
            else:
                files_index.append(
                    {
                        "path": f"{call_dir}/transcript.txt",
                        "skipped": True,
                        "reason": "无转写内容",
                    }
                )

            analysis = db.execute(
                select(AnalysisResult).where(AnalysisResult.call_id == call.id)
            ).scalar_one_or_none()
            analysis_sha: str | None = None
            analysis_bytes: bytes | None = None
            if analysis:
                analysis_payload = {
                    "summary": analysis.summary,
                    "key_segments": analysis.key_segments,
                    "needs_review": analysis.needs_review,
                }
                analysis_bytes = json.dumps(analysis_payload, ensure_ascii=False, indent=2).encode(
                    "utf-8"
                )
                _write(f"{call_dir}/analysis.json", analysis_bytes)
                analysis_sha = files_index[-1]["sha256"]
            else:
                files_index.append(
                    {
                        "path": f"{call_dir}/analysis.json",
                        "skipped": True,
                        "reason": "无 AI 分析",
                    }
                )

            # 区块链上链 —— 录音 / 转写 / 分析各上一次，单条失败不阻断
            blockchain_metas: list[dict[str, Any]] = []
            _attest_targets: list[tuple[str, bytes | None, str]] = [
                ("call_recording", recording_bytes, f"案件{case.id}通话{call.id}录音"),
                ("transcript", transcript_bytes, f"案件{case.id}通话{call.id}转写"),
                ("analysis", analysis_bytes, f"案件{case.id}通话{call.id}AI分析"),
            ]
            for _dtype, _payload, _title in _attest_targets:
                if _payload is None:
                    continue
                att = blockchain_svc.submit_attestation(
                    db,
                    tenant_id=tenant_id,
                    data=_payload,
                    data_type=_dtype,
                    title=_title,
                    description=tenant.name if tenant else None,
                    call_id=call.id,
                    legal_case_id=legal_case_id,
                    payload_metadata={
                        "tenant_name": tenant.name if tenant else None,
                        "call_id": call.id,
                        "case_id": case.id,
                        "data_type": _dtype,
                        "started_at": call.started_at.isoformat() if call.started_at else None,
                        "duration_sec": call.duration_sec,
                    },
                )
                blockchain_metas.append(_attestation_to_blockchain_meta(att))

            attestation = {
                "call_id": call.id,
                "tenant_id": tenant_id,
                "case_id": case.id,
                "started_at": call.started_at.isoformat() if call.started_at else None,
                "duration_sec": call.duration_sec,
                "recording_sha256": recording_sha,
                "recording_skipped": recording_skipped,
                "recording_skip_reason": recording_skip_reason,
                "transcript_sha256": transcript_sha,
                "analysis_sha256": analysis_sha,
                "computed_at": generated_at.isoformat(),
                "blockchain": blockchain_metas,
            }
            _write(
                f"{call_dir}/attestation.json",
                json.dumps(attestation, ensure_ascii=False, indent=2).encode("utf-8"),
            )

        # ── v1.9.5 — 物业法务内部处理流水 + 律师函附件 ─────
        actions = (
            db.execute(
                select(LegalInternalAction)
                .where(LegalInternalAction.tenant_id == tenant_id)
                .where(LegalInternalAction.case_id == case.id)
                .order_by(LegalInternalAction.occurred_at.asc())
            )
            .scalars()
            .all()
        )
        if actions:
            actor_ids = {a.actor_user_id for a in actions if a.actor_user_id}
            tpl_ids = {a.letter_template_id for a in actions if a.letter_template_id}
            firm_ids = {a.partner_law_firm_id for a in actions if a.partner_law_firm_id}
            actor_map = (
                dict(
                    db.execute(
                        select(UserAccount.id, UserAccount.name).where(
                            UserAccount.id.in_(actor_ids)
                        )
                    ).all()
                )
                if actor_ids
                else {}
            )
            tpl_map = (
                dict(
                    db.execute(
                        select(
                            InternalLegalLetterTemplate.id, InternalLegalLetterTemplate.name
                        ).where(InternalLegalLetterTemplate.id.in_(tpl_ids))
                    ).all()
                )
                if tpl_ids
                else {}
            )
            firm_map = (
                dict(
                    db.execute(
                        select(PartnerLawFirm.id, PartnerLawFirm.name).where(
                            PartnerLawFirm.id.in_(firm_ids)
                        )
                    ).all()
                )
                if firm_ids
                else {}
            )

            actions_payload = [
                {
                    "id": a.id,
                    "action_type": a.action_type,
                    "occurred_at": a.occurred_at.isoformat() if a.occurred_at else None,
                    "actor_name": actor_map.get(a.actor_user_id),
                    "note": a.note,
                    "letter_template_name": tpl_map.get(a.letter_template_id)
                    if a.letter_template_id
                    else None,
                    "partner_law_firm_name": firm_map.get(a.partner_law_firm_id)
                    if a.partner_law_firm_id
                    else None,
                    "letter_variables": a.letter_variables,
                    "attachment_filename": a.attachment_filename,
                }
                for a in actions
            ]
            _write(
                f"{base_dir}/legal_internal_actions.json",
                json.dumps(actions_payload, ensure_ascii=False, indent=2).encode("utf-8"),
            )

            # 律师函/催告函附件 PDF
            for a in actions:
                if a.action_type not in ("send_lawyer_letter", "send_notice"):
                    continue
                if not a.attachment_key:
                    continue
                letter_dir = f"{base_dir}/letters/letter_{a.id}"
                try:
                    letter_bytes = storage.get_bytes(a.attachment_key)
                    safe_name = a.attachment_filename or "attachment.bin"
                    _write(f"{letter_dir}/{safe_name}", letter_bytes)
                except Exception as exc:  # noqa: BLE001
                    files_index.append(
                        {
                            "path": f"{letter_dir}/{a.attachment_filename or 'attachment'}",
                            "skipped": True,
                            "reason": f"读取附件失败：{exc!s}",
                        }
                    )
                # action_meta.json 单独留一份，便于举证「这封律师函的元数据」
                _write(
                    f"{letter_dir}/action_meta.json",
                    json.dumps(
                        {
                            "id": a.id,
                            "action_type": a.action_type,
                            "occurred_at": a.occurred_at.isoformat() if a.occurred_at else None,
                            "actor_name": actor_map.get(a.actor_user_id),
                            "note": a.note,
                            "letter_template_name": tpl_map.get(a.letter_template_id)
                            if a.letter_template_id
                            else None,
                            "partner_law_firm_name": firm_map.get(a.partner_law_firm_id)
                            if a.partner_law_firm_id
                            else None,
                            "letter_variables": a.letter_variables,
                            "attachment_filename": a.attachment_filename,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ).encode("utf-8"),
                )

        # ── bundle_manifest.json（最后写，包含全部 sha256）──
        bundle_sha = hashlib.sha256(
            "".join(f.get("sha256") or "" for f in files_index).encode("utf-8")
        ).hexdigest()
        manifest = {
            "bundle_version": "1.1",  # v1.1 加 legal_internal_actions + letters
            "generated_at": generated_at.isoformat(),
            "generated_by_user_id": user_id,
            "tenant_id": tenant_id,
            "tenant_name": tenant.name if tenant else None,
            "legal_case_id": legal_case_id,
            "legal_order_id": legal_order_id,
            "collection_case_id": case.id,
            "call_count": len(calls),
            "internal_action_count": len(actions),
            "files": files_index,
            "bundle_sha256": bundle_sha,
        }
        zf.writestr(
            f"{base_dir}/bundle_manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )

    db.commit()  # 持久化区块链 attestation 行
    buffer.seek(0)
    filename = f"evidence_case_{case.id}_{generated_at.strftime('%Y%m%d')}.zip"
    return buffer, filename
