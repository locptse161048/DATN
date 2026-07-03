"""
labeling.py
-----------
Dedup theo SHA-256 + gán nhãn benign/malware + (tùy chọn) chuẩn hóa tên họ bằng
AVClass2, rồi xuất bảng nhãn thống nhất `labels.csv`.

Quy ước thư mục đầu vào (xem docs/DATA_COLLECTION.md):
    data/raw/malware/<source>/<family?>/<file>     -> label = malware
    data/raw/benign/<source>/<file>                -> label = benign

Mỗi nguồn nên kèm 1 file metadata CSV (do script thu thập sinh ra) có tối thiểu:
    path, sha256, source, family (nếu biết), first_seen (nếu có)
Nếu không có, module này tự quét file PE và tự tính SHA-256.

An toàn: CHỈ đọc bytes (tính hash, kiểm tra magic 'MZ'); KHÔNG thực thi file.
Chạy trong VM cô lập.

Output: data/interim/labels.csv với các cột:
    path, sha256, label (0=benign,1=malware), family, source, first_seen, size
Đã dedup (mỗi sha256 xuất hiện 1 lần; ưu tiên giữ bản có nhiều metadata hơn).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
from pathlib import Path
from typing import Iterable, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PE_EXTS = {".exe", ".dll", ".bin", ".sys", ".scr", ".ocx", ".cpl"}
CHUNK = 1 << 20  # 1 MB


# ---------------------------------------------------------------------------
# Hash & kiểm tra PE
# ---------------------------------------------------------------------------

def sha256_of(path: Path) -> str:
    """SHA-256 của file (đọc streaming, không nạp cả file vào RAM)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def is_pe(path: Path) -> bool:
    """Kiểm tra nhanh magic 'MZ' đầu file (lọc file không phải PE)."""
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"MZ"
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Quét file
# ---------------------------------------------------------------------------

def iter_pe_files(root: Path, require_mz: bool = True) -> Iterable[Path]:
    """Duyệt đệ quy, trả về các file PE hợp lệ."""
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in PE_EXTS:
            continue
        if require_mz and not is_pe(p):
            logger.debug("Bỏ qua (không phải PE/MZ): %s", p)
            continue
        yield p


def _infer_family(path: Path, root: Path) -> str:
    """Suy họ từ tên thư mục con đầu tiên dưới <source> (RAT/bazaar)."""
    try:
        rel = path.relative_to(root)
        parts = rel.parts
        # parts[0] = source, parts[1] = family (nếu có phân cấp)
        if len(parts) >= 3:
            return parts[1]
    except ValueError:
        pass
    return ""


def _source_of(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).parts[0]
    except (ValueError, IndexError):
        return root.name


# ---------------------------------------------------------------------------
# Xây bảng nhãn
# ---------------------------------------------------------------------------

def build_label_rows(
    malware_dir: Optional[Path],
    benign_dir: Optional[Path],
    require_mz: bool = True,
) -> list[dict]:
    """
    Quét malware_dir và benign_dir → list bản ghi đã DEDUP theo sha256.
    Khi trùng hash: ưu tiên bản có 'family' (nhiều metadata hơn).
    """
    rows: dict[str, dict] = {}  # sha256 -> row
    dup = 0

    def add(path: Path, label: int, root: Path):
        nonlocal dup
        sha = sha256_of(path)
        source = _source_of(path, root)
        family = _infer_family(path, root) if label == 1 else ""
        # Quyết định 2026-06-28: RAT là MỘT NHÓM để phân biệt với các họ khác
        # → gộp mọi họ RAT con (XWorm, NjRat, LiberiumRat...) thành 1 nhãn 'RAT'
        # cho nhánh phân loại họ (không phân loại sub-family RAT).
        if source.lower() == "rat":
            family = "RAT"
        row = {
            "path": str(path),
            "sha256": sha,
            "label": label,
            "family": family,
            "source": source,
            "first_seen": "",
            "size": path.stat().st_size,
        }
        if sha in rows:
            dup += 1
            # giữ bản có family nếu bản cũ thiếu
            if not rows[sha]["family"] and family:
                rows[sha] = row
            return
        rows[sha] = row

    if malware_dir and malware_dir.exists():
        n = 0
        for p in iter_pe_files(malware_dir, require_mz):
            add(p, 1, malware_dir)
            n += 1
            if n % 500 == 0:
                logger.info("malware: đã quét %d file", n)
        logger.info("malware: tổng %d file PE", n)

    if benign_dir and benign_dir.exists():
        n = 0
        for p in iter_pe_files(benign_dir, require_mz):
            add(p, 0, benign_dir)
            n += 1
            if n % 500 == 0:
                logger.info("benign: đã quét %d file", n)
        logger.info("benign: tổng %d file PE", n)

    logger.info("Dedup: loại %d file trùng SHA-256 → còn %d mẫu", dup, len(rows))
    return list(rows.values())


def write_csv(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["path", "sha256", "label", "family", "source", "first_seen", "size"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    logger.info("Đã ghi %d dòng → %s", len(rows), out_path)


def summarize(rows: list[dict]) -> None:
    n_mal = sum(1 for r in rows if r["label"] == 1)
    n_ben = sum(1 for r in rows if r["label"] == 0)
    by_source: dict[str, int] = {}
    for r in rows:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    logger.info("Tổng: %d | malware: %d | benign: %d", len(rows), n_mal, n_ben)
    logger.info("Theo nguồn: %s", by_source)
    if n_ben and n_mal:
        logger.info("Tỉ lệ malware:benign = %.1f : 1", n_mal / n_ben)


# ---------------------------------------------------------------------------
# AVClass2 (tùy chọn) — chuẩn hóa tên họ
# ---------------------------------------------------------------------------

def normalize_families_avclass(rows: list[dict], vt_dir: Optional[Path]) -> None:
    """
    (Tùy chọn) Chuẩn hóa cột 'family' bằng AVClass2 nếu có báo cáo VT.
    Đây là HOOK: cần cài `avclass` và có báo cáo VirusTotal cho từng sha256.
    Hiện để placeholder — xem docs/DATA_COLLECTION.md để chạy AVClass2 thủ công
    rồi map kết quả vào labels.csv qua cột 'family'.
    """
    if vt_dir is None:
        logger.info("Bỏ qua AVClass2 (không cung cấp --vt-dir).")
        return
    logger.warning(
        "AVClass2 hook chưa nối tự động — chạy AVClass2 thủ công theo "
        "docs/DATA_COLLECTION.md rồi cập nhật cột 'family'."
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Dedup SHA-256 + gán nhãn benign/malware → labels.csv",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--malware-dir", type=Path, default=Path("data/raw/malware"))
    p.add_argument("--benign-dir", type=Path, default=Path("data/raw/benign"))
    p.add_argument("--out", type=Path, default=Path("data/interim/labels.csv"))
    p.add_argument("--vt-dir", type=Path, default=None,
                   help="(tùy chọn) thư mục báo cáo VirusTotal cho AVClass2.")
    p.add_argument("--no-mz-check", action="store_true",
                   help="Bỏ kiểm tra magic 'MZ' (nhận mọi file đuôi PE).")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    rows = build_label_rows(
        args.malware_dir, args.benign_dir, require_mz=not args.no_mz_check
    )
    normalize_families_avclass(rows, args.vt_dir)
    summarize(rows)
    write_csv(rows, args.out)


if __name__ == "__main__":
    main()
