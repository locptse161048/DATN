"""
preprocess.py — Giai đoạn 2 (S2.3)
----------------------------------
Sinh ảnh 3 kênh composite (gray + entropy-byte + tỉ lệ ASCII) cho danh sách file hợp lệ,
lưu bản resize (224/336/448) + (tùy chọn) bản native, và ghi manifest cuối cùng.

⚠️ Chạy trong VM cô lập (chỉ đọc bytes, không thực thi). Streaming từng file.

Đầu vào: data/interim/valid_for_train.csv (hoặc valid_detect.csv) — đã lọc min/max.
Đầu ra:
  data/processed/<size>/<sha[:2]>/<sha>.png   (ảnh 3 kênh đã resize)
  data/processed/native/<sha[:2]>/<sha>.png   (nếu --save-native)
  data/interim/preprocess_manifest.csv        (sha, label, family, status, dims, paths)

Usage:
    # mặc định size 224 (bài toán phát hiện)
    python scripts/preprocess.py --input data/interim/valid_detect.csv --workers 4
    # cho resolution sweep: thêm 336, 448 (chỉ chạy trên mẫu res_eligible)
    python scripts/preprocess.py --input data/interim/valid_detect.csv \
        --sizes 224 336 448 --only-res-eligible
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from PIL import Image

# import module trong src/preprocessing không cần là package
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "preprocessing"))
from bytes_to_image import convert_file, FileTooSmall  # noqa: E402
from channels import make_composite                    # noqa: E402

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

# Cấu hình ablation kênh (sinh ảnh) — (use_entropy, use_ascii). Mặc định full.
CHANNEL_MODES = {
    "full":      (True, True),    # [gray, entropy-byte, ascii]
    "+entropy":  (True, False),   # [gray, entropy-byte, gray]
    "+ascii":    (False, True),   # [gray, gray, ascii]
    "gray3":     (False, False),  # [gray, gray, gray]
}


def _img_path(out_dir: Path, sub: str, sha: str) -> Path:
    """Đường dẫn ảnh (KHÔNG tạo thư mục) — dùng để kiểm tra tồn tại."""
    return out_dir / sub / sha[:2] / f"{sha}.png"


def _shard(out_dir: Path, sub: str, sha: str) -> Path:
    d = out_dir / sub / sha[:2]
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{sha}.png"


def _process_one(args: dict) -> dict:
    """Worker: sinh ảnh 3 kênh cho 1 mẫu, lưu resize/native, trả manifest row."""
    row = args["row"]
    sha = row["sha256"]
    out_dir = Path(args["out_dir"])
    width = args["width"]
    min_b, max_b = args["min_bytes"], args["max_bytes"]
    sizes = args["sizes"]
    save_native = args["save_native"]
    save_gray = args["save_gray"]
    skip_existing = args["skip_existing"]
    max_nh = args["max_native_height"]
    use_entropy, use_ascii = args["channel_mode"]

    result = {"sha256": sha, "label": row.get("label", ""),
              "family": row.get("family", ""), "source": row.get("source", ""),
              "native_w": "", "native_h": "", "status": "", "image_224": ""}

    # Resume: nếu mọi size đã có ảnh → bỏ qua (không sinh lại)
    if skip_existing and all(_img_path(out_dir, str(s), sha).exists() for s in sizes):
        result["status"] = "ok"
        if 224 in sizes:
            result["image_224"] = str(_img_path(out_dir, "224", sha))
        return result

    try:
        gray_img = convert_file(row["path"], width=width,
                                min_bytes=min_b, max_bytes=max_b)
        # Chặn OOM: ảnh quá cao → thu nhỏ trước khi tính các kênh
        if max_nh and gray_img.height > max_nh:
            gray_img = gray_img.resize((gray_img.width, max_nh), Image.BILINEAR)
        gray = np.asarray(gray_img)
        comp = make_composite(gray, use_entropy=use_entropy, use_ascii=use_ascii)
        h, w = comp.shape[:2]
        result["native_h"], result["native_w"] = h, w
        pil = Image.fromarray(comp, "RGB")
        pil_gray = Image.fromarray(gray, "L") if save_gray else None
        if save_native:
            pil.save(_shard(out_dir, "native", sha))
            if pil_gray is not None:
                pil_gray.save(_shard(out_dir, "gray/native", sha))
        for s in sizes:
            p = _shard(out_dir, str(s), sha)
            pil.resize((s, s), Image.BILINEAR).save(p)          # 3 kênh composite
            if pil_gray is not None:                            # 1 kênh xám (đối chiếu)
                pil_gray.resize((s, s), Image.BILINEAR).save(_shard(out_dir, f"gray/{s}", sha))
            if s == 224:
                result["image_224"] = str(p)
        result["status"] = "ok"
    except FileTooSmall:
        result["status"] = "skipped_small"
    except Exception as e:  # noqa: BLE001
        result["status"] = f"error: {type(e).__name__}"
    return result


def load_cfg(path: Path) -> dict:
    if yaml is None or not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Sinh ảnh 3 kênh composite (S2.3).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--input", type=Path, default=Path("data/interim/valid_for_train.csv"))
    ap.add_argument("--out-dir", type=Path, default=Path("data/processed"))
    ap.add_argument("--manifest", type=Path, default=Path("data/interim/preprocess_manifest.csv"))
    ap.add_argument("--config", type=Path, default=Path("configs/data.yaml"))
    ap.add_argument("--sizes", type=int, nargs="+", default=[224])
    ap.add_argument("--channel-mode", choices=list(CHANNEL_MODES), default="full")
    ap.add_argument("--save-native", action="store_true")
    ap.add_argument("--save-gray", action="store_true",
                    help="Lưu thêm ảnh 1 kênh (xám) vào processed/gray/<size>/ để đối chiếu.")
    ap.add_argument("--skip-existing", action="store_true",
                    help="Bỏ qua mẫu đã có đủ ảnh → chạy tiếp từ chỗ dừng (resume).")
    ap.add_argument("--max-native-height", type=int, default=8192,
                    help="Thu nhỏ ảnh cao hơn ngưỡng này trước khi tính kênh (chặn OOM). 0=tắt.")
    ap.add_argument("--only-res-eligible", action="store_true",
                    help="Chỉ xử lý mẫu res_eligible=1 (cho resolution sweep).")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0, help="Giới hạn số mẫu (test).")
    args = ap.parse_args()

    cfg = load_cfg(args.config)
    width = cfg.get("image_width", 448)
    min_b = cfg.get("min_bytes", 4096)
    max_b = cfg.get("max_bytes", 31457280)

    with open(args.input, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if args.only_res_eligible:
        rows = [r for r in rows if str(r.get("res_eligible", "1")) == "1"]
    if args.limit:
        rows = rows[:args.limit]

    logger.info("Xử lý %d mẫu | sizes=%s | mode=%s | width=%d",
                len(rows), args.sizes, args.channel_mode, width)

    task_args = [{"row": r, "out_dir": str(args.out_dir), "width": width,
                  "min_bytes": min_b, "max_bytes": max_b, "sizes": args.sizes,
                  "save_native": args.save_native, "save_gray": args.save_gray,
                  "skip_existing": args.skip_existing,
                  "max_native_height": args.max_native_height,
                  "channel_mode": CHANNEL_MODES[args.channel_mode]} for r in rows]

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    cols = ["sha256", "label", "family", "source",
            "native_w", "native_h", "status", "image_224"]
    counts = {"ok": 0, "skipped_small": 0, "error": 0}

    with open(args.manifest, "w", newline="", encoding="utf-8") as mf:
        w = csv.DictWriter(mf, fieldnames=cols)
        w.writeheader()

        def handle(res: dict, done: int):
            w.writerow(res)
            key = "error" if res["status"].startswith("error") else res["status"]
            counts[key] = counts.get(key, 0) + 1
            if done % 200 == 0:
                logger.info("Tiến độ %d/%d | ok=%d skip=%d err=%d",
                            done, len(rows), counts["ok"],
                            counts["skipped_small"], counts["error"])

        if args.workers <= 1:
            for i, ta in enumerate(task_args, 1):
                handle(_process_one(ta), i)
        else:
            with ProcessPoolExecutor(max_workers=args.workers) as ex:
                futs = {ex.submit(_process_one, ta): ta for ta in task_args}
                for i, fut in enumerate(as_completed(futs), 1):
                    handle(fut.result(), i)

    logger.info("HOÀN THÀNH: ok=%d | skip=%d | error=%d → manifest %s",
                counts["ok"], counts["skipped_small"], counts["error"], args.manifest)


if __name__ == "__main__":
    main()
