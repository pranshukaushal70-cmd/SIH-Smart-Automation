from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    institution_name: Mapped[str] = mapped_column(String(200))
    institution_id: Mapped[str] = mapped_column(String(40))
    application_type: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(60), default="")
    academic_year: Mapped[str] = mapped_column(String(20), default="")
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    processing_status: Mapped[str] = mapped_column(String(40), default="Awaiting Documents")
    review_status: Mapped[str] = mapped_column(String(60), default="Pending Review")
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_band: Mapped[str | None] = mapped_column(String(20), nullable=True)
    score_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    applied_rules: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ruleset_fingerprint: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    documents: Mapped[list["Document"]] = relationship(back_populates="application", cascade="all, delete-orphan",
                                                       order_by="Document.uploaded_at")
    findings: Mapped[list["Finding"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    reviews: Mapped[list["ReviewAction"]] = relationship(back_populates="application", cascade="all, delete-orphan",
                                                         order_by="ReviewAction.created_at")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    declared_category: Mapped[str] = mapped_column(String(60))
    original_filename: Mapped[str] = mapped_column(String(160))
    stored_filename: Mapped[str] = mapped_column(String(80))
    storage: Mapped[str] = mapped_column(String(10), default="upload")  # upload | demo
    mime_type: Mapped[str] = mapped_column(String(40))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    processing_status: Mapped[str] = mapped_column(String(30), default="Uploaded")  # Uploaded|Processed|Failed
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ocr_engine: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    pages: Mapped[list | None] = mapped_column(JSON, nullable=True)        # [{page, text, method, confidence}]
    fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)       # {name: {value, status, page, evidence}}
    detected_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    screening: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    document_status: Mapped[str] = mapped_column(String(30), default="Pending Processing")
    issuer_verification: Mapped[str] = mapped_column(String(40), default="Not Verified")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    application: Mapped[Application] = relationship(back_populates="documents")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(200))
    rule_id: Mapped[str] = mapped_column(String(30))
    rule_version: Mapped[int] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(30))   # Missing|Expired|Review Required|Flagged|Screening Signal
    severity: Mapped[str] = mapped_column(String(10))  # critical|high|medium|low|info
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    expected: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recommended_action: Mapped[str] = mapped_column(Text)
    factor: Mapped[str] = mapped_column(String(30))   # score factor bucket
    status: Mapped[str] = mapped_column(String(20), default="Open")  # Open|Reviewed
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    application: Mapped[Application] = relationship(back_populates="findings")


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    rule_type: Mapped[str] = mapped_column(String(40))
    group: Mapped[str] = mapped_column(String(30), default="compliance")  # compliance | screening
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    severity: Mapped[str] = mapped_column(String(10), default="medium")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ReviewAction(Base):
    __tablename__ = "review_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(60))
    notes: Mapped[str] = mapped_column(Text, default="")
    officer_name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    application: Mapped[Application] = relationship(back_populates="reviews")


class AuditEvent(Base):
    """Append-only (by application convention) hash-chained audit trail."""
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(60))
    actor: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(40))  # ISO string so the hash input is stable
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Counter(Base):
    __tablename__ = "counters"

    name: Mapped[str] = mapped_column(String(30), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)


def next_id(db, name: str, prefix: str, width: int = 5) -> str:
    c = db.get(Counter, name)
    if c is None:
        c = Counter(name=name, value=0)
        db.add(c)
    c.value += 1
    db.flush()
    return f"{prefix}{c.value:0{width}d}"
