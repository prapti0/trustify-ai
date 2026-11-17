import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET"] = "test-signing-key-must-be-32-bytes"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_STORAGE_DIR"] = tempfile.mkdtemp(prefix="trustify-")
os.environ["ANALYSIS_MODE"] = "inline"
# Keep unit tests offline: packages may be installed without downloaded weights.
os.environ["ENABLE_ML_DETECTORS"] = "false"

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: E402, F401
from app.core.database import Base, get_engine
from app.main import app as fastapi_app


@pytest.fixture()
def client():
    engine = get_engine()
    Base.metadata.create_all(engine)
    with TestClient(fastapi_app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)
