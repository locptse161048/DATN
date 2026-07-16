"""
make_clean_labels.py — Lam sach nhan RAT theo VirusTotal (S6.3).

Xu ly CA HAI bo split:
  * split_{train,val,test}.csv  -> split_clean_*.csv   (bai toan phat hien)
  * sweep_{train,val,test}.csv  -> sweep_clean_*.csv   (luoi 5x3 do phan giai)

Phan quyet (chi ap cho family == RAT da co verdict VT):
  * VT 0 engine            -> NHAN SAI  -> malware -> BENIGN (label 0)
  * VT 1..DROP_MAX / not_found -> vung xam -> LOAI khoi tap
  * VT >= KEEP_MIN engine   -> dung malware -> giu nguyen

Sinh file *_clean_*.csv MOI, KHONG ghi de ban goc. Config chi can doi split_prefix:
  detect: split_prefix: split_clean   |   sweep: split_prefix: sweep_clean

Usage:
    python scripts/make_clean_labels.py --preview
    python scripts/make_clean_labels.py                 # ca split + sweep
    python scripts/make_clean_labels.py --prefixes sweep
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

INTERIM = Path("data/interim")
VT_CSV = INTERIM / "vt_rat_full.csv"

DROP_MAX = 4
KEEP_MIN = 5


def vt_decision(row):
    if not row:
        return "unknown"
    if row.get("verdict") == "not_found":
        return "drop"
    try:
        m = int(row.get("malicious") or 0)
    except ValueError:
        return "unknown"
    if m == 0:
        return "benign"
    if m <= DROP_MAX:
        return "drop"
    return "malware"


def load_vt():
    if not VT_CSV.exists():
        raise SystemExit("Chua co %s. Chay verify_virustotal truoc." % VT_CSV)
    with open(VT_CSV, encoding="utf-8") as f:
        return {r["sha256"].lower(): r for r in csv.DictReader(f)}


def process_one(prefix, part, vt, preview):
    src = INTERIM / ("%s_%s.csv" % (prefix, part))
    with open(src, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)

    kept = []
    st = {"to_benign": 0, "dropped": 0, "kept_malware": 0, "untouched": 0, "rat_unknown": 0}
    for r in rows:
        if r.get("family") != "RAT":
            kept.append(r); st["untouched"] += 1; continue
        dec = vt_decision(vt.get(r["sha256"].lower()))
        if dec == "benign":
            r = dict(r); r["label"] = "0"; r["family"] = "benign_from_RAT"
            kept.append(r); st["to_benign"] += 1
        elif dec == "drop":
            st["dropped"] += 1
        elif dec == "malware":
            kept.append(r); st["kept_malware"] += 1
        else:
            kept.append(r); st["rat_unknown"] += 1

    st["after_benign"] = sum(1 for r in kept if r["label"] == "0")
    st["after_malware"] = sum(1 for r in kept if r["label"] == "1")
    st["after_total"] = len(kept)

    if not preview:
        out = INTERIM / ("%s_clean_%s.csv" % (prefix, part))
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(fields))
            w.writeheader()
            for r in kept:
                w.writerow(r)
    return st


def process_prefix(prefix, vt, preview):
    print("\n=== %s ===" % prefix.upper())
    print("part   ->benign  loai  giu-mal  RAT-chua-tra |  benign malware   tong   ty-le")
    print("-" * 80)
    gb = gd = 0
    for part in ["train", "val", "test"]:
        s = process_one(prefix, part, vt, preview)
        gb += s["to_benign"]; gd += s["dropped"]
        ratio = s["after_malware"] / max(1, s["after_benign"])
        print("%-6s %8d %5d %8d %13d |  %6d %7d %7d %6.2f:1" % (
            part, s["to_benign"], s["dropped"], s["kept_malware"], s["rat_unknown"],
            s["after_benign"], s["after_malware"], s["after_total"], ratio))
    print("-" * 80)
    print("Tong %s: %d -> benign | %d loai (vung xam)" % (prefix, gb, gd))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--prefixes", nargs="+", default=["split", "sweep"],
                    help="Bo du lieu can lam sach (mac dinh: ca split va sweep).")
    args = ap.parse_args()

    vt = load_vt()
    print("VT verdicts: %d hash" % len(vt))
    for prefix in args.prefixes:
        process_prefix(prefix, vt, args.preview)
    if args.preview:
        print("\n[PREVIEW] chua ghi gi.")
    else:
        print("\nDa ghi *_clean_{train,val,test}.csv (ban goc giu nguyen).")
        print("Config: split_prefix: split_clean  (detect)  |  sweep_clean  (luoi)")


if __name__ == "__main__":
    main()
