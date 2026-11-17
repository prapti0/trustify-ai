from app.services.metadata import extract_metadata


def test_png_dimensions():
    # Minimal IHDR after the 8-byte signature.
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + (32).to_bytes(4, "big")
        + (16).to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
    )
    result = extract_metadata(payload, "png", "png")
    assert result.width == 32
    assert result.height == 16
    assert result.container == "png"


def test_gif_dimensions():
    payload = b"GIF89a" + (10).to_bytes(2, "little") + (20).to_bytes(2, "little") + b"\x00\x00\x00"
    result = extract_metadata(payload, "gif", "gif")
    assert result.width == 10
    assert result.height == 20


def test_wav_duration():
    # 1 second of silence at 8000 Hz mono 16-bit = 16000 bytes of PCM.
    fmt = b"fmt " + (16).to_bytes(4, "little") + b"\x01\x00\x01\x00" + (8000).to_bytes(4, "little")
    fmt += (16000).to_bytes(4, "little") + b"\x02\x00\x10\x00"
    data = b"data" + (16000).to_bytes(4, "little") + (b"\x00" * 16000)
    payload = b"RIFF" + (36 + 16000).to_bytes(4, "little") + b"WAVE" + fmt + data
    result = extract_metadata(payload, "wav", "wav")
    assert result.duration_seconds == 1.0
    assert result.extra["sample_rate"] == 8000


def test_zip_lists_members_without_unpacking_to_disk(tmp_path):
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", "hello")
        archive.writestr("nested/info.json", "{}")
    payload = buffer.getvalue()
    result = extract_metadata(payload, "zip", "zip")
    assert result.extra["member_count"] == 2
    assert "readme.txt" in result.extra["member_names_sample"]
    assert any("not unpacked" in note for note in result.notes)


def test_missing_parser_is_inconclusive_not_synthetic():
    result = extract_metadata(b"\x00\x01\x02", "ebml", "mkv")
    assert result.width is None
    assert any("not proof" in note for note in result.notes)
