from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserPublic(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    role: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    session_id: UUID
    user: UserPublic


class RegisterBody(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    password: str
    accepted_terms: bool


class LoginBody(BaseModel):
    email: str
    password: str


class ProfileBody(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)


class PasswordBody(BaseModel):
    current_password: str
    new_password: str


class MessageBody(BaseModel):
    error: str
    message: str


class SessionPublic(BaseModel):
    id: UUID
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    ip_address: str | None
    user_agent: str | None
    current: bool


class StagePublic(BaseModel):
    id: str
    label: str
    state: str
    detail: str


class JobSummary(BaseModel):
    job_id: UUID
    file_id: UUID
    file_name: str
    file_type: str
    category: str
    size_bytes: int
    sha256: str
    created_at: datetime
    status: str
    classification: str | None


class CountPoint(BaseModel):
    label: str
    count: int


class ActivityPoint(BaseModel):
    date: str
    count: int


class DashboardResponse(BaseModel):
    total_files: int
    ai_generated_indicators: int
    suspicious_files: int
    deepfake_indicators: int
    security_threats: int
    completed_investigations: int
    notes: dict[str, str]
    recent: list[JobSummary]
    file_types: list[CountPoint]
    risk_distribution: list[CountPoint]
    detection_results: list[CountPoint]
    activity: list[ActivityPoint]


class EvidencePublic(BaseModel):
    category: str
    observation: str
    severity: str
    source_module: str


class ModulePublic(BaseModel):
    module: str
    status: str
    finding_label: str | None
    confidence: float | None
    limitations: str
    details: dict | None


class DuplicatePublic(BaseModel):
    file_id: UUID
    file_name: str
    matched_file_id: UUID
    matched_file_name: str
    match_kind: str
    distance: float | None


class MetadataPublic(BaseModel):
    container: str | None = None
    codec: str | None = None
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    exif: dict | None = None
    extra: dict | None = None


class ReportResponse(BaseModel):
    job_id: UUID
    file_id: UUID
    file_name: str
    file_type: str
    category: str
    size_bytes: int
    sha256: str
    created_at: datetime
    status: str
    classification: str | None
    summary: str | None
    limitations: str
    metadata: MetadataPublic | None = None
    stages: list[StagePublic]
    modules: list[ModulePublic]
    evidence: list[EvidencePublic]
    sections: dict
    duplicates: list[DuplicatePublic]
    warnings: list[str]
    unverified_claims: list[str]
    recommended_steps: list[str]


class UrlBody(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class ScamBody(BaseModel):
    kind: str = Field(pattern="^(media|url|message|claim)$")
    content: str = Field(min_length=1, max_length=4000)
