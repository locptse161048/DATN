# CLAUDE.md

Tài liệu định hướng cho Claude (và người làm) khi làm việc trên dự án này. Đọc file này trước khi thực hiện bất kỳ tác vụ nào.

## 1. Tổng quan đồ án

- **Tên đề tài (EN):** Malware Detection using Image-based Deep Learning Techniques
- **Tên đề tài (VI):** Phát hiện mã độc bằng kỹ thuật học sâu dựa trên biểu diễn ảnh
- **Sinh viên:** Phạm Tuấn Lộc — ngành An toàn thông tin, Đại học FPT TP.HCM (năm 4)
- **Loại:** Đồ án tốt nghiệp (DATN)
- **Ý tưởng cốt lõi:** Đọc chuỗi bytes của file PE → chuyển thành ảnh 3 kênh composite (grayscale + entropy-byte + tỉ lệ ASCII), **cả 3 kênh sinh từ chuỗi byte** → dùng CNN (deep learning) để **phát hiện mã độc** (benign vs malware) và phân loại họ.

### Giả thuyết nghiên cứu
File benign và malware (và các họ malware khác nhau) khi biểu diễn dưới dạng ảnh byte có **cấu trúc texture phân biệt được**; CNN học các đặc trưng texture này để phát hiện/phân loại mà không cần dịch ngược (disassembly) hay chạy động (dynamic analysis).

## 2. Bài toán & dataset

### Bài toán
- **CHÍNH — Phát hiện nhị phân:** benign vs malware (đúng tên đề tài). Tập **detection** cân bằng **1.5:1** (`detect_subset.csv` — cap RAT & Winwebsec).
- **PHỤ — Phân loại họ:** dùng **labels.csv đầy đủ** (RAT + Winwebsec nguyên gốc). **RAT gộp thành 1 nhóm** (phân biệt với các họ khác). **Hành vi** suy từ họ qua bảng tra family→behavior, KHÔNG train model hành vi riêng.

### Hai tập từ một nguồn raw (không phá hủy)
| Tập | File | Dùng cho |
|-----|------|----------|
| Đầy đủ | `data/interim/labels.csv` | phân loại họ (RAT/Winwebsec nguyên gốc) |
| Detection 1.5:1 | `data/interim/detect_subset.csv` | phát hiện nhị phân |
| Hợp lệ để train | `data/interim/valid_*.csv` | lọc min/max + cờ `res_eligible` (≥448² cho sweep) |

> **Số liệu thực tế (2026-06-28):** 27,340 PE duy nhất = 21,511 malware + 5,829 benign. Tập detection ≈ 8,743 malware + 5,829 benign (1.5:1).
>
> **Hai thí nghiệm dùng tập khác nhau (đừng nhầm):** *Phát hiện* (chính) dùng **toàn bộ** ~14,547 mẫu, chỉ ở **224**. *Resolution sweep* (luận điểm B) chỉ dùng **`res_eligible`** (native ≥448², ~7,806 mẫu) ở **CẢ 224/336/448 với cùng một tập** để so sánh công bằng. KHÔNG so 14,547@224 với 7,806@336. Ảnh 336/448 vì thế ít hơn 224 là **đúng thiết kế**.

### Dataset (PE thô — KHÔNG dùng Malimg, KHÔNG dùng BIG2015)
| Vai trò | Nguồn | Ghi chú |
|---------|-------|---------|
| Malware | **figshare 6635642** (8.970 PE, 5 loại) | có sẵn benign kèm theo; verify VirusTotal |
| Malware | **MalwareBazaar** (abuse.ch) | kéo qua API theo `signature` (=họ); co giãn số lượng |
| Malware | **Ultimate-RAT-Collection** | ~500+ builder RAT; nhãn = tên thư mục; xử lý trong VM cô lập |
| Benign | **figshare benign** (1.000) + **Win10 `.dll/.bin`** (VMware) + phần mềm đa nguồn | **benign là lớp khan hiếm** → phải đa dạng nguồn để chống thiên lệch |

> **Lưu ý quan trọng:** tất cả là **PE thô đầy đủ header** (đồng nhất định dạng). Benign phải **đa dạng nguồn** — nếu benign chỉ là file Win10 sạch còn malware từ kho khác, model dễ học "nguồn dữ liệu" thay vì tính độc hại (bẫy thiên lệch nguồn). Không trộn dữ liệu defanged (kiểu BIG2015) vào đây.

## 3. Quyết định kỹ thuật đã chốt

| Hạng mục | Lựa chọn |
|----------|----------|
| Framework | **PyTorch** (+ torchvision), **timm** cho model hiện đại |
| Mô hình | Transfer learning: **VGG16**, **ResNet50**, **DenseNet121** (pretrained ImageNet) + **ConvNeXt-Tiny** (timm); tùy chọn ViT/Swin, CNN custom |
| Kênh ảnh | **3 kênh composite** (KHÔNG nhân bản), **cả 3 từ chuỗi byte**: k1=grayscale, k2=entropy (cửa sổ byte liền kề), k3=tỉ lệ ký tự in được (printable ASCII, cửa sổ byte). Cả 3 căn chỉnh không gian. Pretrained ImageNet `in_chans=3` |
| Width ảnh | **CỐ ĐỊNH = 448** (chốt sau EDA 2026-06-28; = độ phân giải lớn nhất → 224/336 là downsample thật, không thông tin giả). Bỏ file < 4 KB; đọc tối đa 30 MB/file. height = ceil(len/width) |
| Độ phân giải | Đa kích thước **224 / 336 / 448** (`img_size` config-driven) — **luận điểm chính 2** |
| Đánh giá | Accuracy, Precision/Recall/F1, **ROC-AUC**, Confusion Matrix; split chống rò rỉ |
| Hướng nâng cao | **XAI** (Grad-CAM/HiResCAM) trên model tốt nhất; tùy chọn robustness FGSM |
| Ngôn ngữ | Python 3.10+ |

> **Hai luận điểm chính (co-primary, song song)** — chi tiết: `docs/EXPERIMENTS.md`:
> - **A — Ảnh 3-kênh composite:** gray + entropy-byte + ASCII-ratio (đều từ chuỗi byte) mang 3 góc nhìn khác nhau (cấu trúc / độ ngẫu nhiên / mật độ text). Ablation `gray vs +entropy vs +ascii vs full vs gray×3` chứng minh các kênh **thực sự thêm thông tin**, khác nhân bản kênh.
> - **B — Hiệu quả độ phân giải (H1):** chứng minh **224² đạt accuracy xấp xỉ/nhỉnh hơn 336²/448² nhưng rẻ hơn nhiều lần**. Yêu cầu: **≥3 seed + mean±std + kiểm định thống kê** + bảng **accuracy-vs-cost** (thời gian/GPU mem/FLOPs). Chạy trên bộ phát hiện PE thô (ảnh native lớn). CNN đổi `img_size` là chạy; ViT/Swin nội suy positional embedding (`img_size=` cho timm).

> **Về benchmark/SOTA:** bài toán **phát hiện dựa trên ảnh không có benchmark ảnh chuẩn** (EMBER/BODMAS là đặc trưng, không phải ảnh). Độ tin cậy dựa vào **phương pháp chặt** (split chống rò rỉ, chống bias nguồn, báo cáo P/R/F1/ROC-AUC), không dựa vào "gương". Khảo sát SOTA ảnh-mã-độc: `docs/SOTA_2026.md`.

## 4. Pipeline tổng thể

```
File PE thô (.exe/.dll/.bin)  —  malware (figshare/MalwareBazaar/RAT) + benign (figshare/Win10/đa nguồn)
   ▼
[Gán nhãn] dedup SHA-256 · VirusTotal verify · AVClass2 chuẩn hóa họ · gán benign/malware
   ▼
[Tiền xử lý] đọc bytes PE thô → ảnh xám (k1) + entropy-byte (k2) + tỉ lệ ASCII (k3), đều từ chuỗi byte → stack 3×H×W
   ▼
[Split] grouped/temporal chống rò rỉ · stratified · cân bằng lớp (benign khan hiếm)
   ▼
[Dataset/Dataloader] resize img_size∈{224,336,448}, normalize per-channel (stat train), augment
   ▼
[Model] in_chans=3 (pretrained ImageNet): VGG16 / ResNet50 / DenseNet121 / ConvNeXt-Tiny
   ▼
[Training] CrossEntropyLoss/BCE, AdamW, scheduler, early stopping
   ▼
[Đánh giá] Acc/P/R/F1, ROC-AUC, Confusion Matrix · ablation kênh · accuracy-vs-cost
   ▼
[XAI - tùy chọn] Grad-CAM minh họa vùng quyết định
   ▼
[Dashboard + Báo cáo]
```

### Quy ước bytes → ảnh 3 kênh composite
- **Kênh 1 (grayscale):** mỗi byte (0–255) = 1 pixel; **width CỐ ĐỊNH** (config `image_width`, chốt sau EDA), height = ceil(len(bytes)/width). Đọc **toàn bộ PE thô** (giữ header). Giữ native; chỉ pad 0 hàng cuối nếu lẻ. Width cố định → texture đồng nhất giữa các mẫu.
- **Kênh 2 (entropy):** entropy **TỪ CHUỖI BYTE** — chia byte thành cửa sổ **liên tiếp** (mặc định 256 byte), tính Shannon entropy mỗi khối (0–8 bit) rồi trải về đúng vị trí byte → chuẩn hóa 0–255, **cùng H×W** kênh 1. Đúng ngữ nghĩa entropy cho malware (phát hiện vùng packed/mã hóa). *Khác bản 2D cũ (cửa sổ 9×9 trên ảnh, trộn byte cách nhau `width`).*
- **Kênh 3 (tỉ lệ ASCII):** mỗi cửa sổ byte liên tiếp (mặc định 256) → tỉ lệ byte in được (0x20–0x7E) ∈ [0,1] → ×255 (tuyệt đối), **cùng H×W** kênh 1. Làm nổi vùng chuỗi/text/resource vs code/packed.
- Stack `[k1, k2, k3]` → `3×H×W`. Resize về `img_size` ở bước transform.
- **Normalize per-channel** bằng mean/std tính trên tập train (không dùng stat ImageNet RGB).
- **KHÔNG nhân bản kênh.** Chi tiết & ablation: `docs/EXPERIMENTS.md`.
- **Lưu trữ:** bản native (archive) + bản resize 224/336/448 để train. Chi tiết: `docs/ENVIRONMENT.md`.

## 5. Cấu trúc thư mục

```
DATN/
├── CLAUDE.md · README.md · requirements.txt · .gitignore
├── configs/              # YAML cho từng thí nghiệm
├── data/
│   ├── raw/              # malware/ (figshare,bazaar,rat) + benign/ — KHÔNG commit
│   ├── interim/          # nhãn, hash, split
│   ├── processed/        # ảnh 3 kênh đã resize + split
│   └── external/
├── src/
│   ├── preprocessing/    # đọc PE thô → ảnh 3 kênh, dedup, gán nhãn, split
│   ├── datasets/ · models/ · training/ · evaluation/ · utils/
├── scripts/             # collect.py, preprocess.py, train.py, evaluate.py
├── notebooks/ · experiments/ · results/ · reports/ · docs/ · tests/
```

## 6. Quy ước làm việc (cho Claude)

- **Reproducibility:** luôn set seed; ghi config mỗi run vào `experiments/`.
- **Config-driven:** đọc hyperparameter từ `configs/*.yaml`, không hard-code.
- **Không commit dữ liệu nặng / mẫu malware:** `data/raw/`, checkpoints, logs trong `.gitignore`.
- **Đặt tên run:** `{task}_{model}_{size}_{ngày}` (vd `detect_resnet50_224_20260625`).
- **Chống rò rỉ:** dedup SHA-256; biến thể/họ không vắt qua train/test (grouped split).
- **An toàn:** xử lý malware (figshare/RAT/bazaar) trong **VM cô lập**, chỉ đọc bytes, không chạy.
- **Ngôn ngữ:** tiếng Việt; code/comment có thể tiếng Anh.
- **GPU:** chạy được cả CPU lẫn GPU.
- **Phân vai môi trường:** xử lý/sinh ảnh trên **máy local (i9, trong VM cô lập)**; train trên **local RTX 4060 8GB** (việc nhẹ/224, nhiều seed) + **Google Colab** (việc nặng/448, song song). Chi tiết: `docs/ENVIRONMENT.md`.

## 7. Tiêu chí thành công

- Pipeline PE thô → ảnh 3 kênh → phát hiện nhị phân chạy end-to-end.
- So sánh ≥ 4 model (VGG16, ResNet50, DenseNet121, ConvNeXt-Tiny); báo cáo Acc/P/R/F1/ROC-AUC + confusion matrix.
- Chứng minh 2 luận điểm: ablation kênh composite + hiệu quả độ phân giải 224².
- Split chống rò rỉ + kiểm tra thiên lệch nguồn; kết quả tái lập (cùng seed).
- (Phụ) phân loại họ top-N + bảng family→behavior.

## 8. Trạng thái hiện tại

> Cập nhật **2026-06-25**: chốt pivot sang **phát hiện nhị phân trên PE thô** (figshare + MalwareBazaar + RAT + benign tự thu); **bỏ Malimg & BIG2015**. Giữ 2 luận điểm (composite, độ phân giải) + nhánh phụ phân loại họ. Chưa tải dữ liệu, chưa viết phần lớn code.

- [x] Khung dự án & tài liệu
- [x] Khảo sát SOTA (`docs/SOTA_2026.md`)
- [x] Thu thập dữ liệu + dedup + gán nhãn (figshare+bazaar+RAT+benign) → labels.csv, detect_subset.csv (1.5:1), valid_*.csv
- [x] EDA + chốt `image_width=448` + lọc outlier + kiểm tra bias (S1.4)
- [~] Pipeline PE thô → ảnh 3 kênh (ĐANG LÀM — Giai đoạn 2)
- [ ] Dataset/DataLoader + split chống rò rỉ
- [ ] Huấn luyện + 2 luận điểm
- [ ] Đánh giá & so sánh
- [ ] (Phụ) phân loại họ + (tùy chọn) XAI/robustness
- [ ] Viết báo cáo DATN

> Lộ trình: `docs/ROADMAP.md` · Task: `docs/BACKLOG.md` · Thí nghiệm: `docs/EXPERIMENTS.md` · Môi trường: `docs/ENVIRONMENT.md` · SOTA: `docs/SOTA_2026.md`.
