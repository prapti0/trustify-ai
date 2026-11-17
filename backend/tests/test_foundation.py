from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.database import Base, get_engine, get_session_factory
from app.core.errors import InvalidStorageKey, StorageNotConfigured
from app.core.passwords import hash_password, verify_password
from app.domain.enums import DetectionStatus, FileSource, JobStatus
from app.models import AnalysisJob, DetectionResult, InvestigationReport, UploadedFile, User
from app.services.integrity import identify_signature, sha256_hex
from app.services.storage import LocalObjectStorage, assert_storage_available

EXPECTED_TABLES = {
    "users",
    "user_sessions",
    "uploaded_files",
    "file_metadata",
    "analysis_jobs",
    "detection_results",
    "forensic_evidence",
    "security_scan_results",
    "duplicate_matches",
    "investigation_reports",
    "model_versions",
    "api_keys",
    "audit_logs",
}


@pytest.fixture()
def session():
    engine = get_engine()
    Base.metadata.create_all(engine)
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_schema_covers_the_domain():
    assert set(Base.metadata.tables) == EXPECTED_TABLES
    report_columns = {column.name for column in InvestigationReport.__table__.columns}
    assert "authenticity_score" not in report_columns
    assert "ai_generation" in report_columns
    assert "scam" in report_columns


def test_migration_names_every_table():
    migration = Path("alembic/versions/0001_initial.py").read_text()
    for table in EXPECTED_TABLES:
        assert f'"{table}"' in migration


def test_unavailable_result_cannot_store_a_score(session):
    user, job = _user_and_job(session)
    session.add(user)
    session.add(job)
    session.flush()
    session.add(
        DetectionResult(
            job_id=job.id,
            module="image_forensics",
            status=DetectionStatus.UNAVAILABLE,
            confidence=0.82,
            limitations="model not integrated",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_completed_confidence_must_be_a_fraction(session):
    user, job = _user_and_job(session)
    session.add(user)
    session.add(job)
    session.flush()
    session.add(
        DetectionResult(
            job_id=job.id,
            module="image_forensics",
            status=DetectionStatus.COMPLETED,
            confidence=1.4,
            limitations="out of range",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_signature_and_hash():
    assert identify_signature(b"%PDF-1.7\n").format_id == "pdf"
    assert identify_signature(b"\x89PNG\r\n\x1a\nrest").format_id == "png"
    assert identify_signature(b"PK\x03\x04word/document.xml").format_id == "docx"
    assert identify_signature(b"PK\x03\x04random").format_id == "zip"
    assert identify_signature(b"not a known header") is None
    payload = b"trustify-ai"
    assert sha256_hex(payload) == __import__("hashlib").sha256(payload).hexdigest()
    assert sha256_hex(payload) != sha256_hex(payload + b"x")


def test_local_storage_round_trip_and_rejects_escape(tmp_path):
    storage = LocalObjectStorage(tmp_path)
    digest = storage.put("users/a/file.bin", b"evidence")
    assert storage.read("users/a/file.bin") == b"evidence"
    assert digest == sha256_hex(b"evidence")
    storage.delete("users/a/file.bin")
    with pytest.raises(FileNotFoundError):
        storage.read("users/a/file.bin")
    with pytest.raises(InvalidStorageKey):
        storage.put("../secrets.txt", b"nope")


def test_s3_is_not_pretended():
    with pytest.raises(StorageNotConfigured):
        assert_storage_available("s3")


def test_password_hash_round_trip():
    encoded = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", encoded)
    assert not verify_password("wrong-horse-battery", encoded)
    assert not verify_password("correct-horse-battery", "garbage")
    with pytest.raises(ValueError):
        hash_password("short")


def _user_and_job(session):
    user = User(email="analyst@example.com", password_hash="stored-later")
    session.add(user)
    session.flush()
    uploaded = UploadedFile(
        user_id=user.id,
        original_filename="clip.mp4",
        stored_key="users/a/clip.mp4",
        size_bytes=12,
        sha256="a" * 64,
        source=FileSource.UPLOAD,
    )
    session.add(uploaded)
    session.flush()
    job = AnalysisJob(file_id=uploaded.id, user_id=user.id, status=JobStatus.UPLOADED)
    return user, job
