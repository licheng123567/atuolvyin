from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.call import SuggestionFeedback


def infer_signals_for_call(call_id: int, intent: str, db: Session) -> None:
    if intent in ("payment_confirmed", "promise_made"):
        signal = 1
    elif intent in ("complaint",):
        signal = -1
    else:
        signal = 0

    db.execute(
        update(SuggestionFeedback)
        .where(
            SuggestionFeedback.call_id == call_id,
            SuggestionFeedback.script_template_id.is_not(None),
        )
        .values(inferred_signal=signal)
    )
    db.flush()
