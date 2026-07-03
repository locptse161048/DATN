"""
check_duplicates.py
-------------------
Tính SHA-256 toàn bộ file PE trong data/raw/ và phát hiện:
  1. File TRÙNG NHAU (cùng hash, khác đường dẫn) — trong cùng nguồn hoặc xuyên nguồn.
  2. File TRÙNG GIỮA malware và benign — nguy hiểm: cùng 1 file được gán 2 nhãn khác nhau.

Xuất ra:
  - data/interim/checksums.csv      — sha256 + path + label + source + size cho mọi file PE
  - data/interim/duplicates.csv     — các nhóm file trùng (sha256 xuất hiện ≥ 2 lần)
  - data/interim/label_conflicts.csv — file vừa là malware vừa là benign (cross-label dup)

⚠️ Chạy trong Kali VM cô lập. Script CHỈ đọc bytes (tính hash), không thực thi.

Usage:
    python scripts/check_duplicates.py
    python scripts/check_duplicates.py --malware-dir data/raw/malware --benign-dir data/raw/benign
    python scripts/check_duplicates.py --summary      # chỉ in thống kê, không ghi file
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
from collections import defaultdict
from pathlib import Path

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


# ---------------------------------------------------------------------------
# Quét thư mục
# ---------------------------------------------------------------------------

def scan_dir(root: Path, label: str) -> list[dict]:
    """Quét đệ quy root, trả về list record {sha256, path, label, source, size}."""
    records = []
    n = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() not in PE_EXTS and p.suffix != "":
            # Chấp nhận cả file không có đuôi nếu magic MZ
            pass
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size < 512:
            continue
        if not is_pe(p):
            continue
        try:
            sha = sha256_of(p)
        except OSError as e:
            logger.warning("Không đọc được %s: %s", p, e)
            continue

        # source = thư mục con đầu tiên dưới root (vd figshare, MalwareBazaar, RAT, win10_system32...)
        try:
            source = p.relative_to(root).parts[0]
        except (ValueError, IndexError):
            source = root.name

        records.append({
            "sha256": sha,
            "path": str(p),
            "label": label,
            "source": source,
            "size": size,
        })
        n += 1
        if n % 500 == 0:
            logger.info("  %s: đã quét %d file...", label, n)

    logger.info("%s (%s): tổng %d file PE", label, root, n)
    return records


# ---------------------------------------------------------------------------
# Phân tích trùng
# ---------------------------------------------------------------------------

def find_duplicates(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Trả về:
      - dup_rows: các nhóm file trùng hash (≥ 2 file cùng sha256)
      - conflict_rows: file vừa là malware vừa là benign (cross-label)
    """
    by_hash: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_hash[r["sha256"]].append(r)

    dup_rows: list[dict] = []
    conflict_rows: list[dict] = []

    for sha, group in by_hash.items():
        if len(group) < 2:
            continue
        labels = {r["label"] for r in group}
        is_conflict = len(labels) > 1  # có cả malware lẫn benign

        for r in group:
            row = {**r, "dup_count": len(group), "cross_label": is_conflict}
            dup_rows.append(row)
            if is_conflict:
                conflict_rows.append(row)

    return dup_rows, conflict_rows


# ---------------------------------------------------------------------------
# Ghi CSV
# ---------------------------------------------------------------------------

def write_csv(rows: list[dict], path: Path, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    logger.info("Ghi %d dòng → %s", len(rows), path)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(records: list[dict], dup_rows: list[dict], conflict_rows: list[dict]) -> None:
    total = len(records)
    by_label = defaultdict(int)
    by_source: dict[str, int] = defaultdict(int)
    seen: set[str] = set()
    unique = 0
    for r in records:
        by_label[r["label"]] += 1
        by_source[f"{r['label']}/{r['source']}"] += 1
        if r["sha256"] not in seen:
            seen.add(r["sha256"])
            unique += 1

    n_dup_hashes = len({r["sha256"] for r in dup_rows})
    n_conflict_hashes = len({r["sha256"] for r in conflict_rows})

    print("\n─── Báo cáo checksum & trùng lặp ───")
    print(f"  Tổng file PE quét được : {total}")
    print(f"  SHA-256 duy nhất       : {unique}")
    print(f"  File trùng (≥2 path)   : {total - unique}  ({n_dup_hashes} hash trùng)")
    print(f"  ⚠ Cross-label conflict : {n_conflict_hashes} hash (vừa malware vừa benign!)")
    print()
    print("  Theo nhãn:")
    for lbl, cnt in sorted(by_label.items()):
        print(f"    {lbl:<10} {cnt}")
    print()
    print("  Theo nguồn:")
    for src, cnt in sorted(by_source.items()):
        print(f"    {src:<35} {cnt}")

    if n_conflict_hashes:
        print(f"\n  ❌ CẢNH BÁO: {n_conflict_hashes} hash xuất hiện cả trong malware lẫn benign!")
        print("     → Xem data/interim/label_conflicts.csv để xử lý thủ công.")
    else:
        print("\n  ✓ Không có cross-label conflict.")
    print("─" * 44)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Kiểm tra SHA-256 và trùng lặp trong data/raw/. Chỉ đọc bytes.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--malware-dir", type=Path, default=Path("data/raw/malware"))
    p.add_argument("--benign-dir",  type=Path, default=Path("data/raw/benign"))
    p.add_argument("--out-dir",     type=Path, default=Path("data/interim"),
                   help="Thư mục output (checksums.csv, duplicates.csv, label_conflicts.csv).")
    p.add_argument("--summary", action="store_true",
                   help="Chỉ in thống kê, không ghi file CSV.")
    return p


def main() -> None:
    args = _build_parser().parse_args()

    records: list[dict] = []

    if args.malware_dir.exists():
        records += scan_dir(args.malware_dir, label="malware")
    else:
        logger.warning("Không tìm thấy %s", args.malware_dir)

    if args.benign_dir.exists():
        records += scan_dir(args.benign_dir, label="benign")
    else:
        logger.warning("Không tìm thấy %s", args.benign_dir)

    if not records:
        logger.error("Không có file PE nào để quét.")
        return

    dup_rows, conflict_rows = find_duplicates(records)
    print_summary(records, dup_rows, conflict_rows)

    if not args.summary:
        chk_fields = ["sha256", "path", "label", "source", "size"]
        write_csv(records,       args.out_dir / "checksums.csv",       chk_fields)
        dup_fields = ["sha256", "path", "label", "source", "size", "dup_count", "cross_label"]
        write_csv(dup_rows,      args.out_dir / "duplicates.csv",      dup_fields)
        write_csv(conflict_rows, args.out_dir / "label_conflicts.csv", dup_fields)


if __name__ == "__main__":
    main()
