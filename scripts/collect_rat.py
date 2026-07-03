"""
collect_rat.py
--------------
Tổ chức mẫu PE từ Ultimate-RAT-Collection vào data/raw/malware/RAT/.

⚠️  AN TOÀN: repo này chứa **builder mã độc thật**. Chỉ clone và xử lý
trong **VM cô lập** (VMware, host-only network). KHÔNG double-click,
KHÔNG thực thi, chụp snapshot trước khi làm.

Nguồn: https://github.com/Cryakl/Ultimate-RAT-Collection
Cấu trúc repo: mỗi thư mục con là 1 họ RAT (XWorm/, CraxsRat/, AsyncRAT/, ...).
Một số họ có file 7z nhiều phần — cần 7-Zip để giải nén.

Cách hoạt động:
1. (Tùy chọn) Clone hoặc cập nhật repo từ GitHub (dùng git).
2. Quét từng thư mục con (= họ), lọc file PE (magic 'MZ').
3. Copy/link vào data/raw/malware/RAT/<HọRAT>/, dedup SHA-256.
4. Ghi metadata.csv (sha256, family, orig_path, size).
5. Cố gắng giải nén .7z nếu có 7-Zip (p7zip / 7z.exe) — cảnh báo nếu thiếu.

Yêu cầu:
- git (clone bước đầu)
- 7-Zip (`7z` hoặc `7za`) để giải nén archive nhiều phần (tùy chọn)
- `pip install requests` (không bắt buộc cho bước này)

Usage:
    # Clone repo rồi tổ chức:
    python scripts/collect_rat.py --clone --repo-dir data/tmp/RAT-repo --out data/raw/malware/RAT

    # Nếu đã clone thủ công:
    python scripts/collect_rat.py --repo-dir /path/to/Ultimate-RAT-Collection --out data/raw/malware/RAT

    # Chỉ giải nén 7z trong repo rồi quét (không clone lại):
    python scripts/collect_rat.py --repo-dir data/tmp/RAT-repo --out data/raw/malware/RAT --extract-7z
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

RAT_REPO_URL = "https://github.com/Cryakl/Ultimate-RAT-Collection.git"
PE_EXTS = {".exe", ".dll", ".bin", ".sys"}
CHUNK = 1 << 20  # 1 MB

# Thư mục trong repo không phải họ RAT (bỏ qua)
NON_FAMILY_DIRS = {".git", ".github", "docs", "README", "LICENSE", "__pycache__"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_pe(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"MZ"
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Clone / update repo
# ---------------------------------------------------------------------------

def clone_or_update(repo_url: str, repo_dir: Path) -> None:
    """Clone repo nếu chưa có, hoặc git pull nếu đã có."""
    if (repo_dir / ".git").exists():
        logger.info("Repo đã tồn tại, chạy git pull: %s", repo_dir)
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "pull", "--ff-only"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            logger.warning("git pull thất bại (có thể do thay đổi local): %s", result.stderr.strip())
    else:
        logger.info("Clone repo từ %s → %s", repo_url, repo_dir)
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--depth=1", repo_url, str(repo_dir)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git clone thất bại: {result.stderr.strip()}")
        logger.info("Clone thành công.")


# ---------------------------------------------------------------------------
# Giải nén 7z
# ---------------------------------------------------------------------------

def _find_7z() -> Optional[str]:
    """Tìm 7z/7za trong PATH."""
    for cmd in ("7z", "7za", "7zr"):
        if shutil.which(cmd):
            return cmd
    return None


def extract_7z_archives(repo_dir: Path) -> None:
    """
    Tìm và giải nén .7z (bao gồm multipart .7z.001/.7z.002...) trong repo.
    Chỉ giải nén .7z đầu tiên của mỗi loạt multipart (7z tự ghép).
    """
    cmd = _find_7z()
    if not cmd:
        logger.warning(
            "Không tìm thấy 7-Zip (7z/7za). Bỏ qua giải nén .7z. "
            "Cài: `apt install p7zip-full` (Linux) hoặc 7-Zip (Windows)."
        )
        return

    # Thu thập các file .7z (loại bỏ .7z.002+ vì 7z tự xử lý multipart từ .001)
    archives: list[Path] = []
    for f in sorted(repo_dir.rglob("*.7z*")):
        if f.suffix == ".7z":
            archives.append(f)
        elif f.name.endswith(".7z.001"):
            archives.append(f)

    if not archives:
        logger.info("Không có .7z archive nào trong repo.")
        return

    # Password thường dùng trong RAT repo
    PASSWORDS = ["", "infected", "malware", "1234", "virus", "rat", "password"]

    logger.info("Giải nén %d archive .7z ...", len(archives))
    n_ok = 0
    n_fail = 0
    n_skip = 0

    for i, arc in enumerate(archives, 1):
        dest = arc.parent / arc.name.replace(".7z.001", "").replace(".7z", "_extracted")

        # Bỏ qua nếu đã giải nén rồi (chạy lại không làm lại)
        if dest.exists() and any(dest.iterdir()):
            n_skip += 1
            continue

        dest.mkdir(parents=True, exist_ok=True)

        # Thử lần lượt từng password
        success = False
        for pwd in PASSWORDS:
            pwd_flag = f"-p{pwd}" if pwd else "-p"
            result = subprocess.run(
                [cmd, "x", str(arc), f"-o{dest}", "-y", pwd_flag],
                capture_output=True, text=True,
                timeout=120,  # tối đa 2 phút mỗi archive
            )
            if result.returncode in (0, 1):
                success = True
                break

        if success:
            n_ok += 1
            if i % 50 == 0:
                logger.info("  [%d/%d] OK (skip=%d, fail=%d)", i, len(archives), n_skip, n_fail)
        else:
            n_fail += 1
            logger.warning("  [%d/%d] Thất bại: %s", i, len(archives), arc.name)

    logger.info(
        "Giải nén hoàn tất: OK=%d | bỏ qua (đã có)=%d | thất bại=%d / tổng=%d",
        n_ok, n_skip, n_fail, len(archives),
    )


# ---------------------------------------------------------------------------
# Quét & tổ chức PE
# ---------------------------------------------------------------------------

def organize(repo_dir: Path, out_dir: Path) -> list[dict]:
    """
    Duyệt thư mục repo theo cấu trúc <HọRAT>/<file>.
    Copy PE hợp lệ vào out_dir/<HọRAT>/, dedup SHA-256.
    Trả về list metadata rows.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    seen: dict[str, str] = {}  # sha256 -> dest_path (dedup)
    rows: list[dict] = []
    n_skip = 0
    n_ok = 0

    family_dirs = [
        d for d in sorted(repo_dir.iterdir())
        if d.is_dir() and d.name not in NON_FAMILY_DIRS and not d.name.startswith(".")
    ]

    if not family_dirs:
        logger.warning("Không tìm thấy thư mục họ nào trong %s", repo_dir)
        return rows

    logger.info("Tìm thấy %d họ RAT trong repo.", len(family_dirs))

    for fam_dir in family_dirs:
        family = fam_dir.name
        fam_out = out_dir / family
        n_fam = 0

        for p in fam_dir.rglob("*"):
            if not p.is_file():
                continue
            # Chấp nhận file không có đuôi hoặc đuôi PE, hoặc bất kỳ file để kiểm tra MZ
            try:
                size = p.stat().st_size
            except OSError:
                continue
            if size < 512:  # quá nhỏ
                continue
            if not _is_pe(p):
                continue

            sha = _sha256(p)
            if sha in seen:
                n_skip += 1
                continue

            fam_out.mkdir(parents=True, exist_ok=True)
            # Đặt tên file = <sha><ext> (ext gốc nếu có, không thì .bin)
            ext = p.suffix.lower() if p.suffix.lower() in PE_EXTS else ".bin"
            dst = fam_out / f"{sha}{ext}"
            try:
                shutil.copy2(p, dst)
            except OSError as e:
                logger.warning("Không copy được %s: %s", p, e)
                continue

            seen[sha] = str(dst)
            rows.append({
                "sha256": sha,
                "family": family,
                "orig_path": str(p),
                "dest_path": str(dst),
                "size": size,
                "source": "RAT",
            })
            n_ok += 1
            n_fam += 1

        if n_fam:
            logger.info("  Họ %-20s: %d mẫu PE", family, n_fam)

    logger.info("Tổng: %d mẫu PE → %s | bỏ trùng: %d", n_ok, out_dir, n_skip)
    return rows


def write_metadata(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["sha256", "family", "orig_path", "dest_path", "size", "source"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    logger.info("Metadata → %s (%d dòng)", out_path, len(rows))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Tổ chức mẫu PE từ Ultimate-RAT-Collection. Chạy trong VM cô lập!",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--repo-dir", type=Path, default=Path("data/tmp/Ultimate-RAT-Collection"),
        help="Thư mục chứa (hoặc sẽ clone vào) Ultimate-RAT-Collection.",
    )
    p.add_argument(
        "--out", type=Path, default=Path("data/raw/malware/RAT"),
        help="Thư mục output (PE được tổ chức theo họ).",
    )
    p.add_argument(
        "--clone", action="store_true",
        help="Clone (hoặc pull) repo từ GitHub trước khi xử lý.",
    )
    p.add_argument(
        "--repo-url", default=RAT_REPO_URL,
        help="URL git repo.",
    )
    p.add_argument(
        "--extract-7z", action="store_true",
        help="Giải nén các .7z (kể cả multipart) trong repo trước khi quét PE.",
    )
    p.add_argument(
        "--metadata-out", type=Path, default=None,
        help="Đường dẫn metadata CSV (mặc định: <out>/metadata.csv).",
    )
    return p


def main() -> None:
    args = _build_parser().parse_args()

    if not args.repo_dir.exists() and not args.clone:
        raise SystemExit(
            f"Không tìm thấy repo tại {args.repo_dir}. "
            "Dùng --clone để tự động clone, hoặc tải thủ công rồi chỉ --repo-dir."
        )

    if args.clone:
        clone_or_update(args.repo_url, args.repo_dir)

    if args.extract_7z:
        extract_7z_archives(args.repo_dir)

    rows = organize(args.repo_dir, args.out)

    meta_path = args.metadata_out or (args.out / "metadata.csv")
    write_metadata(rows, meta_path)


if __name__ == "__main__":
    main()
