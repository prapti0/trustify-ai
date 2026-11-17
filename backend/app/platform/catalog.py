import importlib.util
import shutil
from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import Settings

EngineStatus = Literal["ready", "not_integrated"]
ServiceState = Literal["implemented", "foundation", "schema_only", "not_started"]


class RuntimeProbe(BaseModel):
    name: str
    present: bool


class EngineCapability(BaseModel):
    id: str
    name: str
    status: EngineStatus
    detail: str
    runtime: list[RuntimeProbe] = Field(default_factory=list)


class ServiceCapability(BaseModel):
    id: str
    name: str
    phase: int
    state: ServiceState
    detail: str


class PlatformStatus(BaseModel):
    name: str
    version: str
    phase: int
    max_upload_bytes: int
    auth_configured: bool
    storage_backend: str
    guarantees: list[str]
    services: list[ServiceCapability]
    engines: list[EngineCapability]


GUARANTEES = [
    "Detection scores are not simulated.",
    "A missing model is reported as not integrated.",
    "Uploaded content is never executed.",
    "Absence of metadata is not treated as proof that content is synthetic.",
    "Separate findings are not averaged into one authenticity score.",
]


def module_present(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def binary_present(name: str) -> bool:
    return shutil.which(name) is not None


def build_platform_status(settings: Settings) -> PlatformStatus:
    ffmpeg = binary_present("ffmpeg")
    ffprobe = binary_present("ffprobe")
    mediainfo = binary_present("mediainfo")
    clamscan = binary_present("clamscan")
    torch = module_present("torch")
    transformers = module_present("transformers")
    pillow = module_present("PIL")
    cv2 = module_present("cv2")
    whisper = module_present("whisper")
    librosa = module_present("librosa")
    yara = module_present("yara")

    ml_packages = bool(torch and transformers and pillow)
    ml_enabled = bool(settings.enable_ml_detectors and ml_packages)
    image_ready = ml_enabled
    video_ready = bool(ml_enabled and cv2)

    engines = [
        EngineCapability(
            id="file_signature",
            name="File signature identification",
            status="ready",
            detail="Magic-byte identification is implemented. It does not judge whether content is synthetic.",
        ),
        EngineCapability(
            id="sha256",
            name="SHA-256 integrity",
            status="ready",
            detail="SHA-256 hashing is implemented for exact integrity and duplicate comparisons.",
        ),
        EngineCapability(
            id="container_metadata",
            name="Container metadata",
            status="ready",
            detail=(
                "Pure-Python parsers record dimensions, duration, brands, and archive member lists. "
                "Missing metadata is inconclusive and is not treated as synthetic-media proof."
            ),
            runtime=[
                RuntimeProbe(name="ffmpeg", present=ffmpeg),
                RuntimeProbe(name="ffprobe", present=ffprobe),
                RuntimeProbe(name="mediainfo", present=mediainfo),
            ],
        ),
        EngineCapability(
            id="image_forensics",
            name="Image forensics",
            status="ready" if image_ready else "not_integrated",
            detail=(
                f"Hugging Face image classifiers are wired "
                f"({settings.ai_image_model_id}; {settings.deepfake_image_model_id}). "
                "Weights load on first inference. Missing packages or a failed load returns unavailable, "
                "not a simulated score. Confidences are not fused."
                if image_ready
                else (
                    "Image detectors are registered in code but not ready. "
                    "Install backend/requirements-ml.txt and keep ENABLE_ML_DETECTORS=true. "
                    "No image score is produced until packages are present."
                )
            ),
            runtime=[
                RuntimeProbe(name="torch", present=torch),
                RuntimeProbe(name="transformers", present=transformers),
                RuntimeProbe(name="PIL", present=pillow),
                RuntimeProbe(name="cv2", present=cv2),
            ],
        ),
        EngineCapability(
            id="video_forensics",
            name="Video forensics",
            status="ready" if video_ready else "not_integrated",
            detail=(
                f"OpenCV samples up to {settings.video_detector_max_frames} frames; "
                "each frame is scored by the image detectors. No fused video authenticity score. "
                "Lip-sync and temporal models are not integrated."
                if video_ready
                else (
                    "Video frame sampling needs OpenCV plus ML packages "
                    "(backend/requirements-ml.txt). No video score is produced until ready."
                )
            ),
            runtime=[
                RuntimeProbe(name="ffmpeg", present=ffmpeg),
                RuntimeProbe(name="ffprobe", present=ffprobe),
                RuntimeProbe(name="mediainfo", present=mediainfo),
                RuntimeProbe(name="cv2", present=cv2),
                RuntimeProbe(name="torch", present=torch),
            ],
        ),
        EngineCapability(
            id="audio_forensics",
            name="Audio forensics",
            status="not_integrated",
            detail="No speech or voice-clone model is registered. No audio score is produced.",
            runtime=[
                RuntimeProbe(name="ffmpeg", present=ffmpeg),
                RuntimeProbe(name="whisper", present=whisper),
                RuntimeProbe(name="librosa", present=librosa),
            ],
        ),
        EngineCapability(
            id="document_forensics",
            name="Document forensics",
            status="not_integrated",
            detail="Document structure, signature, and script inspection are not implemented.",
        ),
        EngineCapability(
            id="malware_scanner",
            name="Malware scanner",
            status="not_integrated",
            detail="ClamAV and YARA are not invoked. Files are never executed.",
            runtime=[
                RuntimeProbe(name="clamscan", present=clamscan),
                RuntimeProbe(name="yara", present=yara),
            ],
        ),
        EngineCapability(
            id="duplicate_detection",
            name="Duplicate and similarity search",
            status="not_integrated",
            detail="Exact SHA-256 exists. Perceptual hashing, embeddings, and Qdrant search are not implemented.",
        ),
        EngineCapability(
            id="provenance",
            name="Provenance verification",
            status="not_integrated",
            detail="C2PA and digital-signature verification are not implemented. Missing metadata is inconclusive.",
        ),
        EngineCapability(
            id="url_oembed",
            name="Public video URL metadata",
            status="ready",
            detail=(
                "YouTube, Vimeo, Dailymotion, TikTok, and Reddit public oEmbed plus thumbnail intake "
                "are implemented. Video bitstreams, DRM, and login-walled apps (Instagram/Facebook) "
                "are not fetched. This is not a deepfake detector."
            ),
        ),
        EngineCapability(
            id="url_reputation",
            name="URL reputation",
            status="ready",
            detail=(
                "Non-video URLs can be checked. With SAFE_BROWSING_API_KEY or VIRUSTOTAL_API_KEY a live "
                "reputation query runs. Without keys, only Google's published Safe Browsing test vectors "
                "are recognized. Other URLs stay unavailable rather than inventing a phishing label."
            ),
        ),
        EngineCapability(
            id="scam_investigation",
            name="Scam investigation",
            status="not_integrated",
            detail="Gemini is not called. The assistant cannot label a person a scammer from this build.",
        ),
        EngineCapability(
            id="fusion",
            name="Evidence fusion",
            status="not_integrated",
            detail="No calibrated fusion model is trained. Module findings will stay separate.",
        ),
    ]

    services = [
        ServiceCapability(
            id="authentication",
            name="Authentication",
            phase=2,
            state="implemented",
            detail="Email registration, password login, and session revocation are available. Google sign-in is not configured.",
        ),
        ServiceCapability(
            id="file_upload",
            name="File upload",
            phase=2,
            state="implemented",
            detail=(
                "Local upload, hashing, and signature checks are available. "
                "Public video URLs from YouTube, Vimeo, Dailymotion, TikTok, and Reddit use oEmbed "
                "plus thumbnail intake. Video bitstreams, DRM, and login walls are not bypassed. S3 is not connected."
            ),
        ),
        ServiceCapability(
            id="url_intake",
            name="Public URL intake",
            phase=2,
            state="implemented",
            detail=(
                "Supported providers: YouTube/Shorts, Vimeo, Dailymotion, TikTok, Reddit video posts. "
                "Instagram and Facebook stay unavailable because they require login. "
                "Streams behind DRM are not fetched."
            ),
        ),
        ServiceCapability(
            id="metadata_extraction",
            name="Metadata extraction",
            phase=2,
            state="implemented",
            detail=(
                "Container metadata is extracted without executing files. "
                "ffmpeg and MediaInfo are probed but not required for the current parsers."
            ),
        ),
        ServiceCapability(
            id="analysis_jobs",
            name="Analysis jobs",
            phase=2,
            state="implemented",
            detail=(
                "Uploads create queued jobs. ANALYSIS_MODE=inline runs in the API process; "
                "ANALYSIS_MODE=celery uses the worker. Detectors that are not integrated stay unavailable."
            ),
        ),
        ServiceCapability(
            id="video_processing",
            name="Video processing",
            phase=3,
            state="implemented" if video_ready else "foundation",
            detail=(
                "OpenCV frame sampling feeds image detectors. Temporal/lip-sync models are not integrated."
                if video_ready
                else "Frame sampling code exists; OpenCV and ML packages are required before it can run."
            ),
        ),
        ServiceCapability(
            id="audio_processing",
            name="Audio processing",
            phase=3,
            state="not_started",
            detail="No audio pipeline is registered.",
        ),
        ServiceCapability(
            id="image_processing",
            name="Image processing",
            phase=3,
            state="implemented" if image_ready else "foundation",
            detail=(
                "Uploaded images and URL thumbnails are passed to registered Hugging Face classifiers."
                if image_ready
                else "Image detector wrappers exist; ML packages must be installed before inference."
            ),
        ),
        ServiceCapability(
            id="document_processing",
            name="Document processing",
            phase=3,
            state="not_started",
            detail="No document pipeline is registered.",
        ),
        ServiceCapability(
            id="security_scanning",
            name="Security scanning",
            phase=4,
            state="not_started",
            detail="No malware scan task is registered.",
        ),
        ServiceCapability(
            id="ai_detection",
            name="AI detection",
            phase=3,
            state="implemented" if image_ready else "foundation",
            detail=(
                "AI-image and deepfake image models run when packages and weights load. "
                "A failed load returns unavailable. Confidences are not averaged."
                if image_ready
                else "Detector wrappers are registered. Install requirements-ml.txt to enable inference."
            ),
        ),
        ServiceCapability(
            id="investigation",
            name="Investigation orchestration",
            phase=5,
            state="not_started",
            detail="LangGraph agents are not implemented.",
        ),
        ServiceCapability(
            id="reporting",
            name="Report generation",
            phase=5,
            state="foundation",
            detail=(
                "Reports record integrity evidence and model predictions when detectors complete. "
                "Unavailable modules stay unavailable. PDF export is not implemented."
            ),
        ),
    ]

    return PlatformStatus(
        name=settings.app_name,
        version=settings.app_version,
        phase=3,
        max_upload_bytes=settings.max_upload_bytes,
        auth_configured=settings.auth_configured,
        storage_backend=settings.storage_backend,
        guarantees=GUARANTEES,
        services=services,
        engines=engines,
    )
