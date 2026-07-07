# DATA_COLLECTION.md
# Thu thập dữ liệu — Giai đoạn 1

> ⚠️ **An toàn trên hết.** figshare/MalwareBazaar/RAT là **mã độc thật**. Toàn bộ thao tác
> tải/giải nén/đọc bytes phải trong **Kali VM cô lập**. **KHÔNG mở file, KHÔNG thực thi.**
> Chụp **snapshot** VM trước mỗi bước giải nén lớn.

---

## Kết quả thu thập thực tế

> Cập nhật: 2026-06-28 — Đã xác minh qua `check_duplicates.py`
> Tổng PE duy nhất (SHA-256): **27,340** | Malware: **21,511** | Benign: **6,575**

### Malware

| # | Nguồn | Họ (Family) | Số file PE | Ghi chú |
|---|-------|-------------|-----------|---------|
| 1 | **figshare 6635642** | Locker, Mediyes, Winwebsec, Zbot, Zeroaccess (5 họ) | **8,970** | PE thô đầy đủ header; gộp train+test gốc |
| 2 | **MalwareBazaar** (abuse.ch) | AgentTesla, Formbook, RedLineStealer, Emotet, Mirai, Heodo, njrat, RemcosRAT, Trickbot, SnakeKeylogger (10 họ) | **1,035** | Tải 1,824 file; lọc MZ magic còn 1,035 PE |
| 3 | **Ultimate-RAT-Collection** | LiberiumRat, XWorm, NjRat và 200+ họ RAT khác | **11,506** | Builder RAT; đã loại 7 .NET DLL trùng với benign |
| | **Tổng malware** | | **21,511** | Sau dedup SHA-256 |

**Top họ RAT (Ultimate-RAT-Collection):**
LiberiumRat (977), XWorm (859), NjRat (412), và 200+ họ khác.

---

### Benign

| # | Nguồn | Máy thu thập | Thư mục đích | Số file PE |
|---|-------|--------------|-------------|-----------|
| 1 | **figshare 6635642** (benign đi kèm) | Kali VM | `data/raw/benign/figshare/` | **988** |
| 2 | **Windows System32** | Win10 Pro VMware | `data/raw/benign/win10_system32/` | **1,999** |
| 3 | **Windows SysWOW64** | Win10 Pro VMware | `data/raw/benign/win10_syswow64/` | **1,220** |
| 4 | **Windows WinSxS** | Win10 Pro VMware | `data/raw/benign/win10_winsxs/` | **576** |
| 5 | **Program Files** (Win10 VM) | Win10 Pro VMware | `data/raw/benign/program_files/` | **250** |
| 6 | **Program Files** (máy host) | Windows host | `data/raw/benign/program_files_host/` | **1,207** |
| 7 | **Sysinternals Suite** (Microsoft) | Windows host | `data/raw/benign/sysinternals/` | **151** |
| 8 | **NirCmd** (Nirsoft) | Windows host | `data/raw/benign/nirsoft_sysinternals/` | **153** |
| 9 | **Notepad++** | Windows host | `data/raw/benign/notepadpp/` | **7** |
| 10 | **PuTTY** | Windows host | `data/raw/benign/putty/` | **6** |
| 11 | **Misc** (opensource_apps, portable_apps, winrar, nircmd) | Windows host | các thư mục tương ứng | **18** |
| | **Tổng benign** | | | **6,575** |

**Tỉ lệ malware:benign ≈ 3.3:1** (nằm trong ngưỡng chấp nhận ≤ 4:1).

> **Xử lý conflict:** 7 .NET runtime DLL (Newtonsoft.Json, System.Buffers, System.Memory,
> System.Numerics.Vectors, System.Runtime.CompilerServices.Unsafe, System.Text.Encodings.Web,
> System.Resources.Extensions) xuất hiện trong cả RAT và benign → đã xóa khỏi `malware/RAT/`,
> giữ trong benign. `label_conflicts.csv` hiện rỗng (0 conflict).

---

### Phân bổ benign/malware trong `split_*.csv` (split phát hiện — headline, toàn bộ mẫu hợp lệ)

> Cập nhật: 2026-07-08. Đây là **split phát hiện nhị phân dùng cho kết quả headline** (`full @224`, xem `CLAUDE.md` §2), khác với `sweep_*.csv` (chỉ gồm `res_eligible` ≥448², dùng riêng cho lưới hợp nhất 5×3 — xem `docs/EXPERIMENTS.md`). Đếm trực tiếp từ 3 file, cột `label` (0 = benign, 1 = malware).

| Split | Benign | Malware | Tổng | Tỉ lệ malware:benign |
|-------|:------:|:-------:|:----:|:---------------------:|
| `split_train.csv` | 4.066 | 6.115 | 10.181 | 1,50:1 |
| `split_val.csv`   | 872   | 1.311 | 2.183  | 1,50:1 |
| `split_test.csv`  | 872   | 1.311 | 2.183  | 1,50:1 |
| **Tổng**          | **5.810** | **8.737** | **14.547** | **1,50:1** |

---

## Pipeline tổng thể

```
[Bước 1] figshare 6635642     → data/raw/malware/figshare/ + data/raw/benign/figshare/
[Bước 2] MalwareBazaar API    → data/raw/malware/MalwareBazaar/
[Bước 3] Ultimate-RAT         → data/raw/malware/RAT/
[Bước 4] Benign tự thu thập   → data/raw/benign/<source_tag>/          ← thủ công
[Bước 5] Checksum & dedup     → data/interim/checksums.csv + duplicates.csv
[Bước 6] VirusTotal verify    → data/interim/vt_report.csv + vt_suspicious.csv
[Bước 7] Gán nhãn             → data/interim/labels.csv
```

> `collect_all.py` tự động hóa bước 1–3. Bước 4 luôn thủ công. Bước 5–7 chạy riêng sau.

---

## 0. Chuẩn bị Kali VMware

### 0.1 Cài đặt VMware

1. Tạo VM Kali Linux (≥ 4 GB RAM, ≥ 60 GB disk).
2. Vào **VM → Settings → Options**:
   - **Shared Folders** → Disabled
   - **Guest Isolation** → tắt *drag and drop* và *copy and paste*
3. Chụp **snapshot sạch** sau khi cài xong.
4. Mạng: dùng **NAT** khi tải; sau khi xong chuyển **Host-Only**.

### 0.2 Cài dependencies trong Kali

```bash
sudo apt update && sudo apt install -y \
    python3 python3-pip python3-venv \
    git p7zip-full unzip tmux

python3 -m venv ~/datn-env
source ~/datn-env/bin/activate

cd ~/DATN
pip install -r requirements.txt
# Gồm: requests pyzipper pyyaml tqdm pefile scikit-image
```

### 0.3 Cấu trúc thư mục

```
~/DATN/
├── data/                          # Toàn bộ dữ liệu (KHÔNG commit git — đã .gitignore)
│   ├── raw/                       # Dữ liệu gốc, giữ nguyên — KHÔNG sửa/xóa
│   │   ├── malware/               #   PE độc hại (chỉ đọc bytes, không chạy)
│   │   │   ├── figshare/          #     Locker/ Mediyes/ Winwebsec/ Zbot/ Zeroaccess/
│   │   │   ├── MalwareBazaar/     #     AgentTesla/ Formbook/ ... (thư mục = họ)
│   │   │   └── RAT/               #     XWorm/ NjRat/ LiberiumRat/ ... (thư mục = họ con)
│   │   └── benign/                #   PE sạch, nhiều nguồn (chống thiên lệch)
│   │       ├── figshare/  win10_system32/  win10_syswow64/  win10_winsxs/
│   │       ├── program_files/  program_files_host/
│   │       └── nirsoft_sysinternals/  opensource_apps/  ...
│   ├── interim/                   # Trung gian: checksums.csv, labels.csv (ĐẦY ĐỦ),
│   │                              #   detect_subset.csv (tập 1.5:1), split_*.csv
│   └── processed/                 # Ảnh PNG đã sinh (AN TOÀN để đưa ra host/Colab)
│
├── src/                           # MÃ NGUỒN tái sử dụng (thư viện của dự án)
│   ├── preprocessing/             #   Đọc PE→ảnh, dedup, gán nhãn, sinh kênh
│   │   ├── labeling.py            #     dedup SHA-256 + gán benign/malware + gộp RAT → labels.csv
│   │   ├── bytes_to_image.py      #     đọc PE thô → ảnh xám (kênh 1), width cố định
│   │   └── channels.py            #     entropy-byte + tỉ lệ ASCII + ghép 3 kênh (Giai đoạn 2)
│   ├── datasets/                  #   Dataset & DataLoader PyTorch (Giai đoạn 3)
│   ├── models/                    #   Khởi tạo VGG16/ResNet50/DenseNet121/ConvNeXt (GĐ4)
│   ├── training/                  #   Vòng lặp train, loss, scheduler (GĐ5)
│   ├── evaluation/                #   Metrics, confusion matrix, ROC (GĐ6)
│   └── utils/                     #   seed, config loader, logger
│
├── scripts/                       # ĐIỂM CHẠY (CLI) — gọi code trong src/
│   ├── collect_figshare.py        #   tải figshare 6635642
│   ├── collect_malwarebazaar.py   #   tải MalwareBazaar theo họ (API)
│   ├── collect_rat.py             #   clone & tổ chức Ultimate-RAT-Collection
│   ├── collect_benign.py          #   gom PE sạch từ thư mục nguồn
│   ├── collect_all.py             #   orchestrator bước 1–3
│   ├── check_duplicates.py        #   kiểm tra SHA-256 & trùng lặp
│   ├── verify_virustotal.py       #   xác minh mẫu qua VirusTotal
│   ├── make_detection_subset.py   #   tạo tập detection 1.5:1 (không phá tập đầy đủ)
│   ├── preprocess.py              #   sinh ảnh 3 kênh toàn dataset (Giai đoạn 2)
│   ├── train.py  ·  evaluate.py   #   huấn luyện / đánh giá (GĐ5–6)
│   └── balance_rat.py             #   [DEPRECATED — di chuyển file, ĐỪNG dùng]
│
├── configs/                       # Cấu hình YAML (đọc bởi script, không hard-code)
│   └── data.yaml                  #   nguồn dữ liệu, image_width, tỉ lệ split
│
├── notebooks/                     # EDA & thử nghiệm nhanh (01_eda.ipynb ...)
├── experiments/                   # Output + config mỗi lần train (tái lập)
├── results/                       # figures/, metrics/, checkpoints/, logs/
├── reports/                       # Nội dung báo cáo DATN
├── tests/                         # Unit test (preprocessing, dataset)
└── requirements.txt               # Thư viện Python
```

> **Mẹo chạy:** `src/` là thư viện (import), `scripts/` là điểm chạy. Gọi script bằng đường
> dẫn từ gốc dự án, vd `python src/preprocessing/labeling.py` hoặc `python scripts/collect_all.py`.
> Nếu muốn dùng `python -m src.preprocessing.labeling` thì cần `touch src/__init__.py src/preprocessing/__init__.py`.

---

## 1. Malware — figshare 6635642

**Kết quả:** 8,970 malware PE (5 họ) + 1,000 benign.

```bash
cd ~/DATN
source ~/datn-env/bin/activate
python scripts/collect_figshare.py --out data
```

Script tải archive qua figshare API, giải nén và sắp xếp vào:
- `data/raw/malware/figshare/<Locker|Mediyes|Winwebsec|Zbot|Zeroaccess>/`
- `data/raw/benign/figshare/`

---

## 2. Malware — MalwareBazaar (API theo họ)

**Kết quả:** 1,824 PE file từ 10 họ (AgentTesla 193, Formbook 199, RedLineStealer 31, ...).

```bash
# 1. Đăng ký tài khoản tại https://auth.abuse.ch/ → Profile → Generate Key
export MB_API_KEY="<key thật từ auth.abuse.ch>"
echo 'export MB_API_KEY="..."' >> ~/.bashrc

# 2. Tải mẫu (chạy trong tmux vì mất vài giờ)
tmux new -s bazaar
cd ~/DATN && source ~/datn-env/bin/activate
python scripts/collect_malwarebazaar.py --config configs/data.yaml --extract
# Ctrl+B D để detach
```

→ `data/raw/malware/MalwareBazaar/<signature>/`

> Lưu ý: MalwareBazaar cũng trả về file `.js/.vbs/.hta` (dropper) — labeling.py tự lọc qua MZ magic.

---

## 3. Malware — Ultimate-RAT-Collection

**Kết quả:** 11,514 PE file từ 230+ họ RAT.

> ⏱ Ước tính: 3–5 tiếng. Bắt buộc dùng **tmux**.

```bash
tmux new -s rat
cd ~/DATN && source ~/datn-env/bin/activate
python scripts/collect_rat.py \
    --clone \
    --repo-dir data/tmp/Ultimate-RAT-Collection \
    --out data/raw/malware/RAT \
    --extract-7z
# Ctrl+B D để detach
```

Theo dõi tiến trình:
```bash
find ~/DATN/data/raw/malware/RAT -type f | wc -l
tmux attach -t rat
```

> Builder RAT (không phải payload triển khai) — ghi rõ trong báo cáo.

---

## 4. Benign — Thu thập thực tế

> Mục tiêu: đa dạng nguồn để chống thiên lệch (source bias).

### 4.1 figshare benign

Tự động từ Bước 1 → `data/raw/benign/figshare/` (1,000 file).

### 4.2 Windows System Files (Win10 Pro VMware)

Chạy trên **PowerShell của Win10 VM** (không cần Python):

```powershell
# System32 — 2,000 file
$count = 0; $out = "C:\benign_output\win10_system32"
New-Item -ItemType Directory -Force -Path $out | Out-Null
Get-ChildItem "C:\Windows\System32" -Recurse -File -Include "*.dll","*.exe","*.sys" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($count -ge 2000) { return }
    try { $bytes = [System.IO.File]::ReadAllBytes($_.FullName)[0..1]
    if ($bytes[0] -eq 0x4D -and $bytes[1] -eq 0x5A) {
        Copy-Item $_.FullName "$out\$($_.Name)" -ErrorAction SilentlyContinue; $count++
    }} catch {}
}

# SysWOW64 — 1,000 file
$count = 0; $out = "C:\benign_output\win10_syswow64"
New-Item -ItemType Directory -Force -Path $out | Out-Null
Get-ChildItem "C:\Windows\SysWOW64" -Recurse -File -Include "*.dll","*.exe","*.sys" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($count -ge 1000) { return }
    try { $bytes = [System.IO.File]::ReadAllBytes($_.FullName)[0..1]
    if ($bytes[0] -eq 0x4D -and $bytes[1] -eq 0x5A) {
        Copy-Item $_.FullName "$out\$($_.Name)" -ErrorAction SilentlyContinue; $count++
    }} catch {}
}

# WinSxS — 1,000 file (dùng hash để tránh trùng tên)
$count = 0; $out = "C:\benign_output\win10_winsxs"
New-Item -ItemType Directory -Force -Path $out | Out-Null
Get-ChildItem "C:\Windows\WinSxS" -Recurse -File -Include "*.dll","*.exe" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($count -ge 1000) { return }
    try { $bytes = [System.IO.File]::ReadAllBytes($_.FullName)[0..1]
    if ($bytes[0] -eq 0x4D -and $bytes[1] -eq 0x5A) {
        $hash = (Get-FileHash $_.FullName -Algorithm MD5).Hash.Substring(0,6)
        Copy-Item $_.FullName "$out\$($_.BaseName)_$hash$($_.Extension)" -Force -ErrorAction SilentlyContinue; $count++
    }} catch {}
}
```

### 4.3 Program Files (máy host Windows)

Chạy trên **PowerShell của máy host**, lưu thẳng vào D:\DATN:

```powershell
$count = 0; $out = "D:\DATN\data\raw\benign\program_files_host"
New-Item -ItemType Directory -Force -Path $out | Out-Null
Get-ChildItem "C:\Program Files" -Recurse -File -Include "*.dll","*.exe" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($count -ge 1500) { return }
    try { $bytes = [System.IO.File]::ReadAllBytes($_.FullName)[0..1]
    if ($bytes[0] -eq 0x4D -and $bytes[1] -eq 0x5A) {
        Copy-Item $_.FullName "$out\$($_.Name)" -Force -ErrorAction SilentlyContinue; $count++
    }} catch {}
}
```

### 4.4 Sysinternals Suite + NirCmd (Microsoft tools)

```powershell
# Tải trên máy host
wget https://download.sysinternals.com/files/SysinternalsSuite.zip -OutFile SysinternalsSuite.zip
Expand-Archive SysinternalsSuite.zip -DestinationPath C:\benign_output\sysinternals\

$count = 0; $out = "C:\benign_output\nirsoft_sysinternals"
New-Item -ItemType Directory -Force -Path $out | Out-Null
Get-ChildItem "C:\benign_output\sysinternals","C:\benign_output\nircmd" -Recurse -File -Include "*.dll","*.exe" -ErrorAction SilentlyContinue | ForEach-Object {
    try { $bytes = [System.IO.File]::ReadAllBytes($_.FullName)[0..1]
    if ($bytes[0] -eq 0x4D -and $bytes[1] -eq 0x5A) {
        $hash = (Get-FileHash $_.FullName -Algorithm MD5).Hash.Substring(0,6)
        Copy-Item $_.FullName "$out\$($_.BaseName)_$hash$($_.Extension)" -Force -ErrorAction SilentlyContinue; $count++
    }} catch {}
}
```

### 4.5 Open-source apps (Notepad++, PuTTY)

```powershell
wget "https://github.com/notepad-plus-plus/notepad-plus-plus/releases/download/v8.7.1/npp.8.7.1.portable.x64.zip" -OutFile "C:\benign_output\notepadpp.zip"
wget "https://the.earth.li/~sgtatham/putty/latest/w64/putty.zip" -OutFile "C:\benign_output\putty.zip"
Expand-Archive "C:\benign_output\notepadpp.zip" -DestinationPath "C:\benign_output\notepadpp\" -Force
Expand-Archive "C:\benign_output\putty.zip" -DestinationPath "C:\benign_output\putty\" -Force
```

### 4.6 Chuyển benign từ Win10 VM sang Kali

Trên Win10 VM — mở HTTP server:
```powershell
cd C:\benign_output
python -m http.server 8080
```

Trên Kali:
```bash
cd ~/DATN/data/raw/benign/
wget -r -np -nH --cut-dirs=1 --no-clobber http://<win10-vm-ip>:8080/
```

---

## 5. Checksum & kiểm tra trùng lặp

```bash
cd ~/DATN && source ~/datn-env/bin/activate
python scripts/check_duplicates.py \
    --malware-dir data/raw/malware \
    --benign-dir  data/raw/benign \
    --out-dir     data/interim
```

| File output | Nội dung |
|-------------|---------|
| `data/interim/checksums.csv` | sha256 + path + label + source + size |
| `data/interim/duplicates.csv` | File trùng hash |
| `data/interim/label_conflicts.csv` | File vừa malware vừa benign (**phải xử lý**) |

---

## 6. Xác minh qua VirusTotal API

> Free tier: 4 req/phút, 500/ngày → script tự sleep 15s/request.
> Với ~22,000 mẫu → ưu tiên query malware trước.

```bash
export VT_API_KEY="<key từ virustotal.com>"
echo 'export VT_API_KEY="..."' >> ~/.bashrc

cd ~/DATN && source ~/datn-env/bin/activate

# Chỉ query malware trước (tiết kiệm quota)
python scripts/verify_virustotal.py \
    --checksums data/interim/checksums.csv \
    --only-malware \
    --api-key $VT_API_KEY
```

| Verdict | Ý nghĩa | Hành động |
|---------|---------|-----------|
| `confirmed_malware` | ≥ 5 engine detect | ✓ Giữ |
| `low_detection` | 1–4 engine detect | Xem xét, có thể giữ |
| `clean_but_labeled_malware` | 0 engine detect | ⚠ Loại bỏ |
| `confirmed_clean` | 0–2 engine detect | ✓ Giữ |
| `detected_as_malware` | > 2 engine detect | ⚠ Loại khỏi benign |

---

## 7. Gán nhãn

```bash
cd ~/DATN && source ~/datn-env/bin/activate
python -m src.preprocessing.labeling \
    --malware-dir data/raw/malware \
    --benign-dir  data/raw/benign \
    --out         data/interim/labels.csv
```

→ Dedup SHA-256 toàn cục, gán `label` (0=benign / 1=malware), ghi `labels.csv`.

---

## 8. Checklist trước khi sang Giai đoạn 2

- [ ] `checksums.csv` đã sinh; `label_conflicts.csv` rỗng hoặc đã xử lý.
- [ ] `vt_report.csv` đã có; không còn `detected_as_malware` trong benign.
- [ ] `labels.csv` có đủ cột; mỗi sha256 xuất hiện 1 lần.
- [ ] Tỉ lệ benign/malware ≤ 1:4; benign ≥ 3 source tag khác nhau.
- [ ] Snapshot VM còn nguyên.
- [ ] EDA (S1.4): phân bố kích thước file → chốt `image_width`.
