"""
make_split.py — Giai đoạn 2 (S2.4)
----------------------------------
Chia train/val/test CHỐNG RÒ RỈ + tính mean/std per-channel trên tập TRAIN.

Chống rò rỉ (grouped split):
  - Mẫu RAT cùng một builder (sub-family) KHÔNG vắt qua train/test
    (builder có nhiều phiên bản gần trùng → phải ở chung 1 tập).
    → group_key = "RAT/<subfamily>".
  - figshare/MalwareBazaar/benign: mỗi file là 1 nhóm riêng (mẫu phân biệt,
    đã dedup SHA-256) → group_key = sha256 → phân bố tự do.
  - Stratified theo nhãn (benign/malware) để giữ tỉ lệ ở cả 3 tập.

Normalize: tính mean/std từng kênh trên ẢNH TRAIN (đọc PNG 224, streaming) →
lưu data/interim/channel_stats.json. (KHÔNG dùng stat ImageNet vì kênh không phải RGB màu.)

Usage:
    python scripts/make_split.py --input data/interim/valid_detect.csv \
        --manifest data/interim/preprocess_manifest.csv \
        --image-dir data/processed/224
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import random
from collections import defaultdict
from pathlib import Path

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def group_key(row: dict) -> str:
    """RAT → gộp theo builder (sub-family); còn lại → mỗi file 1 nhóm."""
    if str(row.get("source", "")).lower() == "rat":
        parts = Path(row["path"]).parts
        if "RAT" in parts:
            i = parts.index("RAT")
            if i + 1 < len(parts) - 1:
                return f"RAT/{parts[i + 1]}"
        return "RAT/_root"
    return row["sha256"]


def image_path(image_dir: Path, sha: str) -> Path:
    return image_dir / sha[:2] / f"{sha}.png"


def stratified_grouped_split(rows, val_frac, test_frac, seed):
    """Chia theo nhóm, stratified theo nhãn. Trả (train, val, test) list rows."""
    groups: dict[str, list] = defaultdict(list)
    for r in rows:
        groups[group_key(r)].append(r)

    by_label: dict[str, list] = defaultdict(list)  # label -> [(gk, members)]
    for gk, mem in groups.items():
        by_label[str(mem[0]["label"])].append((gk, mem))

    rng = random.Random(seed)
    train, val, test = [], [], []
    for label, glist in by_label.items():
        rng.shuffle(glist)
        total = sum(len(m) for _, m in glist)
        t_target, v_target = total * test_frac, total * val_frac
        acc_t = acc_v = 0
        for gk, mem in glist:
            if acc_t < t_target:
                test += mem; acc_t += len(mem)
            elif acc_v < v_target:
                val += mem; acc_v += len(mem)
            else:
                train += mem
    return train, val, test


def write_split(rows, image_dir: Path, out: Path, split_name: str):
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sha256", "label", "family", "source", "image_path", "split"])
        for r in rows:
            w.writerow([r["sha256"], r["label"], r.get("family", ""),
                        r.get("source", ""), str(image_path(image_dir, r["sha256"])),
                        split_name])


def compute_channel_stats(train_rows, image_dir: Path) -> dict:
    """Mean/std từng kênh trên ảnh train (thang 0–1), streaming."""
    import numpy as np
    from PIL import Image
    s = np.zeros(3, dtype=np.float64)
    ss = np.zeros(3, dtype=np.float64)
    n_pix = 0
    miss = 0
    for i, r in enumerate(train_rows, 1):
        p = image_path(image_dir, r["sha256"])
        if not p.exists():
            miss += 1
            continue
        arr = np.asarray(Image.open(p).convert("RGB"), dtype=np.float64) / 255.0
        flat = arr.reshape(-1, 3)
        s += flat.sum(0)
        ss += (flat * flat).sum(0)
        n_pix += flat.shape[0]
        if i % 500 == 0:
            logger.info("  stats: %d/%d ảnh", i, len(train_rows))
    mean = s / n_pix
    var = np.maximum(ss / n_pix - mean ** 2, 0.0)
    std = np.sqrt(var)
    if miss:
        logger.warning("Thiếu %d ảnh train (chưa sinh?)", miss)
    return {"mean": mean.tolist(), "std": std.tolist(), "n_images": len(train_rows) - miss}


def main():
    ap = argparse.ArgumentParser(description="Split chống rò rỉ + channel stats (S2.4).",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--input", type=Path, default=Path("data/interim/valid_detect.csv"))
    ap.add_argument("--manifest", type=Path, default=Path("data/interim/preprocess_manifest.csv"),
                    help="Lọc chỉ giữ mẫu status=ok (đã sinh ảnh thành công).")
    ap.add_argument("--image-dir", type=Path, default=Path("data/processed/224"))
    ap.add_argument("--out-dir", type=Path, default=Path("data/interim"))
    ap.add_argument("--stats-out", type=Path, default=Path("data/interim/channel_stats.json"))
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--test-frac", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-stats", action="store_true", help="Bỏ qua tính mean/std.")
    ap.add_argument("--only-res-eligible", action="store_true",
                    help="Chỉ lấy mẫu res_eligible=1 (dùng cho resolution sweep).")
    ap.add_argument("--out-prefix", default="split",
                    help="Tiền tố file split (vd 'sweep' → sweep_train/val/test.csv).")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if args.only_res_eligible:
        before = len(rows)
        rows = [r for r in rows if str(r.get("res_eligible", "1")) == "1"]
        logger.info("Lọc res_eligible: %d → %d mẫu (cho sweep)", before, len(rows))

    if args.manifest.exists():
        with open(args.manifest, encoding="utf-8") as f:
            ok = {r["sha256"] for r in csv.DictReader(f) if r.get("status") == "ok"}
        before = len(rows)
        rows = [r for r in rows if r["sha256"] in ok]
        logger.info("Lọc theo manifest ok: %d → %d mẫu", before, len(rows))

    train, val, test = stratified_grouped_split(rows, args.val_frac, args.test_frac, args.seed)

    def lab(rs, v):  # đếm theo nhãn
        return sum(1 for r in rs if str(r["label"]) == v)
    for name, rs in [("train", train), ("val", val), ("test", test)]:
        logger.info("%-5s: %5d mẫu (malware %d / benign %d)",
                    name, len(rs), lab(rs, "1"), lab(rs, "0"))
        write_split(rs, args.image_dir, args.out_dir / f"{args.out_prefix}_{name}.csv", name)

    # Kiểm tra không rò rỉ: tập group_key của train ∩ test = ∅
    g_tr = {group_key(r) for r in train}
    g_te = {group_key(r) for r in test}
    leak = g_tr & g_te
    logger.info("Kiểm tra rò rỉ (group train ∩ test): %d nhóm trùng %s",
                len(leak), "✓ OK" if not leak else "⚠️ CÓ RÒ RỈ")

    if not args.no_stats:
        logger.info("Tính mean/std per-channel trên train...")
        stats = compute_channel_stats(train, args.image_dir)
        args.stats_out.write_text(json.dumps(stats, indent=2), encoding="utf-8")
        logger.info("channel mean=%s std=%s → %s",
                    [round(x, 4) for x in stats["mean"]],
                    [round(x, 4) for x in stats["std"]], args.stats_out)


if __name__ == "__main__":
    main()
