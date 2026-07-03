"""
collect_figshare.py
-------------------
Tải bộ dữ liệu PE từ figshare article 6635642:
  "Malware Detection PE-Based Analysis Using Deep Learning Algorithm Dataset"
  https://figshare.com/articles/dataset/6635642

Bộ này gồm 5 loại malware (Locker, Mediyes, Winwebsec, Zbot, Zeroaccess) + Benign (~1 000 mẫu).

⚠️  AN TOÀN: tải và giải nén **TRONG VM CÔ LẬP**. Không thực thi bất kỳ file PE nào.

Yêu cầu:
- `pip install requests tqdm`
- (tùy chọn) `pip install pyzipper` nếu có file zip AES

Cách hoạt động:
1. Gọi figshare API v2 lấy danh sách file đính kèm của article 6635642.
2. Tải từng file zip/tar về --out.
3. Giải nén, sắp xếp vào data/raw/malware/figshare/ và data/raw/benign/figshare/.
4. Ghi metadata.csv (name, sha256, size, download_url).

Usage:
    python scripts/collect_figshare.py --out data/raw
    python scripts/collect_figshare.py --out data/raw --skip-existing --no-extract
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import shutil
import zipfile
from pathlib import Path
from typing import Optional

import requests

try:
    from tqdm import tqdm  # type: ignore
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

ARTICLE_ID = 6635642
FIGSHARE_API = "https://api.figshare.com/v2"

# Mapping tên file/thư mục figshare → thư mục đích.
# Key: substring trong tên file figshare (lower-case).
# Value: đường dẫn tương đối từ <out>/
FOLDER_MAP: dict[str, str] = {
    "locker":      "malware/figshare/Locker",
    "mediyes":     "malware/figshare/Mediyes",
    "winwebsec":   "malware/figshare/Winwebsec",
    "zbot":        "malware/figshare/Zbot",
    "zeroaccess":  "malware/figshare/Zeroaccess",
    "benign":      "benign/figshare",
}
FALLBACK_MALWARE = "malware/figshare/unknown"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def list_article_files(article_id: int) -> list[dict]:
    """Lấy danh sách file đính kèm của article qua figshare API."""
    url = f"{FIGSHARE_API}/articles/{article_id}/files"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def download_file(url: str, dst: Path, skip_existing: bool = True) -> bool:
    """Tải file về dst, hiển thị thanh tiến trình nếu có tqdm."""
    if skip_existing and dst.exists():
        logger.info("Đã có (bỏ qua): %s", dst.name)
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Đang tải: %s → %s", url, dst.name)
    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    total = int(r.headers.get("Content-Length", 0))
    chunk_size = 1 << 20  # 1 MB
    if HAS_TQDM and total:
        bar = tqdm(total=total, unit="B", unit_scale=True, desc=dst.name, leave=False)
    else:
        bar = None
    with open(dst, "wb") as f:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)
                if bar:
                    bar.update(len(chunk))
    if bar:
        bar.close()
    return True


def _dest_folder(filename: str, out: Path) -> Path:
    """
    Suy thư mục đích từ tên file figshare.
    Nếu là archive tổng hợp (Dataset.rar/Dataset.zip), giải nén ra một thư mục trung gian
    rồi sắp xếp theo tên thư mục con bên trong (Locker/, Mediyes/, Benign/, ...).
    """
    name_lower = filename.lower()
    for key, rel in FOLDER_MAP.items():
        if key in name_lower:
            return out / rel
    # Tên tổng hợp (Dataset.*) → giải nén vào thư mục trung gian, sắp xếp sau
    return out / "_figshare_extracted"


def reorganize_extracted(extracted_dir: Path, out: Path) -> None:
    """
    Sau khi giải nén Dataset.rar vào _figshare_extracted/, duyệt thư mục con
    và copy PE vào đúng đích theo FOLDER_MAP.

    Cấu trúc thực tế bên trong figshare Dataset.rar:
        Dataset/
          train/ và test/  (BỎNG QUA split gốc — gộp hết)
            Locker/ Mediyes/ Winwebsec/ Zbot/ Zeroaccess/ Benign/
              <file PE>

    → Chỉ dùng phần path TƯƠNG ĐỐI so với extracted_dir để match keyword,
      tránh nhầm với các thành phần đường dẫn tuyệt đối (/home/kali/...).
    """
    import shutil as _shutil

    if not extracted_dir.exists():
        logger.warning("Thư mục trung gian không tồn tại: %s", extracted_dir)
        return

    # Log cấu trúc để debug
    subdirs = sorted(set(
        p.parent.relative_to(extracted_dir)
        for p in extracted_dir.rglob("*") if p.is_file()
    ))
    logger.info("Cấu trúc bên trong archive (%d thư mục):", len(subdirs))
    for d in subdirs[:30]:
        logger.info("  %s", d)

    moved = 0
    no_match = 0
    for item in sorted(extracted_dir.rglob("*")):
        if not item.is_file():
            continue

        # Chỉ xét phần tương đối (bỏ qua /home/kali/DATN/...)
        try:
            rel_parts = item.relative_to(extracted_dir).parts
        except ValueError:
            continue

        dest_rel = None
        for part in rel_parts:
            part_lower = part.lower()
            for key, rel in FOLDER_MAP.items():
                if key in part_lower:
                    dest_rel = rel
                    break
            if dest_rel:
                break

        if not dest_rel:
            no_match += 1
            logger.debug("Không tìm được đích cho: %s", "/".join(rel_parts))
            continue

        dst_dir = out / dest_rel
        dst_dir.mkdir(parents=True, exist_ok=True)
        # Dùng sha256 ngắn + tên gốc để tránh trùng tên giữa train/ và test/
        dst = dst_dir / item.name
        if dst.exists():
            # Đổi tên nếu trùng (file khác nội dung)
            dst = dst_dir / f"{item.stem}_{item.parent.name}{item.suffix}"
        _shutil.copy2(item, dst)
        moved += 1

    logger.info(
        "Sắp xếp figshare hoàn tất: %d file → %s | không khớp keyword: %d",
        moved, out, no_match,
    )
    if no_match:
        logger.warning(
            "%d file không khớp keyword nào trong FOLDER_MAP — kiểm tra cấu trúc archive ở trên.",
            no_match,
        )

    # Xóa thư mục trung gian sau khi đã copy xong
    try:
        _shutil.rmtree(extracted_dir)
        logger.info("Đã xóa thư mục trung gian: %s", extracted_dir)
    except OSError as e:
        logger.warning("Không xóa được thư mục trung gian: %s", e)


def extract_archive(archive: Path, dest: Path) -> None:
    """Giải nén zip vào dest (cố gắng mọi định dạng phổ biến)."""
    dest.mkdir(parents=True, exist_ok=True)
    suffix = archive.suffix.lower()
    if suffix == ".zip":
        try:
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(dest)
            logger.info("Giải nén zip: %s → %s", archive.name, dest)
        except zipfile.BadZipFile:
            logger.warning("Không phải zip hợp lệ: %s (thử pyzipper nếu AES)", archive.name)
            _try_pyzipper(archive, dest)
    elif suffix in {".tar", ".gz", ".bz2", ".xz"}:
        import tarfile
        try:
            with tarfile.open(archive) as tf:
                tf.extractall(dest)
            logger.info("Giải nén tar: %s → %s", archive.name, dest)
        except Exception as e:
            logger.error("Lỗi giải nén tar %s: %s", archive.name, e)
    elif suffix == ".rar":
        _extract_rar(archive, dest)
    else:
        logger.warning("Không biết giải nén định dạng '%s' — giữ nguyên tại %s", suffix, archive)


def _extract_rar(archive: Path, dest: Path) -> None:
    """Giải nén .rar bằng unrar hoặc 7z (p7zip-full)."""
    import shutil
    import subprocess
    dest.mkdir(parents=True, exist_ok=True)
    # Ưu tiên unrar, fallback sang 7z
    cmd = shutil.which("unrar") or shutil.which("7z") or shutil.which("7za")
    if not cmd:
        logger.error(
            "Không tìm thấy unrar hoặc 7z để giải nén %s.\n"
            "  Cài: sudo apt install unrar  hoặc  sudo apt install p7zip-full",
            archive.name,
        )
        return
    tool = Path(cmd).name
    if tool == "unrar":
        args = [cmd, "x", "-y", str(archive), str(dest) + "/"]
    else:  # 7z / 7za
        args = [cmd, "x", str(archive), f"-o{dest}", "-y"]
    logger.info("Giải nén RAR (%s): %s → %s", tool, archive.name, dest)
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        logger.error("Lỗi giải nén RAR %s:\n%s", archive.name, result.stderr[:300])
    else:
        logger.info("Giải nén RAR thành công: %s", archive.name)


def _try_pyzipper(archive: Path, dest: Path) -> None:
    try:
        import pyzipper  # type: ignore
        with pyzipper.AESZipFile(archive) as zf:
            zf.extractall(dest)
        logger.info("Giải nén AES-zip (pyzipper): %s → %s", archive.name, dest)
    except ImportError:
        logger.warning("Cần pyzipper để giải nén AES: pip install pyzipper")
    except Exception as e:
        logger.error("Lỗi pyzipper %s: %s", archive.name, e)


def write_metadata(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["name", "figshare_id", "size", "computed_sha256", "download_url", "dest"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    logger.info("Metadata → %s (%d dòng)", out_path, len(rows))


def collect(
    out: Path,
    skip_existing: bool,
    extract: bool,
    keep_archives: bool,
    article_id: int = ARTICLE_ID,
) -> None:
    logger.info("Lấy danh sách file từ figshare article %d ...", article_id)
    files = list_article_files(article_id)
    logger.info("Tìm thấy %d file đính kèm.", len(files))

    archive_dir = out / "_figshare_archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    rows = []

    for fi in files:
        name = fi.get("name", "unknown")
        url = fi.get("download_url", "")
        size = fi.get("size", 0)
        fid = fi.get("id", "")
        if not url:
            logger.warning("Bỏ qua (không có download_url): %s", name)
            continue

        archive_path = archive_dir / name
        downloaded = download_file(url, archive_path, skip_existing=skip_existing)

        # Tính sha256 của archive
        computed_sha = _sha256(archive_path) if archive_path.exists() else ""

        dest_folder = _dest_folder(name, out / "raw")
        if extract and archive_path.exists():
            extract_archive(archive_path, dest_folder)
            if not keep_archives:
                archive_path.unlink(missing_ok=True)
            # Nếu giải nén vào thư mục trung gian (_figshare_extracted),
            # sắp xếp lại theo tên thư mục con bên trong archive
            if dest_folder.name == "_figshare_extracted":
                reorganize_extracted(dest_folder, out / "raw")
                dest_folder = out / "raw"  # cập nhật dest cho metadata

        rows.append({
            "name": name,
            "figshare_id": fid,
            "size": size,
            "computed_sha256": computed_sha,
            "download_url": url,
            "dest": str(dest_folder),
        })

    write_metadata(rows, out / "raw" / "figshare_metadata.csv")
    logger.info("Hoàn thành figshare. Archives tạm: %s", archive_dir if keep_archives else "(đã xoá)")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Tải bộ dữ liệu figshare 6635642 (PE malware + benign). Chạy trong VM!",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--out", type=Path, default=Path("data"),
        help="Thư mục gốc output. Malware → <out>/raw/malware/figshare/, benign → <out>/raw/benign/figshare/",
    )
    p.add_argument(
        "--article-id", type=int, default=ARTICLE_ID,
        help="figshare article ID (mặc định 6635642).",
    )
    p.add_argument(
        "--skip-existing", action="store_true", default=True,
        help="Bỏ qua file đã tải (mặc định bật).",
    )
    p.add_argument(
        "--no-skip-existing", dest="skip_existing", action="store_false",
        help="Tải lại kể cả khi đã có.",
    )
    p.add_argument(
        "--no-extract", dest="extract", action="store_false", default=True,
        help="Chỉ tải archive, không giải nén.",
    )
    p.add_argument(
        "--keep-archives", action="store_true",
        help="Giữ lại file archive sau khi giải nén.",
    )
    return p


def main() -> None:
    args = _build_parser().parse_args()
    collect(
        out=args.out,
        skip_existing=args.skip_existing,
        extract=args.extract,
        keep_archives=args.keep_archives,
        article_id=args.article_id,
    )


if __name__ == "__main__":
    main()
