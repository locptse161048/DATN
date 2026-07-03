"""
collect_benign.py
-----------------
Gom file PE benign từ nhiều thư mục nguồn (Win10 System32, thư mục cài phần mềm,
portable apps...) vào data/raw/benign/<source_tag>/, lọc magic 'MZ', dedup SHA-256,
ghi metadata.

⚠️ CHỐNG THIÊN LỆCH NGUỒN: đừng chỉ lấy DLL hệ thống Win10. Hãy gom từ NHIỀU nguồn
(nhiều phần mềm, nhiều bản Windows, trình biên dịch khác nhau) — chạy script này
nhiều lần với --source-tag khác nhau.

Lấy file benign từ máy SẠCH (không nhiễm). Không trộn với thư mục malware.

Usage:
    # Lấy DLL hệ thống Win10
    python scripts/collect_benign.py --src "C:/Windows/System32" \
        --source-tag win10_system32 --max 2000

    # Lấy từ thư mục cài phần mềm
    python scripts/collect_benign.py --src "C:/Program Files" \
        --source-tag program_files --max 3000
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import shutil
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PE_EXTS = {".exe", ".dll", ".sys", ".ocx", ".cpl", ".scr"}
CHUNK = 1 << 20


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def is_pe(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"MZ"
    except OSError:
        return False


def collect(src: Path, out_dir: Path, source_tag: str, max_files: int,
            min_kb: int, max_mb: int) -> None:
    dst_dir = out_dir / source_tag
    dst_dir.mkdir(parents=True, exist_ok=True)
    meta_path = dst_dir / "metadata.csv"

    seen: set[str] = set()
    # nạp hash đã có (chạy lại nhiều lần không trùng)
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                seen.add(row["sha256"])

    n = 0
    write_header = not meta_path.exists()
    with open(meta_path, "a", newline="", encoding="utf-8") as mf:
        w = csv.DictWriter(mf, fieldnames=["sha256", "orig_path", "size", "source"])
        if write_header:
            w.writeheader()
        for p in src.rglob("*"):
            if n >= max_files:
                break
            if not p.is_file() or p.suffix.lower() not in PE_EXTS:
                continue
            try:
                size = p.stat().st_size
            except OSError:
                continue
            if size < min_kb * 1024 or size > max_mb * 1024 * 1024:
                continue
            if not is_pe(p):
                continue
            sha = sha256_of(p)
            if sha in seen:
                continue
            seen.add(sha)
            dst = dst_dir / f"{sha}{p.suffix.lower()}"
            try:
                shutil.copy2(p, dst)
            except OSError as e:
                logger.warning("Không copy được %s: %s", p, e)
                continue
            w.writerow({"sha256": sha, "orig_path": str(p),
                        "size": size, "source": source_tag})
            n += 1
            if n % 200 == 0:
                logger.info("Đã gom %d file benign...", n)
    logger.info("Hoàn thành: %d file benign (nguồn '%s') → %s", n, source_tag, dst_dir)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Gom PE benign từ thư mục nguồn (máy sạch).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--src", type=Path, required=True, help="Thư mục nguồn benign.")
    p.add_argument("--out", type=Path, default=Path("data/raw/benign"))
    p.add_argument("--source-tag", required=True,
                   help="Nhãn nguồn (vd win10_system32, program_files).")
    p.add_argument("--max", type=int, default=2000, dest="max_files")
    p.add_argument("--min-kb", type=int, default=4, help="Bỏ file < min-kb KB.")
    p.add_argument("--max-mb", type=int, default=64, help="Bỏ file > max-mb MB.")
    return p


def main() -> None:
    a = _build_parser().parse_args()
    if not a.src.exists():
        raise SystemExit(f"Không thấy thư mục nguồn: {a.src}")
    collect(a.src, a.out, a.source_tag, a.max_files, a.min_kb, a.max_mb)


if __name__ == "__main__":
    main()
