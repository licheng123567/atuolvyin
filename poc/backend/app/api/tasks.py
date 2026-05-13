from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db

router = APIRouter()


@router.get("/today")
def today(device_id: str = Query(...), db: Session = Depends(get_db)):
    row = db.execute(text("SELECT id FROM device WHERE device_id=:d"), {"d": device_id}).fetchone()
    if not row:
        raise HTTPException(404, "device not registered")
    dev_pk = row[0]

    rows = (
        db.execute(
            text("""
        SELECT t.id, t.type, t.payload, t.priority,
               o.id AS owner_id, o.name, o.phone, o.building, o.room, o.history
        FROM task t JOIN owner o ON o.id=t.owner_id
        WHERE (t.assigned_to=:d OR t.assigned_to IS NULL) AND t.status='pending'
        ORDER BY t.priority DESC, t.id ASC
    """),
            {"d": dev_pk},
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]
