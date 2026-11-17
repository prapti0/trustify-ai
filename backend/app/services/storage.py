from pathlib import Path

from app.core.errors import InvalidStorageKey, StorageNotConfigured
from app.services.integrity import sha256_hex


class LocalObjectStorage:
    """Stores bytes on the local filesystem. Keys cannot escape the root."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def put(self, key: str, payload: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return sha256_hex(payload)

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def _path(self, key: str) -> Path:
        if not key or key.startswith(("/", "\\")) or "\\" in key or ".." in key.split("/"):
            raise InvalidStorageKey("invalid storage key")
        root = self.root.resolve()
        candidate = (root / key).resolve()
        if candidate != root and root not in candidate.parents:
            raise InvalidStorageKey("invalid storage key")
        return candidate


def assert_storage_available(backend: str) -> None:
    if backend == "local":
        return
    if backend == "s3":
        raise StorageNotConfigured(
            "S3 storage is not connected in this build. Use STORAGE_BACKEND=local for development."
        )
    raise StorageNotConfigured(f"Unknown storage backend: {backend}")
