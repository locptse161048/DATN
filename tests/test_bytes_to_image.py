"""
tests/test_bytes_to_image.py
-----------------------------
Unit tests cho src/preprocessing/bytes_to_image.py (task S2.2).

Chạy:
    pytest tests/test_bytes_to_image.py -v
"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.preprocessing.bytes_to_image import (
    DEFAULT_WIDTH,
    array_to_image,
    bytes_to_array,
    convert_file,
    parse_bytes_file,
    read_pe_bytes,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


def _make_fake_pe(n_bytes: int = 1024) -> bytes:
    """Tạo chuỗi bytes giả (không phải PE hợp lệ, chỉ để test đọc bytes)."""
    return bytes(range(256)) * (n_bytes // 256) + bytes(range(n_bytes % 256))


def _make_bytes_file(tmp_dir: Path, values: list[int]) -> Path:
    """Tạo file .bytes giả theo format IDA hex dump."""
    path = tmp_dir / "sample.bytes"
    lines = []
    addr = 0
    chunk = 16
    for i in range(0, len(values), chunk):
        row = values[i : i + chunk]
        tokens = " ".join(f"{v:02X}" for v in row)
        lines.append(f"{addr:08X} {tokens}")
        addr += chunk
    path.write_text("\n".join(lines), encoding="latin-1")
    return path


# ---------------------------------------------------------------------------
# bytes_to_array
# ---------------------------------------------------------------------------

class TestBytesToArray:
    def test_basic(self):
        raw = bytes([0, 128, 255])
        arr = bytes_to_array(raw)
        assert arr.dtype == np.uint8
        np.testing.assert_array_equal(arr, [0, 128, 255])

    def test_length(self):
        raw = bytes(1000)
        assert len(bytes_to_array(raw)) == 1000

    def test_empty(self):
        arr = bytes_to_array(b"")
        assert len(arr) == 0


# ---------------------------------------------------------------------------
# array_to_image — hành vi chính
# ---------------------------------------------------------------------------

class TestArrayToImage:
    def test_output_is_pil_grayscale(self):
        arr = np.arange(256, dtype=np.uint8)
        img = array_to_image(arr, width=DEFAULT_WIDTH)
        assert isinstance(img, Image.Image)
        assert img.mode == "L"

    def test_width_fixed(self):
        """Width ảnh phải đúng bằng tham số truyền vào."""
        for w in [64, 128, 256, 512]:
            arr = np.ones(w * 10, dtype=np.uint8)
            img = array_to_image(arr, width=w)
            assert img.width == w

    def test_height_ceil(self):
        """Height = ceil(n / width)."""
        width = 256
        for n in [1, 255, 256, 257, 1000, 65535]:
            arr = np.zeros(n, dtype=np.uint8)
            img = array_to_image(arr, width=width)
            expected_h = math.ceil(n / width)
            assert img.height == expected_h, f"n={n}: expected h={expected_h}, got {img.height}"

    def test_padding_only_last_row(self):
        """Pad 0 ở hàng cuối nếu lẻ; các hàng trước không bị thay đổi."""
        width = 16
        n = 30  # 2 hàng đầy (32 px) − 2 → row 1 đầy, row 2 thiếu 2
        arr = np.arange(n, dtype=np.uint8)
        img = array_to_image(arr, width=width)
        pixels = np.array(img)

        # Hàng 0: pixel 0..15 (đầy đủ)
        np.testing.assert_array_equal(pixels[0], arr[:width])
        # Hàng 1: pixel 16..29, rồi pad 0 ở vị trí 14 & 15
        np.testing.assert_array_equal(pixels[1, :n - width], arr[width:])
        np.testing.assert_array_equal(pixels[1, n - width:], np.zeros(width * 2 - n))

    def test_no_padding_when_divisible(self):
        """Khi n chia hết cho width, không cần padding."""
        width, height = 32, 8
        n = width * height
        arr = np.arange(n % 256, dtype=np.uint8)  # wrap-around OK
        arr = (np.arange(n) % 256).astype(np.uint8)
        img = array_to_image(arr, width=width)
        assert img.size == (width, height)
        np.testing.assert_array_equal(np.array(img).flatten(), arr)

    def test_single_byte(self):
        """File 1 byte: ảnh 1 pixel, pad đến 1 hàng đầy đủ."""
        arr = np.array([42], dtype=np.uint8)
        img = array_to_image(arr, width=DEFAULT_WIDTH)
        assert img.height == 1
        assert img.width == DEFAULT_WIDTH
        assert np.array(img)[0, 0] == 42
        assert np.array(img)[0, 1] == 0  # pixel pad

    def test_pixel_values_preserved(self):
        """Giá trị pixel phải khớp byte gốc (không chuẩn hóa, không scale)."""
        arr = np.array([0, 1, 127, 128, 254, 255], dtype=np.uint8)
        img = array_to_image(arr, width=DEFAULT_WIDTH)
        flat = np.array(img).flatten()
        np.testing.assert_array_equal(flat[:6], arr)

    def test_invalid_width(self):
        arr = np.ones(10, dtype=np.uint8)
        with pytest.raises(ValueError, match="width"):
            array_to_image(arr, width=0)

    def test_empty_array(self):
        arr = np.array([], dtype=np.uint8)
        with pytest.raises(ValueError):
            array_to_image(arr, width=DEFAULT_WIDTH)


# ---------------------------------------------------------------------------
# read_pe_bytes
# ---------------------------------------------------------------------------

class TestReadPeBytes:
    def test_reads_full_content(self, tmp_dir):
        data = _make_fake_pe(2048)
        path = tmp_dir / "sample.exe"
        path.write_bytes(data)
        arr = read_pe_bytes(path)
        assert arr.dtype == np.uint8
        assert len(arr) == 2048
        np.testing.assert_array_equal(arr, np.frombuffer(data, dtype=np.uint8))

    def test_empty_file_raises(self, tmp_dir):
        path = tmp_dir / "empty.exe"
        path.write_bytes(b"")
        with pytest.raises(ValueError, match="rỗng"):
            read_pe_bytes(path)

    def test_single_byte_file(self, tmp_dir):
        path = tmp_dir / "tiny.bin"
        path.write_bytes(b"\xff")
        arr = read_pe_bytes(path)
        assert len(arr) == 1
        assert arr[0] == 255

    def test_path_as_string(self, tmp_dir):
        data = _make_fake_pe(512)
        path = tmp_dir / "sample.dll"
        path.write_bytes(data)
        arr = read_pe_bytes(str(path))  # str thay vì Path
        assert len(arr) == 512


# ---------------------------------------------------------------------------
# parse_bytes_file (IDA hex dump legacy)
# ---------------------------------------------------------------------------

class TestParseBytesFile:
    def test_basic(self, tmp_dir):
        path = _make_bytes_file(tmp_dir, list(range(32)))
        arr = parse_bytes_file(path)
        assert arr.dtype == np.uint8
        np.testing.assert_array_equal(arr, list(range(32)))

    def test_question_marks_become_zero(self, tmp_dir):
        path = tmp_dir / "unk.bytes"
        path.write_text("00000000 ?? 01 ?? FF\n", encoding="latin-1")
        arr = parse_bytes_file(path)
        np.testing.assert_array_equal(arr, [0, 1, 0, 255])

    def test_multiline(self, tmp_dir):
        path = tmp_dir / "multi.bytes"
        path.write_text(
            "00000000 00 01 02 03 04 05 06 07\n"
            "00000008 08 09 0A 0B 0C 0D 0E 0F\n",
            encoding="latin-1",
        )
        arr = parse_bytes_file(path)
        np.testing.assert_array_equal(arr, list(range(16)))

    def test_empty_lines_ignored(self, tmp_dir):
        path = tmp_dir / "blank.bytes"
        path.write_text("\n00000000 AA BB\n\n", encoding="latin-1")
        arr = parse_bytes_file(path)
        np.testing.assert_array_equal(arr, [0xAA, 0xBB])


# ---------------------------------------------------------------------------
# convert_file — pipeline đầy đủ
# ---------------------------------------------------------------------------

class TestConvertFile:
    def test_pe_to_image(self, tmp_dir):
        data = _make_fake_pe(1024)
        src = tmp_dir / "sample.exe"
        src.write_bytes(data)
        img = convert_file(src, width=DEFAULT_WIDTH)
        assert isinstance(img, Image.Image)
        assert img.mode == "L"
        assert img.width == DEFAULT_WIDTH

    def test_saves_png(self, tmp_dir):
        data = _make_fake_pe(512)
        src = tmp_dir / "sample.exe"
        src.write_bytes(data)
        dst = tmp_dir / "out" / "sample.png"
        convert_file(src, output_path=dst, width=DEFAULT_WIDTH)
        assert dst.exists()
        saved = Image.open(dst)
        assert saved.mode == "L"

    def test_creates_output_dir(self, tmp_dir):
        data = _make_fake_pe(256)
        src = tmp_dir / "s.exe"
        src.write_bytes(data)
        dst = tmp_dir / "deep" / "nested" / "out.png"
        convert_file(src, output_path=dst, width=DEFAULT_WIDTH)
        assert dst.exists()

    def test_bytes_legacy_dispatch(self, tmp_dir):
        """File .bytes (IDA) phải được route sang parse_bytes_file."""
        path = _make_bytes_file(tmp_dir, list(range(64)))
        img = convert_file(path, width=DEFAULT_WIDTH)
        assert img.mode == "L"
        assert img.width == DEFAULT_WIDTH

    def test_pixel_count(self, tmp_dir):
        """Tổng pixel = width × ceil(n/width)."""
        n = 1000
        width = 256
        data = bytes(range(256)) * (n // 256) + bytes(range(n % 256))
        src = tmp_dir / "s.bin"
        src.write_bytes(data)
        img = convert_file(src, width=width)
        expected_total = width * math.ceil(n / width)
        assert img.width * img.height == expected_total

    def test_custom_width(self, tmp_dir):
        data = _make_fake_pe(2048)
        src = tmp_dir / "s.exe"
        src.write_bytes(data)
        for w in [64, 128, 512]:
            img = convert_file(src, width=w)
            assert img.width == w
