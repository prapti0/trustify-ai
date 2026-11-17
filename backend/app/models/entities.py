from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.domain.enums import (
    DetectionStatus,
    FileSource,
    JobStatus,
    MatchKind,
    RiskClassification,
    UserRole,
)


def str_enum(enum_cls: type) -> Enum:
    return Enum(
        enum_cls,
        native_enum=False,
        length=32,
        values_callable=lambda obj: [item.value for item in obj],
    )


def _id() -> Mapped[UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = _id()
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(str_enum(UserRole), default=UserRole.USER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[UUID] = _id()
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = _created()

    __table_args__ = (Index("ix_user_sessions_user_id", "user_id"),)


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[UUID] = _id()
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255))
    detected_format: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[FileSource] = mapped_column(str_enum(FileSource), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        Index("ix_uploaded_files_user_id", "user_id"),
        Index("ix_uploaded_files_sha256", "sha256"),
    )


class FileMetadata(Base):
    __tablename__ = "file_metadata"

    id: Mapped[UUID] = _id()
    file_id: Mapped[UUID] = mapped_column(
        ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    container: Mapped[str | None] = mapped_column(String(128))
    codec: Mapped[str | None] = mapped_column(String(128))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    exif: Mapped[dict | None] = mapped_column(JSON)
    extra: Mapped[dict | None] = mapped_column(JSON)
    extracted_at: Mapped[datetime] = _created()


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[UUID] = _id()
    file_id: Mapped[UUID] = mapped_column(ForeignKey("uploaded_files.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        str_enum(JobStatus),
        default=JobStatus.UPLOADED,
        nullable=False,
    )
    modules: Mapped[list | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        Index("ix_analysis_jobs_user_id", "user_id"),
        Index("ix_analysis_jobs_status", "status"),
    )


class DetectionResult(Base):
    __tablename__ = "detection_results"

    id: Mapped[UUID] = _id()
    job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False)
    module: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[DetectionStatus] = mapped_column(str_enum(DetectionStatus), nullable=False)
    finding_label: Mapped[str | None] = mapped_column(String(128))
    confidence: Mapped[float | None] = mapped_column(Float)
    model_name: Mapped[str | None] = mapped_column(String(128))
    model_version: Mapped[str | None] = mapped_column(String(64))
    limitations: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        Index("ix_detection_results_job_id", "job_id"),
        CheckConstraint(
            "status = 'completed' OR confidence IS NULL",
            name="ck_detection_results_confidence_only_when_completed",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_detection_results_confidence_range",
        ),
    )


class ForensicEvidence(Base):
    __tablename__ = "forensic_evidence"

    id: Mapped[UUID] = _id()
    job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False)
    detection_result_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("detection_results.id", ondelete="SET NULL")
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    observation: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    source_module: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (Index("ix_forensic_evidence_job_id", "job_id"),)


class SecurityScanResult(Base):
    __tablename__ = "security_scan_results"

    id: Mapped[UUID] = _id()
    job_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False)
    engine: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[DetectionStatus] = mapped_column(str_enum(DetectionStatus), nullable=False)
    findings: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (Index("ix_security_scan_results_job_id", "job_id"),)


class DuplicateMatch(Base):
    __tablename__ = "duplicate_matches"

    id: Mapped[UUID] = _id()
    file_id: Mapped[UUID] = mapped_column(ForeignKey("uploaded_files.id", ondelete="CASCADE"), nullable=False)
    matched_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        nullable=False,
    )
    match_kind: Mapped[MatchKind] = mapped_column(str_enum(MatchKind), nullable=False)
    distance: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (Index("ix_duplicate_matches_file_id", "file_id"),)


class InvestigationReport(Base):
    __tablename__ = "investigation_reports"

    id: Mapped[UUID] = _id()
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    overall_classification: Mapped[RiskClassification | None] = mapped_column(str_enum(RiskClassification))
    summary: Mapped[str | None] = mapped_column(Text)
    ai_generation: Mapped[dict | None] = mapped_column(JSON)
    manipulation: Mapped[dict | None] = mapped_column(JSON)
    malware: Mapped[dict | None] = mapped_column(JSON)
    provenance: Mapped[dict | None] = mapped_column(JSON)
    similarity: Mapped[dict | None] = mapped_column(JSON)
    scam: Mapped[dict | None] = mapped_column(JSON)
    limitations: Mapped[str] = mapped_column(Text, nullable=False)
    pdf_key: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        CheckConstraint(
            "overall_classification IS NULL OR overall_classification IN "
            "('low', 'medium', 'high', 'critical', 'inconclusive')",
            name="ck_investigation_reports_classification",
        ),
    )


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[UUID] = _id()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    task: Mapped[str] = mapped_column(String(128), nullable=False)
    license_name: Mapped[str] = mapped_column(String(128), nullable=False)
    metrics: Mapped[dict | None] = mapped_column(JSON)
    artifact_uri: Mapped[str | None] = mapped_column(String(1024))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (Index("ix_model_versions_name_version", "name", "version", unique=True),)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[UUID] = _id()
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()

    __table_args__ = (Index("ix_api_keys_user_id", "user_id"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = _id()
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    context: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (Index("ix_audit_logs_created_at", "created_at"),)
