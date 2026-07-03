"""
bytes_to_image.py
-----------------
Chuyển đổi file PE thô (.exe/.dll/.bin) sang ảnh xám (grayscale).
Đọc TOÀN BỘ bytes của file PE (giữ header) — KHÔNG phải hex dump defanged.

Quy ước (width CỐ ĐỊNH — KHÔNG dùng bảng Nataraj theo dung lượng file):
- Mỗi byte (0–255) = 1 pixel.
- Width là **một hằng số duy nhất** cho mọi mẫu (tham số `width`, mặc định
  DEFAULT_WIDTH=256, chốt giá trị cuối sau EDA). Width cố định → texture đồng nhất
  giữa các mẫu (không bị lệch scale như bảng Nataraj).
- Height = ceil(n_bytes / width); chỉ pad 0 ở hàng cuối nếu lẻ (< width byte).
- Ảnh lưu ở kích thước native (không resize ở bước này).

An toàn: chạy trong VM cô lập, CHỈ đọc bytes — không thực thi mẫu.
Thiết kế streaming: đọc từng file một, không load toàn bộ dataset vào RAM.

(Tùy chọn) hỗ trợ đọc file hex dump `.bytes` kiểu IDA qua `parse_bytes_file`
cho dữ liệu legacy; mặc định pipeline đọc PE thô.

Usage (CLI):
    python src/preprocessing/bytes_to_image.py \\
        --input  data/raw/malware \\
        --output data/processed/gray \\
        --width 256 \\
        --workers 2

Usage (API):
    from src.preprocessing.bytes_to_image import convert_file
    img = convert_file("path/to/sample.exe", width=256)  # -> PIL.Image ('L')
"""

from __future__ import annotations

import argparse
import logging
import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Width CỐ ĐỊNH (một hằng số cho mọi mẫu) — KHÔNG dùng bảng theo dung lượng file.
# Giá trị mặc định; chốt lại sau EDA BIG2015 và truyền qua config/CLI.
# ---------------------------------------------------------------------------
DEFAULT_WIDTH: int = 448


# ---------------------------------------------------------------------------
# Core conversion
# ---------------------------------------------------------------------------

def bytes_to_array(raw: bytes) -> np.ndarray:
    """Chuyển raw bytes sang mảng uint8 1-D (giá trị 0–255)."""
    return np.frombuffer(raw, dtype=np.uint8)


class FileTooSmall(ValueError):
    """File nhỏ hơn min_bytes → bỏ qua (ảnh sẽ vô nghĩa)."""


def read_pe_bytes(path: str | Path, max_bytes: Optional[int] = None) -> np.ndarray:
    """
    Đọc bytes của file PE thô (.exe/.dll/.bin) → mảng uint8 1-D, giữ header.
    Nếu `max_bytes` đặt: chỉ đọc PHẦN ĐẦU tối đa max_bytes (cắt file khổng lồ
    để tránh ảnh quá lớn — phần đầu chứa header + entry point, vùng phân biệt nhất).
    KHÔNG thực thi file (chỉ đọc nhị phân).
    """
    with open(path, "rb") as f:
        raw = f.read(max_bytes) if max_bytes else f.read()
    if not raw:
        raise ValueError(f"File rỗng: {path}")
    return np.frombuffer(raw, dtype=np.uint8)


def read_input(path: str | Path, max_bytes: Optional[int] = None) -> np.ndarray:
    """Dispatcher: đuôi `.bytes` → hex dump legacy; còn lại → PE thô."""
    path = Path(path)
    if path.suffix.lower() == ".bytes":
        return parse_bytes_file(path)
    return read_pe_bytes(path, max_bytes=max_bytes)


def parse_bytes_file(path: str | Path) -> np.ndarray:
    """
    Đọc file .bytes của BIG2015 (IDA Pro hex dump).

    Format mỗi dòng:
        <địa chỉ hex>  <byte1> <byte2> ... (mỗi byte là 2 ký tự hex hoặc '??')

    '??' → 0 (byte không xác định).
    Trả về mảng uint8 1-D.
    """
    values: list[int] = []
    with open(path, "r", encoding="latin-1") as f:
        for line in f:
            parts = line.split()
            if not parts:
                continue
            # Bỏ cột địa chỉ đầu tiên
            for token in parts[1:]:
                if token == "??":
                    values.append(0)
                else:
                    try:
                        values.append(int(token, 16))
                    except ValueError:
                        values.append(0)
    return np.array(values, dtype=np.uint8)


def array_to_image(pixel_array: np.ndarray, width: int = DEFAULT_WIDTH) -> Image.Image:
    """
    Chuyển mảng uint8 1-D sang ảnh xám PIL.

    - Width CỐ ĐỊNH (tham số `width`, không phụ thuộc dung lượng file).
    - Height = ceil(n / width).
    - Chỉ pad 0 ở hàng cuối nếu lẻ (< width byte).
    """
    n = len(pixel_array)
    if n == 0:
        raise ValueError("Mảng pixel rỗng, không thể tạo ảnh.")
    if width <= 0:
        raise ValueError(f"width phải > 0, nhận {width}.")

    height = math.ceil(n / width)
    total = width * height

    # Padding
    if n < total:
        pixel_array = np.pad(pixel_array, (0, total - n), constant_values=0)

    img_array = pixel_array.reshape(height, width)
    return Image.fromarray(img_array, mode="L")


def convert_file(
    input_path: str | Path,
    output_path: Optional[str | Path] = None,
    width: int = DEFAULT_WIDTH,
    min_bytes: int = 0,
    max_bytes: Optional[int] = None,
) -> Image.Image:
    """
    Pipeline đầy đủ: đọc file (PE thô hoặc .bytes legacy) → ảnh xám PIL.

    Args:
        input_path:  Đường dẫn tới file PE (.exe/.dll/.bin) hoặc .bytes.
        output_path: (Tùy chọn) Nếu cung cấp, lưu ảnh PNG ra đường dẫn này.
        width:       Width cố định (pixels) cho mọi mẫu.
        min_bytes:   Bỏ file nhỏ hơn ngưỡng này (raise FileTooSmall).
        max_bytes:   Chỉ đọc phần đầu tối đa max_bytes (cắt file khổng lồ).

    Returns:
        PIL.Image ở mode 'L' (grayscale).
    """
    input_path = Path(input_path)
    pixel_array = read_input(input_path, max_bytes=max_bytes)
    if len(pixel_array) < min_bytes:
        raise FileTooSmall(f"{input_path} ({len(pixel_array)} byte < {min_bytes})")
    img = array_to_image(pixel_array, width=width)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, format="PNG")

    return img


# Alias tương thích ngược
convert_bytes_file = convert_file


# ---------------------------------------------------------------------------
# Batch conversion (dùng cho CLI)
# ---------------------------------------------------------------------------

def _worker(args: tuple[Path, Path, int]) -> tuple[str, bool, str]:
    """Worker function cho ProcessPoolExecutor."""
    src, dst, width = args
    try:
        convert_bytes_file(src, dst, width=width)
        return str(src.name), True, ""
    except Exception as e:
        return str(src.name), False, str(e)


def batch_convert(
    input_dir: str | Path,
    output_dir: str | Path,
    workers: int = 1,
    overwrite: bool = False,
    width: int = DEFAULT_WIDTH,
) -> dict[str, int]:
    """
    Chuyển đổi toàn bộ file PE (và .bytes legacy) trong input_dir sang ảnh PNG.

    Cấu trúc thư mục đầu vào được bảo toàn:
        input_dir/<label_or_family>/<hash>.exe  →  output_dir/<...>/<hash>.png

    Args:
        input_dir:  Thư mục gốc chứa file PE (có thể phân cấp).
        output_dir: Thư mục đầu ra cho ảnh PNG.
        workers:    Số process song song (mặc định 1 để tiết kiệm RAM).
        overwrite:  Nếu False, bỏ qua file đã tồn tại.

    Returns:
        Dict {"success": int, "skip": int, "error": int}
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Thu thập file PE thô + .bytes legacy
    exts = ("*.exe", "*.dll", "*.bin", "*.bytes")
    all_files: list[Path] = []
    for pat in exts:
        all_files.extend(input_dir.rglob(pat))
    if not all_files:
        logger.warning("Không tìm thấy file PE/.bytes trong: %s", input_dir)
        return {"success": 0, "skip": 0, "error": 0}

    logger.info("Tìm thấy %d file đầu vào", len(all_files))

    tasks: list[tuple[Path, Path, int]] = []
    skipped = 0
    for src in all_files:
        relative = src.relative_to(input_dir)
        dst = output_dir / relative.with_suffix(".png")
        if not overwrite and dst.exists():
            skipped += 1
            continue
        tasks.append((src, dst, width))

    logger.info("Cần xử lý: %d | Bỏ qua (đã có): %d", len(tasks), skipped)

    success, errors = 0, 0

    if workers <= 1:
        for t in tasks:
            name, ok, err = _worker(t)
            if ok:
                success += 1
                if success % 100 == 0:
                    logger.info("Đã xử lý %d/%d", success, len(tasks))
            else:
                errors += 1
                logger.error("Lỗi [%s]: %s", name, err)
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_worker, t): t for t in tasks}
            done = 0
            for future in as_completed(futures):
                name, ok, err = future.result()
                done += 1
                if ok:
                    success += 1
                    if done % 100 == 0:
                        logger.info("Tiến độ: %d/%d", done, len(tasks))
                else:
                    errors += 1
                    logger.error("Lỗi [%s]: %s", name, err)

    logger.info(
        "Hoàn thành — Thành công: %d | Bỏ qua: %d | Lỗi: %d",
        success, skipped, errors,
    )
    return {"success": success, "skip": skipped, "error": errors}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Chuyển đổi file .bytes (BIG2015) sang ảnh xám PNG.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--input", "-i", required=True,
        help="Thư mục chứa file .bytes (phân cấp theo family).",
    )
    p.add_argument(
        "--output", "-o", required=True,
        help="Thư mục đầu ra cho ảnh PNG.",
    )
    p.add_argument(
        "--width", type=int, default=DEFAULT_WIDTH,
        help="Width cố định (pixels) cho mọi ảnh. Chốt sau EDA BIG2015.",
    )
    p.add_argument(
        "--workers", "-w", type=int, default=1,
        help="Số process song song. Khuyên dùng 1–2 trên VM 2 GB RAM.",
    )
    p.add_argument(
        "--overwrite", action="store_true",
        help="Ghi đè ảnh đã tồn tại.",
    )
    return p


def main() -> None:
    args = _build_parser().parse_args()
    batch_convert(
        input_dir=args.input,
        output_dir=args.output,
        workers=args.workers,
        overwrite=args.overwrite,
        width=args.width,
    )


if __name__ == "__main__":
    main()
