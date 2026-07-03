"""
verify_virustotal.py
--------------------
Query VirusTotal API v3 theo SHA-256 để xác minh mẫu malware/benign.

Mục đích:
  - Malware: xác nhận file thực sự độc hại (≥ N engine phát hiện).
  - Benign:  xác nhận file sạch (0 hoặc rất ít engine phát hiện).
  - Xuất báo cáo CSV để lọc trước khi đưa vào training.

⚠️ Giới hạn API miễn phí VT: 4 request/phút, 500/ngày.
   Script tự điều chỉnh rate-limit. Dùng --limit để giới hạn số lượng.

Yêu cầu:
  - Tài khoản VirusTotal + API key (free tại https://www.virustotal.com/gui/join-us)
  - `pip install requests`
  - Biến môi trường VT_API_KEY hoặc tham số --api-key

Đầu vào:
  - Đường dẫn thư mục raw hoặc file checksums.csv từ check_duplicates.py

Đầu ra:
  - data/interim/vt_report.csv      — kết quả đầy đủ mỗi file
  - data/interim/vt_suspicious.csv  — file cần kiểm tra lại (benign bị detect / malware clean)
  - data/interim/vt_cache.json      — cache kết quả (tránh query lại)

Usage:
    export VT_API_KEY="xxxx"

    # Query từ checksums.csv (ưu tiên — đã có sha256 sẵn)
    python scripts/verify_virustotal.py --checksums data/interim/checksums.csv

    # Query trực tiếp từ thư mục raw
    python scripts/verify_virustotal.py --malware-dir data/raw/malware --benign-dir data/raw/benign

    # Giới hạn 100 mẫu (test)
    python scripts/verify_virustotal.py --checksums data/interim/checksums.csv --limit 100

    # Chỉ query malware, bỏ qua benign
    python scripts/verify_virustotal.py --checksums data/interim/checksums.csv --only-malware

    # Xem báo cáo tóm tắt từ vt_report.csv (không query thêm)
    python scripts/verify_virustotal.py --report-only
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

VT_API_URL = "https://www.virustotal.com/api/v3/files/{hash}"

# Ngưỡng phán định
MALWARE_MIN_DETECTIONS = 5   # malware hợp lệ: ≥ 5 engine phát hiện
BENIGN_MAX_DETECTIONS  = 2   # benign hợp lệ: ≤ 2 engine phát hiện (false positive)

# Rate limit API miễn phí VT: 4 req/phút
FREE_RATE_LIMIT_RPM = 4
_SLEEP_BETWEEN_REQUESTS = 60.0 / FREE_RATE_LIMIT_RPM  # 15 giây/request

PE_EXTS = {".exe", ".dll", ".bin", ".sys", ".scr", ".ocx", ".cpl"}
CHUNK = 1 << 20


# ---------------------------------------------------------------------------
# Hash
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
# Cache JSON
# ---------------------------------------------------------------------------

def load_cache(cache_path: Path) -> dict:
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache: dict, cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


# ---------------------------------------------------------------------------
# VirusTotal API
# ---------------------------------------------------------------------------

def query_vt(sha256: str, api_key: str) -> Optional[dict]:
    """
    Query VirusTotal API v3 cho 1 hash.
    Trả về dict kết quả thô hoặc None nếu lỗi.
    """
    url = VT_API_URL.format(hash=sha256)
    headers = {"x-apikey": api_key}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 404:
            return {"not_found": True, "sha256": sha256}
        if r.status_code == 429:
            logger.warning("Rate limit VT — chờ 60s rồi thử lại...")
            time.sleep(60)
            r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        logger.error("Lỗi query VT (%s): %s", sha256[:12], e)
        return None


def parse_vt_response(raw: dict, sha256: str, label: str, source: str) -> dict:
    """
    Trích xuất thông tin quan trọng từ kết quả VT API v3.
    Trả về dict phẳng để ghi CSV.
    """
    if raw.get("not_found"):
        return {
            "sha256": sha256, "label": label, "source": source,
            "found_on_vt": False,
            "malicious": 0, "suspicious": 0, "harmless": 0, "undetected": 0, "total_engines": 0,
            "detection_ratio": "0/0",
            "verdict": "not_found",
            "av_families": "",
            "first_submission": "", "last_analysis_date": "",
        }

    data = raw.get("data", {})
    attrs = data.get("attributes", {})
    stats = attrs.get("last_analysis_stats", {})
    results = attrs.get("last_analysis_results", {})

    malicious   = stats.get("malicious", 0)
    suspicious  = stats.get("suspicious", 0)
    harmless    = stats.get("harmless", 0)
    undetected  = stats.get("undetected", 0)
    total       = malicious + suspicious + harmless + undetected

    # Thu thập tên họ từ các engine phát hiện
    families: set[str] = set()
    for eng, res in results.items():
        cat = res.get("category", "")
        if cat in ("malicious", "suspicious"):
            result_str = res.get("result") or ""
            if result_str:
                families.add(result_str)

    # Phán định
    if label == "malware":
        if malicious >= MALWARE_MIN_DETECTIONS:
            verdict = "confirmed_malware"
        elif malicious > 0:
            verdict = "low_detection"   # đáng ngờ — kiểm tra lại
        else:
            verdict = "clean_but_labeled_malware"  # ⚠ cần xem lại
    else:  # benign
        if malicious > BENIGN_MAX_DETECTIONS:
            verdict = "detected_as_malware"  # ⚠ benign nhưng VT cho là malware
        elif malicious > 0:
            verdict = "low_detection_benign"
        else:
            verdict = "confirmed_clean"

    return {
        "sha256": sha256,
        "label": label,
        "source": source,
        "found_on_vt": True,
        "malicious": malicious,
        "suspicious": suspicious,
        "harmless": harmless,
        "undetected": undetected,
        "total_engines": total,
        "detection_ratio": f"{malicious}/{total}",
        "verdict": verdict,
        "av_families": "|".join(sorted(families)[:10]),  # tối đa 10 tên
        "first_submission": attrs.get("first_submission_date", ""),
        "last_analysis_date": attrs.get("last_analysis_date", ""),
    }


# ---------------------------------------------------------------------------
# Thu thập danh sách cần query
# ---------------------------------------------------------------------------

def load_from_checksums(csv_path: Path, only_malware: bool, only_benign: bool) -> list[dict]:
    """Đọc checksums.csv từ check_duplicates.py."""
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if only_malware and r.get("label") != "malware":
                continue
            if only_benign and r.get("label") != "benign":
                continue
            rows.append({"sha256": r["sha256"], "label": r.get("label", ""), "source": r.get("source", "")})
    return rows


def scan_dirs(malware_dir: Optional[Path], benign_dir: Optional[Path],
              only_malware: bool, only_benign: bool) -> list[dict]:
    """Quét thư mục raw, trả về list {sha256, label, source}."""
    items: list[dict] = []
    seen: set[str] = set()

    def _scan(root: Path, label: str) -> None:
        for p in sorted(root.rglob("*")):
            if not p.is_file() or not is_pe(p):
                continue
            try:
                sha = sha256_of(p)
            except OSError:
                continue
            if sha in seen:
                continue
            seen.add(sha)
            try:
                source = p.relative_to(root).parts[0]
            except (ValueError, IndexError):
                source = root.name
            items.append({"sha256": sha, "label": label, "source": source})

    if malware_dir and malware_dir.exists() and not only_benign:
        logger.info("Quét malware: %s", malware_dir)
        _scan(malware_dir, "malware")
    if benign_dir and benign_dir.exists() and not only_malware:
        logger.info("Quét benign: %s", benign_dir)
        _scan(benign_dir, "benign")
    return items


# ---------------------------------------------------------------------------
# Ghi CSV
# ---------------------------------------------------------------------------

REPORT_FIELDS = [
    "sha256", "label", "source", "found_on_vt",
    "malicious", "suspicious", "harmless", "undetected", "total_engines",
    "detection_ratio", "verdict", "av_families",
    "first_submission", "last_analysis_date",
]

SUSPICIOUS_VERDICTS = {
    "low_detection",
    "clean_but_labeled_malware",
    "detected_as_malware",
    "not_found",
}


def write_report(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=REPORT_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    logger.info("Báo cáo VT → %s (%d dòng)", path, len(rows))


def print_vt_summary(rows: list[dict]) -> None:
    from collections import Counter
    verdicts = Counter(r["verdict"] for r in rows)
    n_found  = sum(1 for r in rows if r.get("found_on_vt"))
    print("\n─── Báo cáo VirusTotal ───")
    print(f"  Tổng query     : {len(rows)}")
    print(f"  Có trên VT     : {n_found}")
    print(f"  Không có trên VT: {len(rows) - n_found}")
    print()
    print("  Verdict:")
    for v, cnt in verdicts.most_common():
        flag = " ⚠" if v in SUSPICIOUS_VERDICTS else " ✓"
        print(f"    {v:<35} {cnt:>5}{flag}")
    n_sus = sum(cnt for v, cnt in verdicts.items() if v in SUSPICIOUS_VERDICTS)
    print(f"\n  Cần kiểm tra lại: {n_sus} mẫu → data/interim/vt_suspicious.csv")
    print("─" * 44)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Xác minh mẫu qua VirusTotal API v3. Cần VT_API_KEY.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--api-key", default=os.environ.get("VT_API_KEY", ""),
                   help="VirusTotal API key (hoặc đặt VT_API_KEY env var).")
    # Đầu vào
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--checksums", type=Path, default=None,
                     help="File checksums.csv từ check_duplicates.py (ưu tiên dùng cái này).")
    grp.add_argument("--malware-dir", type=Path, default=None)

    p.add_argument("--benign-dir", type=Path, default=None)
    # Bộ lọc
    p.add_argument("--only-malware", action="store_true", help="Chỉ query mẫu malware.")
    p.add_argument("--only-benign",  action="store_true", help="Chỉ query mẫu benign.")
    p.add_argument("--limit", type=int, default=0,
                   help="Giới hạn số lượng query (0 = không giới hạn). Dùng khi test.")
    # Output
    p.add_argument("--out-dir", type=Path, default=Path("data/interim"))
    p.add_argument("--cache",   type=Path, default=Path("data/interim/vt_cache.json"),
                   help="File JSON cache kết quả (tránh query lại cùng hash).")
    # Chế độ
    p.add_argument("--report-only", action="store_true",
                   help="Chỉ in tóm tắt từ vt_report.csv hiện có, không query thêm.")
    p.add_argument("--malware-min-detections", type=int, default=MALWARE_MIN_DETECTIONS,
                   help="Ngưỡng engine tối thiểu để xác nhận malware.")
    p.add_argument("--benign-max-detections",  type=int, default=BENIGN_MAX_DETECTIONS,
                   help="Ngưỡng engine tối đa cho benign (vượt = nghi ngờ).")
    p.add_argument("--sleep", type=float, default=_SLEEP_BETWEEN_REQUESTS,
                   help="Giây nghỉ giữa các request (mặc định 15s cho free tier).")
    return p


def main() -> None:
    global MALWARE_MIN_DETECTIONS, BENIGN_MAX_DETECTIONS
    args = _build_parser().parse_args()

    MALWARE_MIN_DETECTIONS = args.malware_min_detections
    BENIGN_MAX_DETECTIONS  = args.benign_max_detections

    report_path    = args.out_dir / "vt_report.csv"
    suspicious_path = args.out_dir / "vt_suspicious.csv"

    # Chế độ chỉ xem báo cáo
    if args.report_only:
        if not report_path.exists():
            raise SystemExit(f"Chưa có báo cáo tại {report_path}. Chạy query trước.")
        rows = []
        with open(report_path, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        print_vt_summary(rows)
        return

    if not args.api_key:
        raise SystemExit(
            "Thiếu VT API key. Đặt VT_API_KEY hoặc --api-key.\n"
            "Đăng ký free tại https://www.virustotal.com/gui/join-us"
        )

    # Thu thập danh sách hash cần query
    if args.checksums:
        items = load_from_checksums(args.checksums, args.only_malware, args.only_benign)
    else:
        mal_dir = args.malware_dir or Path("data/raw/malware")
        ben_dir = args.benign_dir  or Path("data/raw/benign")
        items = scan_dirs(mal_dir, ben_dir, args.only_malware, args.only_benign)

    if args.limit > 0:
        items = items[:args.limit]
    logger.info("Sẽ query %d hash trên VirusTotal.", len(items))

    # Ước tính thời gian
    est_min = len(items) * args.sleep / 60
    logger.info("Ước tính thời gian: %.0f phút (%.0fs/query, free tier).", est_min, args.sleep)

    # Load cache
    cache = load_cache(args.cache)
    logger.info("Cache hiện có: %d hash.", len(cache))

    # Load báo cáo cũ nếu có (để append)
    existing: dict[str, dict] = {}
    if report_path.exists():
        with open(report_path, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                existing[r["sha256"]] = r

    report_rows: list[dict] = list(existing.values())
    n_queried = 0
    n_cached  = 0

    for item in items:
        sha    = item["sha256"]
        label  = item["label"]
        source = item["source"]

        # Đã có trong báo cáo cũ → bỏ qua
        if sha in existing:
            continue

        # Lấy từ cache
        if sha in cache:
            raw = cache[sha]
            n_cached += 1
        else:
            raw = query_vt(sha, args.api_key)
            if raw is None:
                logger.warning("Query thất bại: %s", sha[:12])
                continue
            cache[sha] = raw
            n_queried += 1
            # Lưu cache mỗi 10 query
            if n_queried % 10 == 0:
                save_cache(cache, args.cache)
            time.sleep(args.sleep)

        row = parse_vt_response(raw, sha, label, source)
        report_rows.append(row)
        existing[sha] = row

        # Log tiến trình
        total_done = n_queried + n_cached
        if total_done % 20 == 0 or total_done == len(items):
            logger.info(
                "  [%d/%d] %s | verdict=%s | %s",
                total_done, len(items), sha[:12], row["verdict"], row["detection_ratio"],
            )

    # Lưu cache cuối
    save_cache(cache, args.cache)
    logger.info("Query thật: %d | Từ cache: %d", n_queried, n_cached)

    # Ghi báo cáo
    write_report(report_rows, report_path)

    # Ghi file đáng ngờ
    sus_rows = [r for r in report_rows if r.get("verdict") in SUSPICIOUS_VERDICTS]
    write_report(sus_rows, suspicious_path)

    print_vt_summary(report_rows)


if __name__ == "__main__":
    main()
