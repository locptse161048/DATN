"""
vm_verify_files_kali.py — Kiểm chứng NHÃN bằng FILE THẬT, chạy TRONG KALI (Linux)
================================================================================
Bản Linux/Kali của vm_verify_files.ps1. Với các mẫu RAT nghi nhãn sai, phân tích
file GỐC để biết nhãn 'malware' có đúng không — KHÔNG chạy file, KHÔNG upload.

VÌ SAO AN TOÀN TRÊN KALI: đây là file thực thi WINDOWS (PE). Trên Linux, kernel
không thể thực thi định dạng PE => kể cả lỡ tay cũng không chạy được. Script chỉ:
  * ĐỌC byte tĩnh (pefile: có phải .NET, GUI/console)
  * Kiểm CHỮ KÝ SỐ Authenticode (signify)
  * Quét bằng ClamAV CỤC BỘ (clamscan, offline)
KHÔNG thực thi, KHÔNG upload, KHÔNG sửa/di chuyển file. Đầu ra: 1 CSV metadata
(an toàn mang ra host).

Ba tín hiệu độc lập -> phán định:
  1. ClamAV phát hiện                 -> NHÃN ĐÚNG (malware thật)
  2. Chữ ký số hợp lệ (nhà phát hành)  -> NHÃN SAI (gần như chắc sạch)
  3. .NET + GUI, không dấu hiệu độc    -> nghi BUILDER (không phải payload)

CÀI (trong Kali):
    sudo apt install clamav
    sudo freshclam                 # tải CSDL virus (bắt buộc cho clamscan)
    pip install pefile signify     # signify để đọc chữ ký; pefile để đọc PE

CÁCH DÙNG:
    python3 vm_verify_files_kali.py \
        --hashes rat_all_hashes.txt \
        --labels data/interim/labels.csv \
        --out vm_verify_rat_kali.csv
    # nếu path trong labels.csv không còn đúng, thêm:  --search-root /duong/dan/RAT
    # bỏ quét ClamAV cho nhanh (chỉ chữ ký + PE):        --skip-clamav
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

try:
    import pefile
except ImportError:
    pefile = None

try:
    from signify.authenticode import SignedPEFile
except ImportError:
    SignedPEFile = None


def load_hashes(path: Path) -> list[str]:
    return [ln.strip().lower() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def load_meta(labels_csv: Path, wanted: set[str]) -> dict[str, dict]:
    meta = {}
    with open(labels_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            h = r["sha256"].lower()
            if h in wanted:
                meta[h] = {"path": r.get("path", ""), "family": r.get("family", ""),
                           "source": r.get("source", "")}
    return meta


def find_file(path_str: str, sha: str, search_root: Path | None) -> Path | None:
    """Tìm file theo path trong labels.csv; nếu mất, dò lại trong search_root."""
    if path_str:
        p = Path(path_str)
        if p.exists():
            return p
        # thử tên file dưới search_root
    if search_root and search_root.exists():
        # nhiều pipeline lưu file theo tên = sha256
        for cand in (search_root / sha, search_root / f"{sha}.bin", search_root / f"{sha}.exe"):
            if cand.exists():
                return cand
        # dò theo tên gốc
        if path_str:
            name = Path(path_str).name
            hit = next(search_root.rglob(name), None)
            if hit:
                return hit
    return None


def pe_info(path: Path) -> dict:
    """.NET? GUI/console? — chỉ đọc, không chạy."""
    info = {"is_pe": False, "is_dotnet": False, "subsystem": ""}
    if pefile is None:
        return info
    try:
        pe = pefile.PE(str(path), fast_load=True)
        info["is_pe"] = True
        sub = getattr(pe.OPTIONAL_HEADER, "Subsystem", None)
        info["subsystem"] = {2: "GUI", 3: "Console"}.get(sub, f"other({sub})")
        # Data directory 14 = CLR/.NET
        try:
            dd = pe.OPTIONAL_HEADER.DATA_DIRECTORY[14]
            info["is_dotnet"] = dd.VirtualAddress != 0 and dd.Size != 0
        except (IndexError, AttributeError):
            pass
        pe.close()
    except Exception:
        pass
    return info


def sig_info(path: Path) -> dict:
    """Chữ ký số Authenticode. status='valid' + signer = bằng chứng SẠCH mạnh."""
    out = {"sig_status": "none", "sig_signer": ""}
    if SignedPEFile is None:
        out["sig_status"] = "signify_missing"
        return out
    try:
        with open(path, "rb") as f:
            spe = SignedPEFile(f)
            signed = False
            signer = ""
            for signed_data in spe.signed_datas:
                signed = True
                try:
                    cert = signed_data.signer_info.certificate
                    signer = getattr(cert.subject, "dn", "") or str(cert.subject)
                except Exception:
                    pass
                break
            if not signed:
                out["sig_status"] = "unsigned"
                return out
            out["sig_signer"] = signer[:120]
            # xác thực đầy đủ (chuỗi tin cậy). Lỗi => 'invalid'
            try:
                spe.verify()
                out["sig_status"] = "valid"
            except Exception as e:
                out["sig_status"] = f"invalid:{type(e).__name__}"
    except Exception as e:
        out["sig_status"] = f"error:{type(e).__name__}"
    return out


def clamav_scan_batch(paths: list[Path], batch_size: int = 300) -> dict[str, str]:
    """Quét ClamAV THEO LÔ -> path(str) -> 'clean' | tên virus.

    QUAN TRỌNG: mỗi lần gọi `clamscan`, ClamAV nạp lại toàn bộ CSDL virus (~15s).
    Gọi 1 lần/file với 11.5k file = ~48 GIỜ. Quét theo lô (dùng --file-list) thì
    CSDL chỉ nạp 1 lần cho cả lô -> giảm còn vài chục phút.
    (Nhanh hơn nữa: chạy daemon `clamd` rồi dùng `clamdscan`.)
    """
    import tempfile
    out: dict[str, str] = {}
    if not paths:
        return out
    total = len(paths)
    for i in range(0, total, batch_size):
        chunk = paths[i:i + batch_size]
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tf:
            tf.write("\n".join(str(p) for p in chunk))
            list_file = tf.name
        try:
            r = subprocess.run(
                ["clamscan", "--no-summary", "--stdout", f"--file-list={list_file}"],
                capture_output=True, text=True, timeout=3600)
            for line in r.stdout.splitlines():
                line = line.strip()
                if not line or ":" not in line:
                    continue
                path_part, res = line.rsplit(":", 1)
                res = res.strip()
                if res == "OK":
                    out[path_part.strip()] = "clean"
                elif res.endswith("FOUND"):
                    out[path_part.strip()] = res.replace("FOUND", "").strip()
        except FileNotFoundError:
            return {str(p): "no_clamav" for p in paths}
        except subprocess.TimeoutExpired:
            for p in chunk:
                out.setdefault(str(p), "timeout")
        except Exception:
            for p in chunk:
                out.setdefault(str(p), "error")
        finally:
            Path(list_file).unlink(missing_ok=True)
        print(f"  [ClamAV] {min(i + batch_size, total)}/{total} file đã quét")
    for p in paths:
        out.setdefault(str(p), "error")
    return out


def verdict_of(row: dict) -> str:
    clam = row["clamav"]
    detected = clam not in ("clean", "no_clamav", "error", "timeout", "")
    if detected:
        return "NHAN_DUNG (ClamAV phat hien)"
    if row["sig_status"] == "valid":
        return "NHAN_SAI (chu ky hop le -> sach)"
    if row["is_dotnet"] and row["subsystem"] == "GUI":
        return "NGHI_BUILDER (.NET GUI)"
    return "CHUA_KET_LUAN"


def main():
    ap = argparse.ArgumentParser(description="Kiểm chứng nhãn RAT bằng file thật trên Kali (S6.3).")
    ap.add_argument("--hashes", type=Path, required=True)
    ap.add_argument("--labels", type=Path, default=Path("data/interim/labels.csv"))
    ap.add_argument("--out", type=Path, default=Path("vm_verify_rat_kali.csv"))
    ap.add_argument("--search-root", type=Path, default=None,
                    help="Thư mục dò lại file nếu path trong labels.csv đã đổi.")
    ap.add_argument("--skip-clamav", action="store_true", help="Bỏ quét ClamAV (chỉ chữ ký + PE).")
    ap.add_argument("--batch-size", type=int, default=300,
                    help="Số file mỗi lô clamscan (CSDL virus chỉ nạp 1 lần/lô).")
    ap.add_argument("--limit", type=int, default=0, help="Chỉ xử lý N mẫu đầu (để test).")
    args = ap.parse_args()

    if pefile is None:
        print("[!] Thiếu pefile -> pip install pefile", file=sys.stderr)
    if SignedPEFile is None:
        print("[!] Thiếu signify -> pip install signify (bỏ qua kiểm chữ ký)", file=sys.stderr)

    wanted = load_hashes(args.hashes)
    if args.limit:
        wanted = wanted[:args.limit]
    wset = set(wanted)
    meta = load_meta(args.labels, wset)
    print(f"Cần kiểm: {len(wset)} | khớp labels.csv: {len(meta)}")

    # Nạp kết quả cũ nếu có -> chạy tiếp được (an toàn khi ngắt giữa chừng)
    done = {}
    if args.out.exists():
        with open(args.out, encoding="utf-8") as f:
            done = {r["sha256"]: r for r in csv.DictReader(f)}
        print(f"Đã có kết quả cũ: {len(done)} -> chỉ xử lý phần còn lại")

    rows = list(done.values())
    todo = [h for h in wanted if h not in done]
    print(f"Cần xử lý lần này: {len(todo)}")

    # --- Bước 1: định vị file ---
    located: dict[str, Path] = {}
    for h in todo:
        fp = find_file(meta.get(h, {}).get("path", ""), h, args.search_root)
        if fp:
            located[h] = fp
    print(f"Tìm thấy file: {len(located)}/{len(todo)}")

    # --- Bước 2: quét ClamAV THEO LÔ (CSDL chỉ nạp 1 lần/lô) ---
    clam: dict[str, str] = {}
    if not args.skip_clamav and located:
        print(f"Quét ClamAV theo lô ({args.batch_size} file/lô)...")
        clam = clamav_scan_batch(list(located.values()), args.batch_size)

    # --- Bước 3: PE + chữ ký cho từng file, rồi phán định ---
    for i, h in enumerate(todo, 1):
        m = meta.get(h, {})
        fp = located.get(h)
        row = {"sha256": h, "family": m.get("family", ""), "source": m.get("source", ""),
               "file_found": bool(fp), "is_pe": False, "is_dotnet": False, "subsystem": "",
               "sig_status": "", "sig_signer": "", "clamav": "", "verdict": ""}
        if not fp:
            row["verdict"] = "FILE_KHONG_TIM_THAY"
        else:
            pi = pe_info(fp)
            row.update({k: pi[k] for k in ("is_pe", "is_dotnet", "subsystem")})
            row.update(sig_info(fp))
            row["clamav"] = "skipped" if args.skip_clamav else clam.get(str(fp), "error")
            row["verdict"] = verdict_of(row)
        rows.append(row)

        if i % 200 == 0 or i == len(todo):
            print(f"  [{i}/{len(todo)}] phân tích PE+chữ ký...")
            _write(rows, args.out)   # ghi dần, ngắt giữa chừng không mất tiến độ

    _write(rows, args.out)
    _summary(rows)


def _write(rows, out: Path):
    cols = ["sha256", "family", "source", "file_found", "is_pe", "is_dotnet",
            "subsystem", "sig_status", "sig_signer", "clamav", "verdict"]
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})


def _summary(rows):
    from collections import Counter
    c = Counter(r["verdict"] for r in rows)
    print("\n=== TÓM TẮT PHÁN ĐỊNH ===")
    for v, n in c.most_common():
        print(f"  {v:<36} {n}")
    tot = len(rows)
    sai = sum(1 for r in rows if r["verdict"].startswith("NHAN_SAI"))
    dung = sum(1 for r in rows if r["verdict"].startswith("NHAN_DUNG"))
    print(f"\n  NHÃN SAI (chữ ký hợp lệ)  : {sai}/{tot}")
    print(f"  NHÃN ĐÚNG (ClamAV bắt)    : {dung}/{tot}")
    print("\n  Chỉ 'NHAN_SAI' và 'NHAN_DUNG' là KẾT LUẬN CHẮC.")
    print("  Đối chiếu thêm với VirusTotal (theo hash) để có 3 nguồn độc lập.")


if __name__ == "__main__":
    main()
