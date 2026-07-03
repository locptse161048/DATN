"""
collect_all.py
--------------
Orchestrator — chạy toàn bộ pipeline thu thập dữ liệu theo thứ tự:

    Bước 1: figshare  → data/raw/malware/figshare/ + data/raw/benign/figshare/
    Bước 2: MalwareBazaar → data/raw/malware/MalwareBazaar/
    Bước 3: RAT       → data/raw/malware/RAT/
    Bước 4: Benign    → data/raw/benign/<source_tag>/  (chạy thủ công / đã có)
    Bước 5: Labeling  → data/interim/labels.csv

⚠️  AN TOÀN: chạy **TRONG VM CÔ LẬP**. Chỉ đọc bytes, không thực thi mẫu.

Yêu cầu:
    pip install requests tqdm pyzipper pyyaml

    Biến môi trường cho MalwareBazaar:
        export MB_API_KEY=xxxx      (Linux/Mac)
        set MB_API_KEY=xxxx         (Windows)

Usage:
    # Chạy toàn bộ (figshare + bazaar + RAT + labeling):
    python scripts/collect_all.py --config configs/data.yaml --api-key $MB_API_KEY

    # Bỏ qua bước figshare (đã tải thủ công):
    python scripts/collect_all.py --config configs/data.yaml --skip-figshare

    # Chỉ labeling (đã có đủ raw):
    python scripts/collect_all.py --config configs/data.yaml --only-label

    # Xem status từng nguồn mà không làm gì:
    python scripts/collect_all.py --config configs/data.yaml --status
"""

from __future__ import annotations

import argparse
import importlib
import logging
import os
import sys
import time
from pathlib import Path

# Thêm root vào sys.path để import src.*
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

try:
    import yaml  # type: ignore
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_config(config_path: Path) -> dict:
    if not _HAS_YAML:
        raise ImportError("Cần pyyaml: pip install pyyaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ---------------------------------------------------------------------------
# Kiểm tra trạng thái từng nguồn
# ---------------------------------------------------------------------------

def count_pe(directory: Path) -> int:
    """Đếm số file có magic MZ trong thư mục."""
    if not directory.exists():
        return 0
    count = 0
    for p in directory.rglob("*"):
        if not p.is_file():
            continue
        try:
            with open(p, "rb") as f:
                if f.read(2) == b"MZ":
                    count += 1
        except OSError:
            pass
    return count


def print_status(cfg: dict) -> None:
    """In trạng thái số lượng mẫu hiện có từng nguồn."""
    paths = cfg.get("paths", {})
    base = Path(".")
    raw_mal = base / paths.get("raw_malware", "data/raw/malware")
    raw_ben = base / paths.get("raw_benign", "data/raw/benign")
    label_csv = base / paths.get("labels_csv", "data/interim/labels.csv")

    sources = {
        "malware/figshare":      raw_mal / "figshare",
        "malware/MalwareBazaar": raw_mal / "MalwareBazaar",
        "malware/RAT":           raw_mal / "RAT",
        "benign/figshare":       raw_ben / "figshare",
        "benign/win10_system32": raw_ben / "win10_system32",
        "benign/program_files":  raw_ben / "program_files",
        "benign/portable_apps":  raw_ben / "portable_apps",
    }

    print("\n─── Trạng thái dataset ───")
    for name, path in sources.items():
        n = count_pe(path)
        status = f"{n:>6} PE" if path.exists() else "   (chưa có thư mục)"
        print(f"  {name:<30} {status}")

    if label_csv.exists():
        import csv
        with open(label_csv, encoding="utf-8") as f:
            n_rows = sum(1 for _ in f) - 1
        print(f"\n  labels.csv                     {n_rows:>6} dòng")
    else:
        print(f"\n  labels.csv                        (chưa tạo)")
    print("─" * 44)


# ---------------------------------------------------------------------------
# Bước 1: figshare
# ---------------------------------------------------------------------------

def step_figshare(cfg: dict, skip_existing: bool = True) -> None:
    logger.info("=== BƯỚC 1: figshare 6635642 ===")
    from scripts.collect_figshare import collect as figshare_collect
    paths = cfg.get("paths", {})
    out = Path(".") / Path(paths.get("raw_malware", "data/raw/malware")).parent
    figshare_collect(
        out=out,
        skip_existing=skip_existing,
        extract=True,
        keep_archives=False,
    )


# ---------------------------------------------------------------------------
# Bước 2: MalwareBazaar
# ---------------------------------------------------------------------------

def step_malwarebazaar(cfg: dict, api_key: str) -> None:
    logger.info("=== BƯỚC 2: MalwareBazaar ===")
    from scripts.collect_malwarebazaar import collect as mb_collect
    mb_cfg = cfg.get("malwarebazaar", {})
    paths = cfg.get("paths", {})
    signatures = mb_cfg.get("signatures", [])
    if not signatures:
        logger.warning("Không có signature nào trong config — bỏ qua MalwareBazaar.")
        return
    mb_collect(
        api_key=api_key,
        signatures=signatures,
        per_signature=mb_cfg.get("per_signature", 200),
        out_dir=Path(paths.get("raw_malware", "data/raw/malware")) / "MalwareBazaar",
        extract=True,
        sleep=mb_cfg.get("sleep", 1.0),
    )


# ---------------------------------------------------------------------------
# Bước 3: RAT
# ---------------------------------------------------------------------------

def step_rat(
    cfg: dict,
    repo_dir: Path,
    clone: bool,
    extract_7z: bool,
) -> None:
    logger.info("=== BƯỚC 3: Ultimate-RAT-Collection ===")
    from scripts.collect_rat import clone_or_update, extract_7z_archives, organize, write_metadata, RAT_REPO_URL
    paths = cfg.get("paths", {})
    out_dir = Path(paths.get("raw_malware", "data/raw/malware")) / "RAT"

    if clone:
        clone_or_update(RAT_REPO_URL, repo_dir)
    if not repo_dir.exists():
        logger.warning(
            "Repo RAT không tìm thấy tại %s. Dùng --clone hoặc tải thủ công "
            "rồi chạy lại với --rat-repo-dir.", repo_dir
        )
        return
    if extract_7z:
        extract_7z_archives(repo_dir)
    rows = organize(repo_dir, out_dir)
    write_metadata(rows, out_dir / "metadata.csv")


# ---------------------------------------------------------------------------
# Bước 5: Labeling
# ---------------------------------------------------------------------------

def step_labeling(cfg: dict) -> None:
    logger.info("=== BƯỚC 5: Dedup + gán nhãn → labels.csv ===")
    from src.preprocessing.labeling import build_label_rows, write_csv, summarize
    paths = cfg.get("paths", {})
    mal_dir = Path(paths.get("raw_malware", "data/raw/malware"))
    ben_dir = Path(paths.get("raw_benign", "data/raw/benign"))
    out_csv = Path(paths.get("labels_csv", "data/interim/labels.csv"))

    rows = build_label_rows(
        malware_dir=mal_dir if mal_dir.exists() else None,
        benign_dir=ben_dir if ben_dir.exists() else None,
        require_mz=True,
    )
    summarize(rows)
    write_csv(rows, out_csv)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Thu thập dataset malware/benign từ mọi nguồn → labels.csv. "
            "Chạy TRONG VM CÔ LẬP!"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--config", type=Path, default=Path("configs/data.yaml"),
                   help="File YAML config chính (configs/data.yaml).")
    p.add_argument("--api-key", default=os.environ.get("MB_API_KEY", ""),
                   help="MalwareBazaar Auth-Key (hoặc đặt MB_API_KEY env var).")

    # Bỏ qua từng bước
    p.add_argument("--skip-figshare", action="store_true",
                   help="Bỏ qua bước tải figshare (đã tải thủ công).")
    p.add_argument("--skip-bazaar", action="store_true",
                   help="Bỏ qua bước MalwareBazaar.")
    p.add_argument("--skip-rat", action="store_true",
                   help="Bỏ qua bước RAT.")
    p.add_argument("--skip-label", action="store_true",
                   help="Bỏ qua bước labeling.")

    # Chỉ làm 1 bước
    p.add_argument("--only-label", action="store_true",
                   help="Chỉ chạy bước labeling (bỏ qua tất cả thu thập).")
    p.add_argument("--status", action="store_true",
                   help="In trạng thái số lượng mẫu rồi thoát (không làm gì).")

    # RAT options
    p.add_argument("--rat-repo-dir", type=Path,
                   default=Path("data/tmp/Ultimate-RAT-Collection"),
                   help="Thư mục repo Ultimate-RAT-Collection.")
    p.add_argument("--rat-clone", action="store_true",
                   help="Clone (hoặc pull) repo RAT từ GitHub.")
    p.add_argument("--rat-extract-7z", action="store_true",
                   help="Giải nén .7z trong repo RAT (cần 7-Zip).")

    return p


def main() -> None:
    args = _build_parser().parse_args()

    if not args.config.exists():
        raise SystemExit(f"Không tìm thấy config: {args.config}")
    cfg = load_config(args.config)

    if args.status:
        print_status(cfg)
        return

    t0 = time.time()
    failed: list[str] = []

    if args.only_label:
        step_labeling(cfg)
        logger.info("Hoàn thành chỉ labeling (%.1fs)", time.time() - t0)
        return

    # Bước 1: figshare
    if not args.skip_figshare:
        try:
            step_figshare(cfg)
        except Exception as e:
            logger.error("figshare thất bại: %s", e)
            failed.append("figshare")

    # Bước 2: MalwareBazaar
    if not args.skip_bazaar:
        api_key = args.api_key
        if not api_key:
            logger.warning(
                "Không có MB_API_KEY → bỏ qua MalwareBazaar. "
                "Đặt --api-key hoặc biến môi trường MB_API_KEY."
            )
        else:
            try:
                step_malwarebazaar(cfg, api_key)
            except Exception as e:
                logger.error("MalwareBazaar thất bại: %s", e)
                failed.append("MalwareBazaar")

    # Bước 3: RAT
    if not args.skip_rat:
        try:
            step_rat(
                cfg=cfg,
                repo_dir=args.rat_repo_dir,
                clone=args.rat_clone,
                extract_7z=args.rat_extract_7z,
            )
        except Exception as e:
            logger.error("RAT thất bại: %s", e)
            failed.append("RAT")

    # Bước 5: labeling
    if not args.skip_label:
        try:
            step_labeling(cfg)
        except Exception as e:
            logger.error("Labeling thất bại: %s", e)
            failed.append("labeling")

    elapsed = time.time() - t0
    print_status(cfg)
    if failed:
        logger.warning("Các bước thất bại: %s", ", ".join(failed))
    logger.info("Hoàn thành toàn bộ pipeline (%.1fs)", elapsed)


if __name__ == "__main__":
    main()
