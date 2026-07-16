# BACKLOG — Danh sách task theo phiên làm việc

Nguồn chân lý cho tiến độ dự án. Mỗi task **gọn trong một phiên** để tối ưu context: một phiên chỉ cần đọc `CLAUDE.md` + đúng file ở mục *Input*.

**Trạng thái:** `TODO` · `DOING` · `BLOCKED` · `REVIEW` · `DONE`
**Ưu tiên:** P0 (chặn pipeline) · P1 (chính) · P2 (tùy chọn)
**DoD = Definition of Done** = tiêu chí chất lượng để task được tính `DONE`.

> Đề tài: **Phát hiện mã độc dựa trên ảnh** (nhị phân benign/malware — chính; phân loại họ — phụ). Dataset PE thô: figshare + MalwareBazaar + RAT + benign tự thu. **Không dùng Malimg/BIG2015.**
> Mỗi khi xong task: cập nhật trạng thái ở đây **và** tick trên `progress_dashboard.html`.

---

## Giai đoạn 1 — Thu thập & gán nhãn dữ liệu

### S1.1 — Thu thập malware (đa nguồn, trong VM cô lập) `[P0]` `TODO`
- **Input:** —.
- **Output:** `data/raw/malware/` từ figshare (8.970) + MalwareBazaar (API, theo `signature`) + Ultimate-RAT-Collection; `SOURCE.md` ghi nguồn/license.
- **DoD:** xử lý hoàn toàn trong **VM cô lập** (không chạy file); figshare giải nén đủ; MalwareBazaar kéo qua API theo họ (lưu kèm `signature` + `tags`); RAT lưu kèm tên họ (thư mục); ghi metadata (hash, nguồn, nhãn gốc) ra CSV.
- **Phụ thuộc:** —  ·  **Ước lượng:** 1–2 ngày. Xem `docs/ENVIRONMENT.md`.

### S1.2 — Thu thập benign đa nguồn `[P0]` `TODO`
- **Input:** —.
- **Output:** `data/raw/benign/` từ figshare benign (1.000) + Win10 `.dll/.bin` (VMware) + phần mềm hợp pháp đa dạng.
- **DoD:** **đa dạng nguồn** (nhiều phần mềm/bản Windows/trình biên dịch) để chống thiên lệch — KHÔNG chỉ DLL hệ thống; đủ số lượng cân bằng với malware; ghi metadata (hash, nguồn); chỉ lấy file PE hợp lệ.
- **Phụ thuộc:** —  ·  **Ước lượng:** 1–2 ngày.

### S1.3 — Dedup + gán nhãn + chuẩn hóa họ (AVClass2) `[P0]` `TODO`
- **Input:** S1.1, S1.2.
- **Output:** bảng nhãn thống nhất `data/interim/labels.csv` (path, sha256, label 0/1, family, source, first_seen nếu có).
- **DoD:** **dedup SHA-256** toàn bộ (loại trùng & gần trùng); gán benign/malware; **AVClass2** chuẩn hóa tên họ về 1 chuẩn (gom bí danh); đánh dấu họ "other" nếu < ngưỡng; ghi lại số lượng mỗi lớp/họ/nguồn.
- **Phụ thuộc:** S1.1, S1.2  ·  **Ước lượng:** 1 ngày.

### S1.4 — EDA + chốt `image_width` + kiểm tra thiên lệch `[P1]` `TODO`
- **Input:** `data/interim/labels.csv`, file PE thô.
- **Output:** `notebooks/01_eda.ipynb`.
- **DoD:** phân bố benign/malware + họ + nguồn; phân bố kích thước file → **chốt `image_width`** (mục tiêu height đa số ≥ 448); **kiểm tra thiên lệch nguồn** (vd kích thước/định dạng benign vs malware có tách biệt bất thường không); kết luận cân bằng & cách xử lý.
- **Phụ thuộc:** S1.3  ·  **Ước lượng:** 0.5 ngày.

---

## Giai đoạn 2 — Tiền xử lý PE thô → ảnh 3 kênh

### S2.1 — Utils nền tảng `[P0]` `TODO`
- **Input:** —.
- **Output:** `src/utils/` — `seed.py`, `config.py` (load YAML), `logger.py`.
- **DoD:** set seed tái lập; config loader đọc YAML; logger file+stdout; có test nhỏ.
- **Phụ thuộc:** —  ·  **Ước lượng:** 0.5 ngày.

### S2.2 — Đọc PE thô → ảnh xám (kênh 1) + test `[P0]` `TODO`
- **Input:** vài file PE mẫu.
- **Output:** `src/preprocessing/bytes_to_image.py` (đọc **PE thô đầy đủ**), `tests/test_bytes_to_image.py`.
- **DoD:** đọc nguyên bytes file PE → uint8; **width cố định từ config** (không bảng tra); pad 0 hàng cuối nếu lẻ; unit test pass; sinh thử 1 ảnh xem được.
- **Phụ thuộc:** S2.1  ·  **Ước lượng:** 0.5 ngày.

### S2.2b — Kênh entropy-byte + tỉ lệ ASCII + ghép 3 kênh `[P0]` `TODO`
- **Input:** ảnh xám (S2.2).
- **Output:** `src/preprocessing/channels.py` + hàm stack `3×H×W` + unit test.
- **DoD:** entropy **từ chuỗi byte** (cửa sổ liền kề, mặc định 256) & **tỉ lệ ASCII** (0x20–0x7E, cửa sổ byte) cùng H×W kênh 1; chuẩn hóa 0–255; tính ở native; bật/tắt từng kênh (ablation); sinh thử ảnh 3 kênh. Xem `docs/EXPERIMENTS.md`.
- **Phụ thuộc:** S2.2  ·  **Ước lượng:** 1 ngày.

### S2.3 — Sinh ảnh 3 kênh toàn dataset `[P0]` `TODO`
- **Input:** `data/raw/`, S2.2b, `labels.csv`.
- **Output:** `scripts/preprocess.py`; ảnh 3 kênh **native** (archive) + bản **resize 224/336/448**.
- **DoD:** **streaming từng file** (trong VM); sinh đủ ảnh cho mọi mẫu; giữ native; xuất 2 tầng (native archive + resize để train); config-driven; thanh tiến trình; lưu theo nhãn.
- **Phụ thuộc:** S2.2b, S1.3  ·  **Ước lượng:** 1 ngày. Xem `docs/ENVIRONMENT.md`.

### S2.4 — Split chống rò rỉ + stat per-channel `[P0]` `TODO`
- **Input:** ảnh đã sinh, `labels.csv`.
- **Output:** file split `train/val/test` + mean/std per-channel (train).
- **DoD:** **grouped split** (biến thể/họ cùng builder KHÔNG vắt qua train/test) + stratified theo lớp; (nếu có timestamp) cân nhắc temporal split; cố định seed; tính & lưu mean/std từng kênh trên train; không rò rỉ.
- **Phụ thuộc:** S2.3  ·  **Ước lượng:** 0.5 ngày.

---

## Giai đoạn 3 — Dataset & DataLoader

### S3.1 — Dataset + transforms `[P0]` `TODO`
- **Input:** file split (S2.4).
- **Output:** `src/datasets/malware_dataset.py`.
- **DoD:** đọc ảnh 3 kênh theo split; resize `img_size`, normalize per-channel; chọn tập con kênh (ablation); augment cấu hình được; trả (image, label); chạy CPU/GPU.
- **Phụ thuộc:** S2.4  ·  **Ước lượng:** 1 ngày.

### S3.2 — Cân bằng lớp + sanity check `[P1]` `TODO`
- **Input:** S3.1.
- **Output:** weighted sampler/class weights (benign khan hiếm) + script kiểm tra batch.
- **DoD:** hiển thị 1 batch đúng; xác minh phân bố sampler; không lỗi shape/dtype.
- **Phụ thuộc:** S3.1  ·  **Ước lượng:** 0.5 ngày.

---

## Giai đoạn 4 — Mô hình

### S4.1 — Model factory (pretrained) `[P0]` `TODO`
- **Output:** `src/models/factory.py` — VGG16, ResNet50, DenseNet121.
- **DoD:** load pretrained ImageNet (`in_chans=3`); thay lớp cuối (nhị phân & đa lớp); freeze/unfreeze; forward tensor giả OK.
- **Phụ thuộc:** —  ·  **Ước lượng:** 1 ngày.

### S4.2 — Baseline CNN custom `[P2]` `TODO`
- **DoD:** CNN custom nhẹ forward đúng; tích hợp factory qua tên config.
- **Phụ thuộc:** S4.1  ·  **Ước lượng:** 0.5 ngày.

### S4.3 — Model hiện đại qua `timm` (ConvNeXt-Tiny / ViT) `[P1]` `TODO`
- **DoD:** `timm.create_model(pretrained=True)`; thay head; forward OK; chọn qua config; bám SOTA 2025–2026.
- **Phụ thuộc:** S4.1  ·  **Ước lượng:** 0.5 ngày.

---

## Giai đoạn 5 — Huấn luyện

### S5.1 — Training loop lõi `[P0]` `TODO`
- **Output:** `src/training/trainer.py`.
- **DoD:** loss (CE/BCE), optimizer+scheduler, early stopping, checkpoint tốt nhất, log TensorBoard, ghi config mỗi run.
- **Phụ thuộc:** S3.1, S4.1  ·  **Ước lượng:** 1.5 ngày.

### S5.2 — CLI train + config YAML `[P0]` `TODO`
- **Output:** `scripts/train.py`, `configs/{task}_{model}.yaml`.
- **DoD:** chạy `--config`; mỗi model 1 config cùng setup; đặt tên run đúng quy ước.
- **Phụ thuộc:** S5.1  ·  **Ước lượng:** 0.5 ngày.

### S5.3 — Train PHÁT HIỆN nhị phân (4 model) `[P1]` `DONE`
- **Output:** checkpoints + logs VGG16/ResNet50/DenseNet121/ConvNeXt-Tiny (benign vs malware) trong `experiments/detect_<model>_224_<timestamp>/`.
- **DoD:** 4 run hoàn tất; val loss/acc hợp lý; checkpoint đủ.
- **Kết quả test set (2026-07-03):**

  | Model | Acc | Precision | Recall | F1 | ROC-AUC |
  |---|---|---|---|---|---|
  | VGG16 | 0.9689 | 0.9777 | 0.9703 | 0.9740 | 0.9901 |
  | ResNet50 | 0.9698 | 0.9792 | 0.9703 | 0.9747 | 0.9909 |
  | DenseNet121 | 0.9725 | 0.9830 | 0.9710 | 0.9770 | 0.9940 |
  | ConvNeXt-Tiny | 0.9675 | 0.9740 | 0.9718 | 0.9729 | 0.9929 |

  DenseNet121 tốt nhất mọi chỉ số; 4 model đều sát nhau (F1 0.973–0.977) — pipeline ổn định.
- **Phụ thuộc:** S5.2  ·  **Ước lượng:** 1–2 ngày (GPU).

### S5.4 — Phân loại họ mã độc (nhánh phụ) `[P2]` `TODO`
> Kế hoạch chi tiết: **`docs/EXPERIMENT_FAMILY.md`**. Dữ liệu: `labels.csv` (malware). **Phương án C:** tách bucket "RAT" (hành vi, không phải họ) thành các họ RAT thật → phân loại ~20 họ cùng mức family. Reuse ảnh 3 kênh @224.
- **S5.4a — Chuẩn hóa & tách nhãn:** lọc `label=1`; **tách RAT-subfamily từ path**; gộp alias (Heodo→Emotet, njrat→NjRat); **ngưỡng ≥150 + cap MAX_PER_CLASS=1000** (seed) → `labels_family.csv` + `family_map.json` (~20 lớp, imbalance ~6.7:1). *(0.5–1 ngày)*
- **S5.4b — Split họ:** `make_split_family.py` — **stratified theo họ, KHÔNG group theo subfamily** (group subfamily sẽ khiến lớp không học được); dedup SHA-256; (tùy chọn) cụm near-dup ssdeep/TLSH + `channel_stats_family.json`. *(0.5–1 ngày)*
- **S5.4c — Train:** `configs/family_{model}_224.yaml`, `num_classes≈20`, class_weights/sampler, ≥3 seed (model tốt nhất từ S5.3). *(1–2 ngày GPU)*
- **S5.4d — Đánh giá:** bảng per-class + **macro/weighted-F1 + top-3 + confusion matrix** + phân tích lỗi → `reports/experiment_family.md`. *(0.5 ngày)*
- **S5.4e — Bảng family→behavior** (đối chiếu Malpedia/MITRE). *(0.25 ngày)*
- **DoD:** metric chính = **macro-F1** (KHÔNG dùng accuracy làm chính); nêu rõ giới hạn near-duplicate & nhãn RAT-builder; kiểm tra bias nguồn.
- **Phụ thuộc:** S5.2, S2.3  ·  **Ước lượng:** ~3–4 ngày.

---

## Giai đoạn 5b — Thí nghiệm hợp nhất: lưới 5 kênh × 3 độ phân giải

> Gộp ablation kênh + hiệu quả độ phân giải thành **MỘT lưới** → rút **2 kết luận**. Chạy trên `res_eligible` (native ≥448²) của bộ phát hiện PE thô.

### S5b.1 — Lưới hợp nhất 5×3 (2 KẾT LUẬN CHÍNH) `[P0]` `DONE`
- **Input:** S2.2b, S5.2, S4.3; **tệp cố định `data/interim/sweep_{train,val,test}.csv`** (res_eligible) + `channel_stats_sweep.json`.
- **Cấu hình kênh:** **`gray1, gray×3, +entropy, +ascii, full`** (config đã có sẵn đủ trong `configs/`).
- **Output:** runs `{gray1, gray×3, +entropy, +ascii, full} × {224, 336, 448}` × **≥3 seed** trên ResNet50 (đủ lưới) + ConvNeXt-Tiny (trục độ phân giải với `full`). **1 bảng: dòng = config×size (15 dòng), cột = metrics (Acc/P/R/F1/ROC-AUC + time/GPUmem/FLOPs), làm nổi ô F1 tốt nhất.**
- **DoD:** **CẢ 15 ô đọc đúng cùng bộ `sweep_*.csv`** (config `split_prefix: sweep`), **chỉ đổi `channels`/`img_size`**; cùng seed-set/augment/epoch; **kiểm định thống kê** (t-test/McNemar) cho trục độ phân giải; ViT/Swin nội suy pos-embed nếu dùng.
- **Kết quả thực tế (2026-07-07):** 45/45 run ResNet50 + 9/9 run ConvNeXt-Tiny hoàn tất (3 seed: 42/123/2026). Bảng đầy đủ + kiểm định t-test: `docs/EXPERIMENTS.md` §2. Tổng hợp: `results/metrics/grid_{resnet50,convnext_tiny}.csv` + `grid_resolution_ttest.csv` + `results/figures/pareto_accuracy_vs_cost.png` (script `scripts/analyze_grid.py`, dùng `src/evaluation/stats.py`), dữ liệu thô mỗi run `results/metrics/sweep_{resnet50,convnext}_raw.csv` (script `scripts/aggregate_results.py`).
  - **Kết luận 1 (hàng, kênh):** thực tế `+entropy ≈ +ascii ≈ full > gray1 ≈ gray×3` (yếu hơn kỳ vọng `full` dẫn đầu tuyệt đối — `full` không luôn vượt `+entropy`/`+ascii` riêng lẻ). Chưa có kiểm định t-test chính thức cho trục kênh — chỉ là xu hướng quan sát được. Cần nêu rõ giới hạn n=3 seed trong báo cáo.
  - **Kết luận 2 (cột, độ phân giải):** paired t-test (trên F1, theo seed) 14/15 cặp size×kênh ở ResNet50 đều p>0.05 (ngoại lệ lẻ: `gray×3` 336² vs 448², p=0.047); kênh `full`: ResNet50 p=0.20/0.12/0.08, ConvNeXt-Tiny p=0.30/0.83/0.11 → accuracy tương đương thống kê giữa 3 size, trong khi chi phí tăng ×2.3–4× theo lý thuyết → **224² tối ưu, kết luận mạnh và đầy đủ bằng chứng trên gần như toàn lưới, không phụ thuộc kiến trúc.**
  - Ô F1 cao nhất thực tế: `full × 448` (ResNet50, F1=0.9823±0.0024), `full × 224` (ConvNeXt-Tiny, F1=0.9844±0.0031). Khuyến nghị triển khai vẫn là `full × 224` (ResNet50, F1=0.9755±0.0038) do Kết luận 2.
- **Phụ thuộc:** S5.2, S2.2b, S4.3  ·  **Ước lượng:** 3–4 ngày (GPU).

---

## Giai đoạn 6 — Đánh giá & so sánh

### S6.1 — Module metrics `[P0]` `DONE` (code, chưa có unit test riêng)
- **Output:** `src/evaluation/metrics.py` — `compute_metrics` (Acc/P/R/F1/ROC-AUC/confusion), `plot_confusion_matrix`, `plot_roc_curve`, `plot_pr_curve`, `plot_training_curves`, `save_evaluation_report`.
- **DoD:** nhận (y_true, y_pred/prob); vẽ confusion + ROC; test trên dữ liệu giả.
- **Ghi chú:** đã tích hợp thẳng vào `scripts/train.py` — sau khi train xong tự đánh giá trên **test set** bằng `best.pt` và xuất `figures/{test_metrics.json, test_confusion_matrix.png, test_roc_curve.png, test_pr_curve.png, training_curves.png}` vào từng thư mục run. Đã smoke-test bằng dữ liệu giả (không phải pytest chính thức) và backfill cho run VGG16 cũ.
- **Phụ thuộc:** —  ·  **Ước lượng:** 1 ngày.

### S6.2 — CLI evaluate + bảng so sánh + kiểm tra bias `[P1]` `DONE`
- **Output:** `scripts/evaluate.py` — tải `best.pt` + config của 1 hoặc nhiều run, chạy lại inference trên test set, xuất `results/metrics/evaluate_summary.csv` (bảng so sánh model) + `results/metrics/bias_source.csv` (accuracy/F1 theo từng `source` trong test set).
- **Usage:** `python scripts/evaluate.py --run experiments/<run>` (1 run) hoặc `--filter detect_` (nhiều run khớp tên).
- **Kết quả kiểm tra bias NGUỒN (2026-07-11, test set, 4 model detect_*):** nhóm **RAT** (n=262/2183, toàn malware) tụt **8.4–9.1 điểm % accuracy** so với accuracy tổng thể ở **cả 4 model** (VGG16/ResNet50/DenseNet121/ConvNeXt-Tiny) — bias nhất quán, không phải nhiễu ngẫu nhiên. Các nguồn khác dao động trong ±5 điểm % (phần lớn n nhỏ, kém tin cậy hơn); `figshare` (n=1027, có cả 2 lớp) cao hơn tổng thể ~2.1–2.6 điểm %.
- **Kiểm tra TEMPORAL — KHÔNG thực hiện được:** cột `first_seen` trong `data/interim/labels.csv` rỗng 100% (MalwareBazaar API có trả về nhưng chưa merge vào bước gán nhãn; figshare/RAT vốn không có ngày per-sample). Ghi nhận là **giới hạn đã biết** của đồ án, không suy diễn số liệu giả định. (Quyết định: chỉ làm source bias, không backfill lại metadata do figshare/RAT vẫn không phủ được.)
- **DoD:** bảng metrics đầy đủ các run ✓; **kiểm tra thiên lệch nguồn** ✓ (temporal: không khả thi, đã ghi giới hạn) ✓; xuất `results/metrics/` ✓.
- **Phụ thuộc:** S6.1, S5.3  ·  **Ước lượng:** 1 ngày.

### S6.3 — Phân tích lỗi + family→behavior `[P2]` `TODO`
- **Output:** `notebooks/03_error_analysis.ipynb`, bảng family→behavior.
- **DoD:** ca FP/FN tiêu biểu; nhận định nguyên nhân; (nhánh phụ) suy hành vi từ họ qua bảng tra.
- **Phụ thuộc:** S6.2  ·  **Ước lượng:** 0.5 ngày.

---

## Giai đoạn 6b — XAI & Robustness (tùy chọn)

### S6b.1 — Grad-CAM/HiResCAM `[P2]` `TODO`
- **Output:** `notebooks/04_xai.ipynb`, heatmap.
- **DoD:** heatmap cho mẫu benign & malware tiêu biểu; nhận xét vùng quyết định; dùng captum/pytorch-grad-cam.
- **Phụ thuộc:** S5.3  ·  **Ước lượng:** 1 ngày.

### S6b.2 — Robustness FGSM `[P2]` `TODO`
- **Output:** bảng accuracy trước/sau FGSM.
- **DoD:** mẫu đối kháng vài epsilon; đo suy giảm; nhận định độ bền.
- **Phụ thuộc:** S6b.1  ·  **Ước lượng:** 1–1.5 ngày.

---

## Giai đoạn 7 — Báo cáo DATN

### S7.1 — Tổng hợp số liệu & biểu đồ `[P1]` `TODO`
- **DoD:** biểu đồ in báo cáo; bảng so sánh cuối; số liệu khớp run.
- **Phụ thuộc:** S6.2  ·  **Ước lượng:** 0.5 ngày.

### S7.2 — Viết các chương báo cáo `[P1]` `TODO`
- **DoD:** đủ Tổng quan / Cơ sở lý thuyết / Phương pháp / Thực nghiệm / Kết luận; nêu rõ 2 RQ; trích dẫn dataset & paper.
- **Phụ thuộc:** S7.1  ·  **Ước lượng:** song song.

---

## Bảng theo dõi nhanh

| ID | Task | Ưu tiên | Phụ thuộc | Trạng thái |
|----|------|---------|-----------|------------|
| S1.1 | Thu thập malware (VM cô lập) | P0 | — | **DONE** |
| S1.2 | Thu thập benign đa nguồn | P0 | — | **DONE** |
| S1.3 | Dedup + nhãn + AVClass2 | P0 | S1.1,S1.2 | **DONE** |
| S1.4 | EDA + chốt width(=448) + check bias | P1 | S1.3 | **DONE** |
| S2.1 | Utils nền tảng (seed/config/logger) | P0 | — | **DONE** (code+test) |
| S2.2 | Đọc PE thô → ảnh xám + test | P0 | S2.1 | **DONE** |
| S2.2b | Entropy-byte + ASCII + ghép | P0 | S2.2 | **DONE** (code+test) |
| S2.3 | Sinh ảnh 3 kênh toàn dataset | P0 | S2.2b,S1.3 | **DONE** (224 toàn bộ; 336/448 res_eligible 7,860) |
| S2.4 | Split chống rò rỉ + stat | P0 | S2.3 | **DONE** (split 70/15/15, 0 rò rỉ, channel_stats) |
| S3.1 | Dataset + transform | P0 | S2.4 | **DONE** (code) |
| S3.2 | Cân bằng + sanity | P1 | S3.1 | ~ (class_weights trong train) |
| S4.1 | Model factory (VGG/ResNet/DenseNet/ConvNeXt) | P0 | — | **DONE** (code) |
| S4.2 | Baseline CNN custom | P2 | S4.1 | TODO |
| S4.3 | Model hiện đại (timm) | P1 | S4.1 | TODO |
| S5.1 | Training loop | P0 | S3.1,S4.1 | **DONE** (code) |
| S5.2 | CLI train + config | P0 | S5.1 | **DONE** (code, vgg16) |
| S5.3 | Train phát hiện nhị phân ×4 | P1 | S5.2 | **DONE** (DenseNet121 tốt nhất, F1=0.977) |
| S5.4 | Train phân loại họ (phụ) | P2 | S5.2,S1.3 | TODO |
| S5b.1 | Lưới hợp nhất 5×3 (2 kết luận) | P0 | S5.2,S2.2b,S4.3 | TODO (chờ 336/448 từ Kali VM + config) |
| S6.1 | Module metrics | P0 | — | **DONE** (tích hợp trong train.py) |
| S6.2 | CLI evaluate + check bias | P1 | S6.1,S5.3 | TODO |
| S6.3 | Phân tích lỗi + behavior | P2 | S6.2 | TODO |
| S6b.1 | Grad-CAM/XAI | P2 | S5.3 | TODO |
| S6b.2 | Robustness FGSM | P2 | S6b.1 | TODO |
| S7.1 | Tổng hợp số liệu | P1 | S6.2 | TODO |
| S7.2 | Viết báo cáo | P1 | S7.1 | TODO |
