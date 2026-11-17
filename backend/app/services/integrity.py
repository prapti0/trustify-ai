import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class SignatureMatch:
    format_id: str
    mime_hint: str
    method: str = "magic-bytes"


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def identify_signature(payload: bytes) -> SignatureMatch | None:
    """Identify a file family from header bytes.

    ZIP-based Office files are distinguished only when their internal names
    appear in the provided bytes. This does not unpack or execute the file.
    """
    if payload.startswith(b"%PDF-"):
        return SignatureMatch("pdf", "application/pdf")
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return SignatureMatch("png", "image/png")
    if payload.startswith(b"\xff\xd8\xff"):
        return SignatureMatch("jpeg", "image/jpeg")
    if payload.startswith(b"GIF87a") or payload.startswith(b"GIF89a"):
        return SignatureMatch("gif", "image/gif")
    if payload.startswith(b"ID3") or (
        len(payload) > 1 and payload[0] == 0xFF and payload[1] & 0xE0 == 0xE0
    ):
        return SignatureMatch("mp3", "audio/mpeg")
    if payload.startswith(b"fLaC"):
        return SignatureMatch("flac", "audio/flac")
    if payload.startswith(b"RIFF") and len(payload) >= 12:
        kind = payload[8:12]
        if kind == b"WAVE":
            return SignatureMatch("wav", "audio/wav")
        if kind == b"AVI ":
            return SignatureMatch("avi", "video/x-msvideo")
        if kind == b"WEBP":
            return SignatureMatch("webp", "image/webp")
    if payload.startswith(b"\x1a\x45\xdf\xa3"):
        return SignatureMatch("ebml", "video/webm")
    if payload.startswith(b"\x1f\x8b"):
        return SignatureMatch("gzip", "application/gzip")
    if payload.startswith(b"7z\xbc\xaf'\x1c"):
        return SignatureMatch("7z", "application/x-7z-compressed")
    if len(payload) >= 262 and payload[257:262] == b"ustar":
        return SignatureMatch("tar", "application/x-tar")
    if len(payload) >= 12 and payload[4:8] == b"ftyp":
        return SignatureMatch("iso_bmff", "video/mp4")
    if payload.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return SignatureMatch("ole_compound", "application/x-ole-storage")
    if payload.startswith(b"PK\x03\x04"):
        if b"word/" in payload:
            return SignatureMatch("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        if b"xl/" in payload:
            return SignatureMatch("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        return SignatureMatch("zip", "application/zip")
    return None
