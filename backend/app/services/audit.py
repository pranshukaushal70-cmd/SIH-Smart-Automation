"""Hash-chained audit log.

Each event stores sha256(prev_hash + canonical JSON of the event). Editing or deleting a stored row
breaks the chain and is detected by verify_chain(). The SQLite table itself is still editable by
anyone with file access, so this is tamper-*evident*, not tamper-proof.
"""
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select

from ..models import AuditEvent

GENESIS = "0" * 64


def _digest(prev_hash: str, application_id, event_type, actor, details, created_at) -> str:
    payload = json.dumps({"application_id": application_id, "event_type": event_type, "actor": actor,
                          "details": details, "created_at": created_at}, sort_keys=True, separators=(",", ":"),
                         default=str)
    return hashlib.sha256((prev_hash + payload).encode("utf-8")).hexdigest()


def record(db, event_type: str, actor: str, application_id: str | None = None, details: dict | None = None):
    details = json.loads(json.dumps(details or {}, default=str))
    last = db.execute(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)).scalar_one_or_none()
    prev = last.hash if last else GENESIS
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ev = AuditEvent(application_id=application_id, event_type=event_type, actor=actor, details=details,
                    created_at=created_at, prev_hash=prev,
                    hash=_digest(prev, application_id, event_type, actor, details, created_at))
    db.add(ev)
    db.flush()
    return ev


def verify_chain(db) -> dict:
    prev = GENESIS
    count = 0
    for ev in db.execute(select(AuditEvent).order_by(AuditEvent.id)).scalars():
        count += 1
        expected = _digest(prev, ev.application_id, ev.event_type, ev.actor, ev.details, ev.created_at)
        if ev.prev_hash != prev or ev.hash != expected:
            return {"valid": False, "events_checked": count, "first_invalid_event_id": ev.id,
                    "message": f"Chain broken at event #{ev.id}: stored data no longer matches its hash."}
        prev = ev.hash
    return {"valid": True, "events_checked": count, "first_invalid_event_id": None,
            "head_hash": prev, "message": f"All {count} events verified; hash chain intact."}
