"""
error_analysis.py — Giai đoạn 6 (S6.3)
---------------------------------------
Phân tích LỖI của một run đã train: model sai ở đâu, sai trên họ/nguồn nào, và
liệu chỉ cần hạ NGƯỠNG quyết định là cứu được không.

Trả lời 3 câu hỏi của S6.3:
  1. FN (bỏ sót malware) tập trung ở họ nào?  -> recall theo từng HỌ
  2. FP (báo động giả) tập trung ở nguồn benign nào?  -> FPR theo từng NGUỒN
  3. Ngưỡng 0.5 có phải điểm vận hành tốt cho an ninh không?  -> sweep ngưỡng
     (bỏ sót malware nguy hiểm hơn báo động giả => nên ưu tiên recall)

AN TOÀN: script chỉ dùng metadata + ảnh PNG + SHA-256. KHÔNG đọc, KHÔNG copy file
PE thô. Danh sách hash mẫu bị bỏ sót được xuất ra để tra VirusTotal BẰNG HASH
(không cần gửi file) — xem scripts/verify_virustotal.py.

Usage (chạy bằng venv có torch):
    ./datn-env/Scripts/python.exe scripts/error_analysis.py \
        --run experiments/detect_densenet121_224_1783077868
    ./datn-env/Scripts/python.exe scripts/error_analysis.py --filter detect_
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate import load_run, build_test_loader, predict, read_meta  # noqa: E402
from src.utils.config import get                                      # noqa: E402
from src.evaluation.metrics import compute_metrics                    # noqa: E402

LABELS_CSV = ROOT / "data" / "interim" / "labels.csv"
MAX_FPR = 0.05          # trần báo động giả mặc định khi chọn điểm vận hành
FPR_BUDGETS = (0.01, 0.02, 0.05, 0.10)   # các mức "ngân sách báo động giả" để so sánh
TOP_ERRORS = 15         # số lỗi "tự tin nhất" in ra để soi tay


def load_sizes() -> dict[str, dict]:
    """sha256 -> {size, path} lấy từ labels.csv (chỉ metadata, không đọc file PE)."""
    if not LABELS_CSV.exists():
        return {}
    with open(LABELS_CSV, encoding="utf-8") as f:
        return {r["sha256"]: {"size": r.get("size", ""), "raw_path": r.get("path", "")}
                for r in csv.DictReader(f)}


def recall_by_family(meta, y_true, y_pred, thr_pred=None):
    """Recall (=tỉ lệ bắt được) trên từng HỌ malware. Nhóm benign bỏ qua."""
    preds = y_pred if thr_pred is None else thr_pred
    g = defaultdict(lambda: {"n": 0, "hit": 0})
    for m, yt, yp in zip(meta, y_true, preds):
        if yt != 1:
            continue
        fam = m.get("family") or "(unknown)"
        g[fam]["n"] += 1
        g[fam]["hit"] += int(yp == 1)
    rows = [{"family": k, "n": v["n"], "n_missed": v["n"] - v["hit"],
             "recall": v["hit"] / v["n"] if v["n"] else float("nan")}
            for k, v in g.items()]
    rows.sort(key=lambda r: r["recall"])
    return rows


def fpr_by_source(meta, y_true, y_pred):
    """FPR (=tỉ lệ báo động giả) trên từng NGUỒN benign. Nhóm malware bỏ qua."""
    g = defaultdict(lambda: {"n": 0, "fp": 0})
    for m, yt, yp in zip(meta, y_true, y_pred):
        if yt != 0:
            continue
        s = m.get("source") or "(unknown)"
        g[s]["n"] += 1
        g[s]["fp"] += int(yp == 1)
    rows = [{"source": k, "n": v["n"], "n_false_alarm": v["fp"],
             "fpr": v["fp"] / v["n"] if v["n"] else float("nan"),
             "specificity": 1 - (v["fp"] / v["n"]) if v["n"] else float("nan")}
            for k, v in g.items()]
    rows.sort(key=lambda r: -r["fpr"])
    return rows


def threshold_sweep(y_true, y_prob, max_fpr=MAX_FPR):
    """Quét ngưỡng 0.01..0.99 -> recall/FPR/precision/F1. Trả về (bảng, điểm vận hành đề xuất)."""
    y = np.asarray(y_true)
    p = np.asarray(y_prob)
    n_pos, n_neg = int((y == 1).sum()), int((y == 0).sum())
    rows = []
    for thr in np.arange(0.01, 1.00, 0.01):
        pred = (p >= thr).astype(int)
        tp = int(((pred == 1) & (y == 1)).sum())
        fp = int(((pred == 1) & (y == 0)).sum())
        fn = n_pos - tp
        recall = tp / n_pos if n_pos else float("nan")
        fpr = fp / n_neg if n_neg else float("nan")
        prec = tp / (tp + fp) if (tp + fp) else float("nan")
        f1 = 2 * prec * recall / (prec + recall) if (prec + recall) else 0.0
        rows.append({"threshold": round(float(thr), 2), "recall": recall, "fpr": fpr,
                     "precision": prec, "f1": f1, "n_missed": fn, "n_false_alarm": fp})

    # Điểm vận hành đề xuất: recall CAO NHẤT với ràng buộc FPR <= max_fpr
    feasible = [r for r in rows if r["fpr"] <= max_fpr]
    best_sec = max(feasible, key=lambda r: (r["recall"], -r["fpr"])) if feasible else None
    best_f1 = max(rows, key=lambda r: r["f1"])
    return rows, best_sec, best_f1


def recall_at_budgets(rows, budgets=FPR_BUDGETS):
    """Với mỗi 'ngân sách báo động giả' (FPR trần) -> ngưỡng cho recall cao nhất.

    Lưu ý đọc kết quả: nếu FPR ở ngưỡng mặc định 0.5 ĐÃ vượt ngân sách thì để giữ
    FPR trong ngân sách buộc phải NÂNG ngưỡng -> recall GIẢM (đánh đổi ngược).
    """
    out = []
    for b in budgets:
        feasible = [r for r in rows if r["fpr"] <= b]
        if not feasible:
            out.append({"budget_fpr": b, "threshold": None, "recall": float("nan"),
                        "fpr": float("nan"), "n_missed": None, "n_false_alarm": None})
            continue
        best = max(feasible, key=lambda r: (r["recall"], -r["fpr"]))
        out.append({"budget_fpr": b, "threshold": best["threshold"], "recall": best["recall"],
                    "fpr": best["fpr"], "precision": best["precision"], "f1": best["f1"],
                    "n_missed": best["n_missed"], "n_false_alarm": best["n_false_alarm"]})
    return out


def main():
    ap = argparse.ArgumentParser(description="Phân tích lỗi FP/FN + ngưỡng (S6.3).")
    ap.add_argument("--run", type=Path, help="1 thư mục run cụ thể.")
    ap.add_argument("--exp-dir", type=Path, default=Path("experiments"))
    ap.add_argument("--filter", default="", help="Lấy mọi run khớp chuỗi này.")
    ap.add_argument("--out-dir", type=Path, default=Path("results/metrics"))
    ap.add_argument("--max-fpr", type=float, default=MAX_FPR,
                    help="Trần FPR khi chọn điểm vận hành ưu tiên recall (mặc định 0.02).")
    args = ap.parse_args()

    if args.run:
        run_dirs = [args.run]
    elif args.filter:
        run_dirs = [d for d in sorted(args.exp_dir.iterdir())
                    if d.is_dir() and args.filter in d.name and (d / "best.pt").exists()]
    else:
        raise SystemExit("Cần --run <thư mục> hoặc --filter <chuỗi>.")
    if not run_dirs:
        raise SystemExit("Không tìm thấy run nào.")

    sizes = load_sizes()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for run_dir in run_dirs:
        print(f"\n{'=' * 78}\nPHÂN TÍCH LỖI — {run_dir.name}\n{'=' * 78}")
        cfg, model, device = load_run(run_dir)
        loader, csv_path = build_test_loader(cfg)
        y_true, y_pred, y_prob = predict(model, loader, device)
        meta = read_meta(csv_path)
        if len(meta) != len(y_true):
            raise RuntimeError(f"meta ({len(meta)}) != dự đoán ({len(y_true)})")

        overall = compute_metrics(y_true, y_pred, y_prob)
        tag = run_dir.name
        print(f"Tổng thể: acc={overall['acc']:.4f} recall={overall['recall']:.4f} "
              f"precision={overall['precision']:.4f} auc={overall['roc_auc']:.4f}\n")

        # ---------- 1. Danh sách mọi mẫu sai ----------
        errors = []
        for m, yt, yp, pr in zip(meta, y_true, y_pred, y_prob):
            if yt == yp:
                continue
            extra = sizes.get(m["sha256"], {})
            errors.append({
                "sha256": m["sha256"],
                "error_type": "FN (bỏ sót malware)" if yt == 1 else "FP (báo động giả)",
                "true_label": yt, "pred_label": yp,
                "prob_malware": round(float(pr), 4),
                "confidence": round(abs(float(pr) - 0.5) * 2, 4),  # 1.0 = model rất chắc mà vẫn sai
                "family": m.get("family", ""), "source": m.get("source", ""),
                "size_bytes": extra.get("size", ""),
                "image_path": m.get("image_path", ""),
            })
        errors.sort(key=lambda r: -r["confidence"])

        err_path = args.out_dir / f"errors_{tag}.csv"
        with open(err_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(errors[0].keys()) if errors else ["sha256"])
            w.writeheader()
            w.writerows(errors)

        n_fn = sum(1 for e in errors if e["true_label"] == 1)
        n_fp = len(errors) - n_fn
        print(f"Tổng lỗi: {len(errors)}  |  FN (bỏ sót malware) = {n_fn}  |  FP (báo động giả) = {n_fp}")

        print(f"\n--- {TOP_ERRORS} lỗi TỰ TIN NHẤT (model rất chắc chắn nhưng vẫn sai) ---")
        print(f'{"loại":<22} {"prob":<7} {"họ":<16} {"nguồn":<20} {"size":<10} sha256[:16]')
        for e in errors[:TOP_ERRORS]:
            print(f'{e["error_type"]:<22} {e["prob_malware"]:<7} {e["family"]:<16} '
                  f'{e["source"]:<20} {e["size_bytes"]:<10} {e["sha256"][:16]}')

        # ---------- 2. Recall theo HỌ (FN tập trung ở đâu?) ----------
        fam_rows = recall_by_family(meta, y_true, y_pred)
        print(f'\n--- RECALL THEO HỌ MALWARE (thấp = hay bị bỏ sót) ---')
        print(f'{"họ":<20} {"n":<6} {"bỏ sót":<8} {"recall":<8}')
        for r in fam_rows:
            flag = "  <-- ĐIỂM MÙ" if r["recall"] < overall["recall"] - 0.05 and r["n"] >= 20 else ""
            print(f'{r["family"]:<20} {r["n"]:<6} {r["n_missed"]:<8} {r["recall"]:.4f}{flag}')
        with open(args.out_dir / f"error_by_family_{tag}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["family", "n", "n_missed", "recall"])
            w.writeheader(); w.writerows(fam_rows)

        # ---------- 3. FPR theo NGUỒN benign (FP tập trung ở đâu?) ----------
        src_rows = fpr_by_source(meta, y_true, y_pred)
        print(f'\n--- BÁO ĐỘNG GIẢ THEO NGUỒN BENIGN (cao = hay bị gán nhầm malware) ---')
        print(f'{"nguồn":<22} {"n":<6} {"báo giả":<9} {"FPR":<8}')
        for r in src_rows:
            print(f'{r["source"]:<22} {r["n"]:<6} {r["n_false_alarm"]:<9} {r["fpr"]:.4f}')
        with open(args.out_dir / f"error_by_source_{tag}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["source", "n", "n_false_alarm", "fpr", "specificity"])
            w.writeheader(); w.writerows(src_rows)

        # ---------- 4. Sweep ngưỡng: 0.5 có tối ưu cho an ninh không? ----------
        thr_rows, best_sec, best_f1 = threshold_sweep(y_true, y_prob, args.max_fpr)
        with open(args.out_dir / f"threshold_curve_{tag}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(thr_rows[0].keys()))
            w.writeheader(); w.writerows(thr_rows)

        cur = next(r for r in thr_rows if r["threshold"] == 0.50)
        print(f'\n--- ĐIỂM VẬN HÀNH (an ninh: bỏ sót malware nguy hiểm hơn báo động giả) ---')
        print(f'Hiện tại @0.50: recall={cur["recall"]:.4f}  FPR={cur["fpr"]:.4f}  '
              f'bỏ sót={cur["n_missed"]}  báo giả={cur["n_false_alarm"]}')
        print(f'\n{"ngân sách FPR":<15} {"ngưỡng":<9} {"recall":<9} {"FPR thực":<10} '
              f'{"bỏ sót":<8} {"báo giả":<9} {"so với @0.50"}')
        for r in recall_at_budgets(thr_rows):
            if r["threshold"] is None:
                print(f'<= {r["budget_fpr"]:.0%}          (không ngưỡng nào đạt được ngân sách này)')
                continue
            d = r["recall"] - cur["recall"]
            note = f'recall {d:+.4f}' + ("  <-- ĐÁNH ĐỔI NGƯỢC (phải nâng ngưỡng)" if d < 0 else "")
            print(f'<= {r["budget_fpr"]:<12.0%} {r["threshold"]:<9.2f} {r["recall"]:<9.4f} '
                  f'{r["fpr"]:<10.4f} {r["n_missed"]:<8} {r["n_false_alarm"]:<9} {note}')
        print(f'{"max F1":<15} {best_f1["threshold"]:<9.2f} {best_f1["recall"]:<9.4f} '
              f'{best_f1["fpr"]:<10.4f} {best_f1["n_missed"]:<8} {best_f1["n_false_alarm"]:<9} '
              f'F1={best_f1["f1"]:.4f}')

        # Ngưỡng mới có cứu được các HỌ điểm mù không?
        if best_sec and best_sec["threshold"] != 0.50:
            new_pred = [int(p >= best_sec["threshold"]) for p in y_prob]
            fam_new = {r["family"]: r for r in recall_by_family(meta, y_true, new_pred)}
            print(f'\n--- RECALL THEO HỌ SAU KHI HẠ NGƯỠNG xuống {best_sec["threshold"]:.2f} ---')
            print(f'{"họ":<20} {"recall @0.50":<14} {"recall @mới":<13} {"thay đổi"}')
            for r in sorted(fam_rows, key=lambda x: x["recall"]):
                if r["n"] < 20:
                    continue
                nr = fam_new[r["family"]]["recall"]
                print(f'{r["family"]:<20} {r["recall"]:<14.4f} {nr:<13.4f} {nr - r["recall"]:+.4f}')

        # ---------- 5. Xuất hash các mẫu bị bỏ sót -> tra VirusTotal bằng HASH ----------
        fn_hashes = [e["sha256"] for e in errors if e["true_label"] == 1]
        hash_path = args.out_dir / f"fn_hashes_{tag}.txt"
        hash_path.write_text("\n".join(fn_hashes), encoding="utf-8")

        print(f"\n-> Đã lưu:")
        print(f"   {err_path}                     (mọi mẫu sai, sắp theo độ 'tự tin sai')")
        print(f"   {args.out_dir}/error_by_family_{tag}.csv   (recall theo họ)")
        print(f"   {args.out_dir}/error_by_source_{tag}.csv   (báo động giả theo nguồn)")
        print(f"   {args.out_dir}/threshold_curve_{tag}.csv   (đường cong ngưỡng)")
        print(f"   {hash_path}   ({len(fn_hashes)} hash bị bỏ sót -> tra VirusTotal BẰNG HASH)")

    print("\nBƯỚC KIỂM CHỨNG NHÃN: đưa file fn_hashes_*.txt vào scripts/verify_virustotal.py.")
    print("Nếu VirusTotal báo SẠCH (0 detection) cho mẫu nào -> NHÃN SAI, không phải model sai.")
    print("(Tra bằng hash: KHÔNG cần gửi file PE ra khỏi VM cô lập.)")


if __name__ == "__main__":
    main()
