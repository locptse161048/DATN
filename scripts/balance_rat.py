"""
balance_rat.py
--------------
⚠️ DEPRECATED (2026-06-28): script này DI CHUYỂN file RAT thừa ra ngoài → sẽ phá
tập đầy đủ cần cho nhánh PHÂN LOẠI họ. KHÔNG dùng nữa.
→ Dùng `scripts/make_detection_subset.py` (không phá hủy, chỉ xuất danh sách chọn)
  để tạo tập detection 1.5:1, trong khi labels.csv đầy đủ vẫn dùng cho phân loại.

Cân bằng tỉ lệ malware:benign bằng cách CẮT GIẢM dữ liệu RAT
(Ultimate-RAT-Collection thường chiếm tỉ trọng quá lớn & là 1 loại hành vi hẹp).

Chiến lược mặc định **per-family cap**: giới hạn mỗi họ RAT tối đa K mẫu, tự tìm K
để tổng RAT ≈ mục tiêu. Giữ tối đa đa dạng họ (họ hiếm gần như nguyên), cắt mạnh
các họ áp đảo → vẫn phục vụ tốt nhánh phân loại họ RAT.

KHÔNG xóa: file thừa được **chuyển** sang --excluded-dir (khôi phục được).
Dùng --dry-run để chỉ xem kế hoạch.

Mục tiêu RAT tính tự động từ tỉ lệ:
    target_malware = ratio * n_benign
    target_rat     = target_malware - n_other_malware   (figshare + MalwareBazaar)

Usage:
    # Tự tính mục tiêu để đạt tỉ lệ 2:1, xem trước
    python scripts/balance_rat.py --ratio 2.0 --dry-run

    # Thực thi (chuyển file thừa sang _excluded)
    python scripts/balance_rat.py --ratio 2.0

    # Hoặc chỉ định thẳng số RAT muốn giữ
    python scripts/balance_rat.py --target-rat 3145
"""

from __future__ import annotations

import argparse
import logging
import random
import shutil
from collections import defaultdict
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PE_EXTS = {".exe", ".dll", ".bin", ".sys", ".scr", ".ocx", ".cpl"}


def is_pe(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"MZ"
    except OSError:
        return False


def list_pe(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in PE_EXTS and is_pe(p):
            out.append(p)
    return out


def files_by_family(rat_dir: Path) -> dict[str, list[Path]]:
    """Họ = tên thư mục con cấp 1 dưới rat_dir."""
    fam: dict[str, list[Path]] = defaultdict(list)
    for p in rat_dir.rglob("*"):
        if not (p.is_file() and p.suffix.lower() in PE_EXTS and is_pe(p)):
            continue
        rel = p.relative_to(rat_dir)
        family = rel.parts[0] if len(rel.parts) >= 2 else "_root"
        fam[family].append(p)
    return fam


def find_cap(counts: list[int], target: int) -> int:
    """
    Tìm cap K lớn nhất sao cho sum(min(n, K)) <= target.
    (binary search trên K)
    """
    if sum(counts) <= target:
        return max(counts) if counts else 0
    lo, hi = 0, max(counts)
    best = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        s = sum(min(n, mid) for n in counts)
        if s <= target:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def select_keep(fam: dict[str, list[Path]], target_rat: int, seed: int
                ) -> tuple[dict[str, list[Path]], dict[str, list[Path]]]:
    """Trả về (keep, drop) theo per-family cap."""
    rng = random.Random(seed)
    counts = [len(v) for v in fam.values()]
    cap = find_cap(counts, target_rat)

    keep: dict[str, list[Path]] = {}
    drop: dict[str, list[Path]] = {}
    kept_total = 0
    for family, files in fam.items():
        files = sorted(files)  # ổn định
        if len(files) <= cap:
            keep[family] = files
            drop[family] = []
        else:
            rng.shuffle(files)
            keep[family] = sorted(files[:cap])
            drop[family] = sorted(files[cap:])
        kept_total += len(keep[family])

    # Phân bổ phần dư (target - kept_total) cho các họ còn file bị bỏ, ưu tiên họ to
    leftover = target_rat - kept_total
    if leftover > 0:
        donors = sorted(
            [f for f in fam if drop[f]],
            key=lambda f: len(drop[f]), reverse=True,
        )
        i = 0
        while leftover > 0 and donors:
            f = donors[i % len(donors)]
            if drop[f]:
                keep[f].append(drop[f].pop())
                leftover -= 1
            else:
                donors.remove(f)
                continue
            i += 1
    return keep, drop


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Cân bằng malware:benign bằng cách cắt RAT theo họ.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--malware-dir", type=Path, default=Path("data/raw/malware"))
    ap.add_argument("--benign-dir", type=Path, default=Path("data/raw/benign"))
    ap.add_argument("--rat-subdir", default="RAT", help="Thư mục RAT dưới malware-dir.")
    ap.add_argument("--ratio", type=float, default=2.0,
                    help="Tỉ lệ malware:benign mong muốn.")
    ap.add_argument("--target-rat", type=int, default=None,
                    help="Chỉ định thẳng số RAT muốn giữ (bỏ qua --ratio).")
    ap.add_argument("--excluded-dir", type=Path,
                    default=Path("data/raw/_excluded/RAT"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rat_dir = args.malware_dir / args.rat_subdir
    if not rat_dir.exists():
        raise SystemExit(f"Không thấy thư mục RAT: {rat_dir}")

    # Đếm các nhóm
    n_benign = len(list_pe(args.benign_dir))
    fam = files_by_family(rat_dir)
    n_rat = sum(len(v) for v in fam.values())
    other_dirs = [d for d in args.malware_dir.iterdir()
                  if d.is_dir() and d.name != args.rat_subdir
                  and not d.name.startswith("_")]
    n_other = sum(len(list_pe(d)) for d in other_dirs)

    # Mục tiêu RAT
    if args.target_rat is not None:
        target_rat = args.target_rat
    else:
        target_malware = int(round(args.ratio * n_benign))
        target_rat = max(0, target_malware - n_other)

    logger.info("benign=%d | malware khác RAT=%d | RAT hiện=%d (%d họ)",
                n_benign, n_other, n_rat, len(fam))
    logger.info("Mục tiêu: malware=%d (tỉ lệ %.2f:1) → giữ RAT≈%d, bỏ≈%d",
                n_other + target_rat, args.ratio, target_rat, n_rat - target_rat)

    if target_rat >= n_rat:
        logger.info("RAT hiện (%d) ≤ mục tiêu (%d) → không cần cắt.", n_rat, target_rat)
        return

    keep, drop = select_keep(fam, target_rat, args.seed)
    kept = sum(len(v) for v in keep.values())
    dropped = sum(len(v) for v in drop.values())
    final_mal = n_other + kept
    logger.info("Sau cắt: giữ RAT=%d, bỏ RAT=%d → malware=%d, tỉ lệ=%.2f:1",
                kept, dropped, final_mal, final_mal / max(1, n_benign))

    # Top họ bị ảnh hưởng
    affected = sorted(((f, len(fam[f]), len(keep[f])) for f in fam if drop[f]),
                      key=lambda x: x[1], reverse=True)[:10]
    logger.info("Top họ bị cắt (họ: trước → sau):")
    for f, before, after in affected:
        logger.info("   %-20s %5d → %d", f, before, after)

    if args.dry_run:
        logger.info("[DRY-RUN] Không di chuyển file. Bỏ --dry-run để thực thi.")
        return

    # Di chuyển file bị bỏ sang excluded-dir (giữ cấu trúc họ)
    moved = 0
    for family, files in drop.items():
        for src in files:
            dst = args.excluded_dir / family / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(src), str(dst))
                moved += 1
            except OSError as e:
                logger.warning("Không di chuyển %s: %s", src, e)
    logger.info("Đã chuyển %d file RAT thừa → %s (khôi phục được).",
                moved, args.excluded_dir)
    logger.info("Chạy lại check_duplicates.py / labeling.py để cập nhật labels.csv.")


if __name__ == "__main__":
    main()
