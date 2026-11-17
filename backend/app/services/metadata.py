"""Pure-Python container metadata. Files are never executed."""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field


@dataclass
class ExtractedMetadata:
    container: str | None = None
    codec: str | None = None
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    exif: dict | None = None
    extra: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def extract_metadata(payload: bytes, format_id: str, extension: str) -> ExtractedMetadata:
    result = ExtractedMetadata()
    if format_id == "png" or extension == "png":
        _png(payload, result)
    elif format_id == "jpeg" or extension in {"jpg", "jpeg"}:
        _jpeg(payload, result)
    elif format_id == "gif" or extension == "gif":
        _gif(payload, result)
    elif format_id == "webp" or extension == "webp":
        _webp(payload, result)
    elif format_id == "wav" or extension == "wav":
        _wav(payload, result)
    elif format_id == "flac" or extension == "flac":
        _flac(payload, result)
    elif format_id == "pdf" or extension == "pdf":
        _pdf(payload, result)
    elif format_id == "iso_bmff" or extension in {"mp4", "mov"}:
        _iso_bmff(payload, result)
    elif format_id in {"zip", "docx", "xlsx"} or extension in {"zip", "docx", "xlsx"}:
        _zip_members(payload, result, format_id or extension)
    elif extension in {"txt", "csv", "json", "xml"}:
        _text(payload, result, extension)
    else:
        result.notes.append(
            f"No container parser is registered for format '{format_id or extension}'. "
            "Missing metadata is not proof that the content is synthetic."
        )
    if not result.notes and result.width is None and result.duration_seconds is None and not result.extra:
        result.notes.append(
            "Header parsing did not yield dimensions or duration. "
            "Missing metadata is not proof that the content is synthetic."
        )
    return result


def _png(payload: bytes, result: ExtractedMetadata) -> None:
    result.container = "png"
    if len(payload) < 24 or payload[12:16] != b"IHDR":
        result.notes.append("PNG IHDR chunk was not found at the expected offset.")
        return
    result.width = int.from_bytes(payload[16:20], "big")
    result.height = int.from_bytes(payload[20:24], "big")
    result.extra["bit_depth"] = payload[24]
    result.extra["color_type"] = payload[25]


def _gif(payload: bytes, result: ExtractedMetadata) -> None:
    result.container = "gif"
    if len(payload) < 10:
        result.notes.append("GIF header is too short to read dimensions.")
        return
    result.width = int.from_bytes(payload[6:8], "little")
    result.height = int.from_bytes(payload[8:10], "little")
    result.extra["version"] = payload[3:6].decode("ascii", errors="replace")


def _jpeg(payload: bytes, result: ExtractedMetadata) -> None:
    result.container = "jpeg"
    index = 2
    while index + 9 < len(payload):
        if payload[index] != 0xFF:
            break
        marker = payload[index + 1]
        if marker in {0xC0, 0xC1, 0xC2}:
            result.height = int.from_bytes(payload[index + 5 : index + 7], "big")
            result.width = int.from_bytes(payload[index + 7 : index + 9], "big")
            result.extra["sof_marker"] = f"0xFF{marker:02X}"
            return
        if marker == 0xD8 or marker == 0x01 or marker == 0xFF:
            index += 1
            continue
        if marker in {0xD9, 0xDA}:
            break
        if index + 4 > len(payload):
            break
        length = int.from_bytes(payload[index + 2 : index + 4], "big")
        if length < 2:
            break
        index += 2 + length
    result.notes.append("JPEG start-of-frame marker was not located. Dimensions were not recorded.")


def _webp(payload: bytes, result: ExtractedMetadata) -> None:
    result.container = "webp"
    if len(payload) < 30 or payload[8:12] != b"WEBP":
        result.notes.append("WEBP chunk header was not recognized.")
        return
    kind = payload[12:16]
    result.codec = kind.decode("ascii", errors="replace")
    if kind == b"VP8 " and len(payload) >= 30:
        result.width = int.from_bytes(payload[26:28], "little") & 0x3FFF
        result.height = int.from_bytes(payload[28:30], "little") & 0x3FFF
    elif kind == b"VP8L" and len(payload) >= 25:
        bits = int.from_bytes(payload[21:25], "little")
        result.width = (bits & 0x3FFF) + 1
        result.height = ((bits >> 14) & 0x3FFF) + 1
    elif kind == b"VP8X" and len(payload) >= 30:
        result.width = 1 + int.from_bytes(payload[24:27], "little")
        result.height = 1 + int.from_bytes(payload[27:30], "little")
    else:
        result.notes.append("WEBP dimensions were not parsed for this chunk type.")


def _wav(payload: bytes, result: ExtractedMetadata) -> None:
    result.container = "wav"
    if len(payload) < 44 or payload[8:12] != b"WAVE":
        result.notes.append("WAVE header was not recognized.")
        return
    offset = 12
    sample_rate = None
    channels = None
    bits = None
    data_size = None
    while offset + 8 <= len(payload):
        chunk_id = payload[offset : offset + 4]
        chunk_size = int.from_bytes(payload[offset + 4 : offset + 8], "little")
        data_start = offset + 8
        data_end = data_start + chunk_size
        if chunk_id == b"fmt " and chunk_size >= 16 and data_end <= len(payload):
            channels = int.from_bytes(payload[data_start + 2 : data_start + 4], "little")
            sample_rate = int.from_bytes(payload[data_start + 4 : data_start + 8], "little")
            bits = int.from_bytes(payload[data_start + 14 : data_start + 16], "little")
            result.codec = f"pcm_{bits}bit" if bits else "pcm"
        elif chunk_id == b"data":
            data_size = chunk_size
        offset = data_end + (chunk_size % 2)
        if offset <= data_start:
            break
    if channels is not None:
        result.extra["channels"] = channels
    if sample_rate is not None:
        result.extra["sample_rate"] = sample_rate
    if bits is not None:
        result.extra["bits_per_sample"] = bits
    if sample_rate and channels and bits and data_size is not None and bits > 0:
        bytes_per_second = sample_rate * channels * (bits // 8)
        if bytes_per_second > 0:
            result.duration_seconds = round(data_size / bytes_per_second, 3)


def _flac(payload: bytes, result: ExtractedMetadata) -> None:
    result.container = "flac"
    if len(payload) < 42 or payload[0:4] != b"fLaC":
        result.notes.append("FLAC STREAMINFO was not found.")
        return
    # STREAMINFO block follows the 4-byte marker: 1 byte header + 34 bytes
    if payload[4] & 0x7F != 0:
        result.notes.append("First FLAC metadata block is not STREAMINFO.")
        return
    block = payload[8:42]
    sample_rate = (block[10] << 12) | (block[11] << 4) | ((block[12] & 0xF0) >> 4)
    channels = ((block[12] & 0x0E) >> 1) + 1
    total_samples = ((block[13] & 0x0F) << 32) | int.from_bytes(block[14:18], "big")
    result.extra["sample_rate"] = sample_rate
    result.extra["channels"] = channels
    result.codec = "flac"
    if sample_rate > 0 and total_samples > 0:
        result.duration_seconds = round(total_samples / sample_rate, 3)


def _pdf(payload: bytes, result: ExtractedMetadata) -> None:
    result.container = "pdf"
    if not payload.startswith(b"%PDF-"):
        result.notes.append("PDF header marker was missing.")
        return
    version = payload[5:8].decode("ascii", errors="replace")
    result.extra["pdf_version"] = version
    # Count page objects loosely. /Type /Pages is the tree node, not a page.
    page_hits = len(re.findall(rb"/Type\s*/Page(?![s\w])", payload))
    result.extra["page_object_count"] = page_hits
    result.notes.append(
        "PDF page_object_count is a heuristic from object markers. It is not a rendered page proof."
    )
    for label, pattern in (
        ("producer", rb"/Producer\s*\((?:\\.|[^\\)]){0,200}\)"),
        ("creator", rb"/Creator\s*\((?:\\.|[^\\)]){0,200}\)"),
    ):
        match = re.search(pattern, payload)
        if match:
            raw = match.group(0).split(b"(", 1)[1].rsplit(b")", 1)[0]
            text = raw.decode("latin-1", errors="replace").replace("\\(", "(").replace("\\)", ")")
            result.extra[label] = text[:180]


def _iso_bmff(payload: bytes, result: ExtractedMetadata) -> None:
    result.container = "iso_bmff"
    offset = 0
    found_ftyp = False
    while offset + 8 <= len(payload) and offset < min(len(payload), 2_000_000):
        size = int.from_bytes(payload[offset : offset + 4], "big")
        box_type = payload[offset + 4 : offset + 8]
        header = 8
        if size == 1 and offset + 16 <= len(payload):
            size = int.from_bytes(payload[offset + 8 : offset + 16], "big")
            header = 16
        elif size == 0:
            size = len(payload) - offset
        if size < header:
            break
        end = offset + size
        if end > len(payload):
            break
        body = payload[offset + header : end]
        if box_type == b"ftyp" and len(body) >= 4:
            found_ftyp = True
            brand = body[0:4].decode("ascii", errors="replace")
            result.extra["major_brand"] = brand
            result.codec = brand
        elif box_type == b"moov":
            _scan_moov(body, result)
        offset = end
    if not found_ftyp:
        result.notes.append("ISO BMFF ftyp box was not found in the scanned prefix.")


def _scan_moov(body: bytes, result: ExtractedMetadata) -> None:
    offset = 0
    while offset + 8 <= len(body):
        size = int.from_bytes(body[offset : offset + 4], "big")
        box_type = body[offset + 4 : offset + 8]
        header = 8
        if size == 1 and offset + 16 <= len(body):
            size = int.from_bytes(body[offset + 8 : offset + 16], "big")
            header = 16
        elif size == 0:
            size = len(body) - offset
        if size < header:
            break
        end = offset + size
        if end > len(body):
            break
        content = body[offset + header : end]
        if box_type == b"mvhd" and len(content) >= 20:
            version = content[0]
            if version == 0 and len(content) >= 20:
                timescale = int.from_bytes(content[12:16], "big")
                duration = int.from_bytes(content[16:20], "big")
            elif version == 1 and len(content) >= 32:
                timescale = int.from_bytes(content[20:24], "big")
                duration = int.from_bytes(content[24:32], "big")
            else:
                timescale = 0
                duration = 0
            if timescale > 0 and duration > 0:
                result.duration_seconds = round(duration / timescale, 3)
                result.extra["timescale"] = timescale
        elif box_type == b"trak":
            _scan_trak(content, result)
        offset = end


def _scan_trak(body: bytes, result: ExtractedMetadata) -> None:
    offset = 0
    while offset + 8 <= len(body):
        size = int.from_bytes(body[offset : offset + 4], "big")
        box_type = body[offset + 4 : offset + 8]
        if size < 8 or offset + size > len(body):
            break
        content = body[offset + 8 : offset + size]
        if box_type == b"tkhd" and result.width is None and len(content) >= 84:
            version = content[0]
            # width/height are 16.16 fixed point near the end of tkhd
            if version == 0 and len(content) >= 84:
                result.width = int.from_bytes(content[76:80], "big") >> 16
                result.height = int.from_bytes(content[80:84], "big") >> 16
            elif version == 1 and len(content) >= 96:
                result.width = int.from_bytes(content[88:92], "big") >> 16
                result.height = int.from_bytes(content[92:96], "big") >> 16
        offset += size


def _zip_members(payload: bytes, result: ExtractedMetadata, format_id: str) -> None:
    result.container = format_id
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile:
        result.notes.append("ZIP central directory could not be read. The archive was not unpacked.")
        return
    result.extra["member_count"] = len(names)
    result.extra["member_names_sample"] = names[:40]
    result.notes.append(
        "Archive member names were listed from the ZIP directory. Contents were not unpacked or executed."
    )


def _text(payload: bytes, result: ExtractedMetadata, extension: str) -> None:
    result.container = extension
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        result.notes.append("Text could not be decoded as UTF-8 for metadata counting.")
        return
    result.extra["encoding"] = "utf-8"
    result.extra["byte_length"] = len(payload)
    result.extra["character_count"] = len(text)
    result.extra["line_count"] = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
    if extension == "json":
        result.extra["json_root_type"] = "parsed_elsewhere"
    result.notes.append("Text metadata counts characters and lines only. Content was not executed.")
