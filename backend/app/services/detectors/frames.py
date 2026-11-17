"""Sample video frames without executing media as code."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_jpeg_frames(payload: bytes, *, max_frames: int = 8) -> tuple[list[bytes], str | None]:
    """Return JPEG frame bytes sampled across the video, or an error reason."""
    try:
        import cv2  # type: ignore
    except Exception as exc:  # pragma: no cover
        return [], f"OpenCV is not installed ({exc.__class__.__name__})."

    suffix = ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(payload)
        path = Path(handle.name)
    try:
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            return [], "OpenCV could not open the video container."
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total <= 0:
            # Fall back to reading sequentially.
            frames: list[bytes] = []
            while len(frames) < max_frames:
                ok, frame = capture.read()
                if not ok:
                    break
                encoded = _encode_jpeg(cv2, frame)
                if encoded:
                    frames.append(encoded)
            capture.release()
            if not frames:
                return [], "No frames could be decoded from the video."
            return frames, None

        indexes = _sample_indexes(total, max_frames)
        frames = []
        for index in indexes:
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            if not ok:
                continue
            encoded = _encode_jpeg(cv2, frame)
            if encoded:
                frames.append(encoded)
        capture.release()
        if not frames:
            return [], "Frame sampling produced no decodable frames."
        return frames, None
    except Exception as exc:
        logger.info("frame_extract_failed err=%s", exc.__class__.__name__)
        return [], f"Frame extraction failed ({exc.__class__.__name__})."
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _sample_indexes(total: int, max_frames: int) -> list[int]:
    if total <= max_frames:
        return list(range(total))
    if max_frames == 1:
        return [total // 2]
    step = (total - 1) / (max_frames - 1)
    return sorted({min(total - 1, int(round(index * step))) for index in range(max_frames)})


def _encode_jpeg(cv2, frame) -> bytes | None:
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        return None
    return buffer.tobytes()
