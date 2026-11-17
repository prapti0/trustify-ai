from enum import Enum


class UserRole(str, Enum):
    USER = "user"
    ANALYST = "analyst"
    ADMIN = "admin"


class FileSource(str, Enum):
    UPLOAD = "upload"
    URL = "url"


class JobStatus(str, Enum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DetectionStatus(str, Enum):
    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    SKIPPED = "skipped"


class RiskClassification(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    INCONCLUSIVE = "inconclusive"


class MatchKind(str, Enum):
    EXACT_HASH = "exact_hash"
    PERCEPTUAL = "perceptual"
    EMBEDDING = "embedding"
    FINGERPRINT = "fingerprint"
