# Báo cáo mã nguồn: Data / Model / Training

Tài liệu tổng hợp toàn bộ code Python đang dùng cho 3 mảng: **xử lý dữ liệu**, **model**, **huấn luyện/đánh giá**. Dùng để đưa vào báo cáo DATN hoặc để tra cứu nhanh khi cần chỉnh sửa pipeline.

> Quy ước: đường dẫn tương đối từ gốc repo `d:\DATN`. Các số hiệu "Giai đoạn Sx.y" tham chiếu `docs/BACKLOG.md`.

---

## 1. Sơ đồ tổng thể

```
labels.csv → detect_subset.csv → valid_*.csv → preprocess_manifest.csv
         (labeling.py)  (make_detection_subset.py) (make_valid_list.py) (preprocess.py)
                                                                              │
                                                    bytes_to_image.py + channels.py
                                                                              │
                                                                     ảnh PNG 3 kênh
                                                                              │
                                                    make_split.py → split_*.csv / sweep_*.csv
                                                                    + channel_stats.json
                                                                              │
                                                              malware_dataset.py (Dataset)
                                                                              │
                                                  factory.py (build_model) ──▶ train.py
                                                                              │
                                              evaluation/metrics.py + evaluation/stats.py
                                                                              │
                                          aggregate_results.py / analyze_grid.py (tổng hợp)
```

---

## 2. Code xử lý dữ liệu (data pipeline)

### 2.1. Gán nhãn & dedup — [`src/preprocessing/labeling.py`](../src/preprocessing/labeling.py)

- Quét đệ quy `data/raw/malware/` và `data/raw/benign/`, lọc theo phần mở rộng PE (`.exe .dll .bin .sys`) và kiểm tra magic `MZ` (`is_pe`).
- Tính SHA-256 streaming (`sha256_of`, đọc từng chunk 1 MB — không nạp cả file vào RAM).
- Dedup theo SHA-256 (`build_label_rows`): trùng hash → giữ bản có nhiều metadata hơn (có `family`).
- Suy `family` từ tên thư mục con (`_infer_family`); riêng nguồn `RAT` gộp cứng mọi sub-family (XWorm, NjRat, LiberiumRat…) thành nhãn `"RAT"` duy nhất.
- Hook `normalize_families_avclass()` — placeholder cho AVClass2 (chưa nối tự động, xem `docs/DATA_COLLECTION.md`).
- Output: `data/interim/labels.csv` (cột: `path, sha256, label, family, source, first_seen, size`).

### 2.2. Tạo tập detection cân bằng — [`scripts/make_detection_subset.py`](../scripts/make_detection_subset.py)

- Từ `labels.csv` đầy đủ, cap đều số mẫu mỗi họ malware để đạt tỉ lệ malware:benign mong muốn (mặc định **1.5:1**) — thuật toán `find_cap()` (binary search trên cap K sao cho `sum(min(n,K)) <= target`).
- Họ `RAT` được cap **theo từng sub-family** (`rat_subfamily()`) để tránh vài builder áp đảo.
- Không di chuyển/xoá file gốc — chỉ ghi danh sách được chọn ra `data/interim/detect_subset.csv`.

### 2.3. Lọc mẫu hợp lệ để train — [`scripts/make_valid_list.py`](../scripts/make_valid_list.py)

- Từ `labels.csv`/`detect_subset.csv` + `configs/data.yaml`, tính (chỉ từ cột `size`, không đọc bytes):
  - `valid = size >= min_bytes` (bỏ file quá nhỏ)
  - `native_h = ceil(min(size, max_bytes) / image_width)`
  - `res_eligible = valid và native_h >= image_width` (đủ ≥448×448 cho resolution sweep)
- Output: `data/interim/valid_for_train.csv` / `valid_detect.csv`.

### 2.4. Bytes → ảnh xám — [`src/preprocessing/bytes_to_image.py`](../src/preprocessing/bytes_to_image.py)

- `read_pe_bytes()` / `read_input()`: đọc **toàn bộ bytes PE thô** (giữ header), hoặc dispatch sang `parse_bytes_file()` cho định dạng `.bytes` legacy (BIG2015 IDA hex dump — không dùng trong pipeline chính).
- `array_to_image()`: width **cố định = 448** (`DEFAULT_WIDTH`), height = `ceil(n/width)`, pad 0 hàng cuối nếu lẻ → ảnh PIL mode `'L'`.
- `convert_file()`: hàm pipeline đầy đủ 1 file (dùng cả CLI lẫn import trong `preprocess.py`).
- `batch_convert()`: xử lý hàng loạt bằng `ProcessPoolExecutor`, giữ cấu trúc thư mục, hỗ trợ resume (`overwrite=False` bỏ qua file đã có).
- An toàn: chỉ đọc bytes, không thực thi; thiết kế streaming từng file để chạy trong VM cô lập RAM thấp.

### 2.5. Sinh 2 kênh còn lại — [`src/preprocessing/channels.py`](../src/preprocessing/channels.py)

- `byte_entropy_channel()` (kênh 2): duỗi ảnh xám về chuỗi byte gốc → chia khối 256 byte liên tiếp → Shannon entropy mỗi khối (0–8 bit, vectorized bằng `bincount`) → trải lại đúng vị trí byte → chuẩn hoá 0–255 (`normalize_uint8`, min-max theo từng ảnh).
- `printable_ratio_channel()` (kênh 3): cùng cách chia khối 256 byte, tính tỉ lệ byte thuộc `0x20–0x7E` (printable ASCII) ∈ [0,1] → map **tuyệt đối** ×255 (không min-max từng ảnh → nhất quán giữa các mẫu).
- `entropy_channel()`: bản **entropy 2D cũ** (cửa sổ 9×9 trên ảnh, dùng `skimage.filters.rank.entropy`) — giữ lại chỉ để đối chiếu, KHÔNG dùng trong pipeline mặc định.
- `make_composite()`: ghép `[gray, k2, k3]` → `H×W×3`; có cờ `use_entropy` / `use_ascii` để tắt từng kênh cho ablation (kênh tắt → thay bằng gray).

### 2.6. Điều phối sinh ảnh hàng loạt — [`scripts/preprocess.py`](../scripts/preprocess.py)

- Đọc `valid_*.csv` → với mỗi mẫu: `convert_file()` (bytes_to_image) → `make_composite()` (channels) → lưu ảnh resize (`Image.resize` BILINEAR) ở các `--sizes` (224/336/448) + tuỳ chọn bản native.
- `CHANNEL_MODES` (`full / +entropy / +ascii / gray3`) — chọn cấu hình kênh khi sinh ảnh cho ablation.
- Chống OOM: nếu ảnh native cao hơn `--max-native-height` (mặc định 8192) thì resize xuống trước khi tính kênh.
- Hỗ trợ resume (`--skip-existing`), đa tiến trình (`ProcessPoolExecutor`), giới hạn mẫu (`--limit`) để test nhanh.
- Output: ảnh PNG tại `data/processed/<size>/<sha[:2]>/<sha>.png` + `data/interim/preprocess_manifest.csv` (trạng thái ok/skipped_small/error từng mẫu).

### 2.7. Split chống rò rỉ + thống kê chuẩn hoá — [`scripts/make_split.py`](../scripts/make_split.py)

- `group_key()`: mẫu RAT nhóm theo **builder/sub-family** (`RAT/<subfamily>`) để builder không vắt qua train/test; các nguồn khác nhóm theo `sha256` (mỗi file 1 nhóm, đã dedup).
- `stratified_grouped_split()`: chia theo nhóm, stratified theo nhãn (benign/malware), giữ tỉ lệ ở cả 3 tập.
- Kiểm tra rò rỉ tự động: `group_key(train) ∩ group_key(test)` phải rỗng (log cảnh báo nếu không).
- `compute_channel_stats()`: tính mean/std **từng kênh** trên ảnh TRAIN (streaming qua PIL) → `channel_stats.json` — dùng để normalize, KHÔNG dùng stat ImageNet vì kênh không phải RGB thật.
- `--out-prefix`: `split` (bộ headline, toàn bộ mẫu hợp lệ, dùng cho phát hiện tổng thể) hoặc `sweep` (chỉ mẫu `res_eligible=1`, dùng chung cho cả 15 ô của lưới 5×3).

### 2.8. Dataset PyTorch — [`src/datasets/malware_dataset.py`](../src/datasets/malware_dataset.py)

- `MalwareImageDataset(split_csv, channel_stats, img_size, train, augment, channels, image_root)`.
- Đọc ảnh PNG 3 kênh, resize `img_size`, `ToTensor()` rồi `Normalize(mean, std)` theo `channel_stats.json` — **normalize trước khi chọn kênh ablation** nên mỗi kênh giữ đúng thống kê gốc của nó.
- `CHANNEL_KEEP` (bảng ablation kênh dữ liệu, không đổi kiến trúc model):

  | channels | tensor kết quả |
  |---|---|
  | `full` | `[gray, entropy, ascii]` |
  | `+entropy` | `[gray, entropy, gray]` |
  | `+ascii` | `[gray, gray, ascii]` |
  | `gray3` | `[gray, gray, gray]` |
  | `gray1` (đặc biệt) | chỉ lấy kênh 0 → tensor **1×H×W** (dùng với `model.in_chans=1`) |
- `image_root`: nếu set, tự dựng path `{image_root}/{img_size}/{sha[:2]}/{sha}.png` thay vì đọc cột `image_path` trong CSV — cho phép 1 bộ `sweep_*.csv` dùng chung cho cả 224/336/448 (chỉ đổi `img_size`).
- Augment nhẹ có chủ đích: chỉ `RandomAffine(translate=0.02)` xác suất 0.3 — **không lật/xoay mạnh** vì sẽ phá cấu trúc byte tuyến tính của ảnh.
- `class_counts()`: đếm mẫu theo nhãn — dùng để tính class weights (benign khan hiếm).

---

## 3. Code liên quan đến model

### 3.1. Model factory — [`src/models/factory.py`](../src/models/factory.py)

Hàm chính: `build_model(name, num_classes=2, pretrained=True, freeze_backbone=False, in_chans=3)`.

| Model | Trọng số pretrained | Head thay thế | Conv đầu (attr) |
|---|---|---|---|
| `vgg16` | `VGG16_Weights.IMAGENET1K_V1` | `classifier[6]` → `Linear` | `features[0]` |
| `resnet50` | `ResNet50_Weights.IMAGENET1K_V2` | `fc` → `Linear` | `conv1` |
| `densenet121` | `DenseNet121_Weights.IMAGENET1K_V1` | `classifier` → `Linear` | `features.conv0` |
| `convnext_tiny` | `ConvNeXt_Tiny_Weights.IMAGENET1K_V1` | `classifier[2]` → `Linear` | `features[0][0]` |

- **`in_chans=3` (mặc định, ảnh composite):** giữ nguyên conv đầu pretrained, chỉ thay lớp phân loại cuối.
- **`in_chans=1` (ablation `gray1`):** `_new_first_conv()` tạo conv đầu mới 1 kênh, khởi tạo trọng số = **tổng 3 kênh RGB pretrained** (`w.sum(dim=1)`) → tương đương "gray×3" ngay lúc khởi tạo, đảm bảo so sánh công bằng giữa các cấu hình kênh (không mất tri thức pretrained chỉ vì đổi số kênh input).

#### "Head thay thế" là gì

Mọi model torchvision liệt kê ở trên đều **pretrained trên ImageNet (1000 lớp)**, nên lớp cuối cùng (classification head) có `out_features=1000`. Bài toán ở đây chỉ có 2 lớp (benign/malware), nên phải thay lớp cuối bằng `nn.Linear(in_features, num_classes=2)` — **giữ nguyên `in_features`** (số đặc trưng do backbone trích ra, không đổi) và chỉ đổi `out_features`. Toàn bộ backbone phía trước (đã học đặc trưng texture/cạnh/hình khối tổng quát từ ImageNet) được **giữ nguyên trọng số pretrained**, chỉ có head là khởi tạo ngẫu nhiên và học lại từ đầu cho bài toán mới. Vì mỗi kiến trúc đặt tên module cuối khác nhau nên phải trỏ đúng attribute:

- `vgg16`: `m.classifier[6]` — lớp `Linear` cuối cùng trong khối `classifier` (Sequential 7 lớp: Linear→ReLU→Dropout ×2 + Linear cuối).
- `resnet50`: `m.fc` — attribute độc lập (không nằm trong Sequential nào), là lớp Linear duy nhất sau `AdaptiveAvgPool2d`.
- `densenet121`: `m.classifier` — cũng là 1 attribute Linear độc lập, sau global pooling.
- `convnext_tiny`: `m.classifier[2]` — lớp Linear cuối trong khối `classifier` (gồm LayerNorm2d → Flatten → Linear).

#### "Conv đầu (attr)" là gì

Đây là **lớp convolution đầu tiên** của mỗi kiến trúc — lớp duy nhất **trực tiếp nhận ảnh đầu vào**, nên cũng là lớp duy nhất cần sửa khi `in_chans != 3`. Trọng số pretrained của lớp này có shape `(out_channels, 3, kH, kW)` (ứng với 3 kênh RGB ImageNet gốc); khi đổi số kênh đầu vào (ví dụ ablation `gray1` dùng `in_chans=1`), phải tạo conv mới với `in_channels` khác và khởi tạo trọng số hợp lý từ pretrained (qua `_new_first_conv()`, xem §3.1 ở trên) thay vì random-init hoàn toàn — nếu không sẽ mất hết tri thức pretrained ngay từ lớp đầu tiên. Path khác nhau tùy kiến trúc vì cấu trúc module khác nhau:

- `vgg16`: `m.features[0]` — phần tử đầu tiên trong `Sequential features` (khối conv trước khi vào pooling).
- `resnet50`: `m.conv1` — attribute độc lập, conv 7×7 stride 2 đầu tiên trước `bn1`/`maxpool`.
- `densenet121`: `m.features.conv0` — nằm trong `OrderedDict` con tên `features` (DenseNet đặt tên các lớp stem là `conv0, norm0, relu0, pool0`).
- `convnext_tiny`: `m.features[0][0]` — lớp "patchify stem" (conv 4×4 stride 4), phần tử `[0]` đầu tiên của `features` lại là 1 `Sequential` con nên phải chỉ số kép `[0][0]`.

Vì `_new_first_conv()` là hàm dùng chung cho cả 4 kiến trúc, việc xác định đúng attribute path này là bắt buộc — sai đường dẫn sẽ tạo thêm 1 conv layer song song vô nghĩa thay vì thay thế đúng lớp cần sửa.
- `freeze_backbone=True`: đóng băng toàn bộ tham số, chỉ bật `requires_grad` cho head (`_set_requires_grad`).
- **Lưu ý quan trọng:** với 4 cấu hình kênh dữ liệu `full/gray3/+entropy/+ascii`, `in_chans` luôn = 3 → kiến trúc và trọng số khởi tạo của conv đầu **giống hệt nhau**; khác biệt accuracy giữa các cấu hình chỉ đến từ nội dung ảnh (xem §2.8), không phải từ model. Chỉ `gray1` mới thực sự đổi kiến trúc (conv 1 kênh).

---

## 4. Code dùng để train / đánh giá

### 4.1. Vòng lặp huấn luyện chính — [`scripts/train.py`](../scripts/train.py)

Usage: `python scripts/train.py --config configs/detect_vgg16_224.yaml`

- `make_loaders(cfg, logger)`: dựng 3 `MalwareImageDataset` (train/val/test) từ `data.split_prefix` (`split` hay `sweep`) + `DataLoader` (batch size, num_workers, `pin_memory`, `drop_last=True` cho train).
- `class_weights()`: tính trọng số lớp tự động (nghịch đảo tần suất) — bù benign khan hiếm, dùng trong `CrossEntropyLoss(weight=...)`.

  ```python
  def class_weights(train_ds, num_classes, device):
      c = train_ds.class_counts()
      total = sum(c.values())
      w = [total / (num_classes * c.get(i, 1)) for i in range(num_classes)]
      return torch.tensor(w, dtype=torch.float32, device=device)
  ```

  Công thức chuẩn "balanced class weight": `w_i = N / (K × n_i)` (N = tổng số mẫu, K = số lớp, n_i = số mẫu lớp i — giống `class_weight="balanced"` của scikit-learn). Ví dụ với `split_train.csv` thực tế (benign 4.066 / malware 6.115, N=10.181, K=2):
  - `w_benign = 10181 / (2×4066) ≈ 1.252`
  - `w_malware = 10181 / (2×6115) ≈ 0.832`

  Lớp càng **hiếm** (benign) thì trọng số càng **lớn**. Khi đưa vào `nn.CrossEntropyLoss(weight=weight)`, mỗi lỗi phân loại sai trên 1 mẫu benign sẽ đóng góp vào loss **gấp ~1,5 lần** so với lỗi trên 1 mẫu malware — bù lại việc benign chỉ chiếm ~40% dữ liệu. Nếu không có bước này, loss sẽ bị chi phối bởi lớp đa số (malware), model dễ đạt accuracy cao ảo bằng cách thiên vị dự đoán "malware" mà không thực sự phân biệt tốt benign. Cách này ưu việt hơn oversampling vật lý (nhân bản mẫu benign) vì không tạo dữ liệu trùng lặp gây overfitting. Kích hoạt qua config `train.class_weights: "auto"` (mặc định).

- Vòng train mỗi epoch: forward/backward với **AMP** (`torch.cuda.amp.autocast` + `GradScaler`), hỗ trợ **gradient accumulation** (`train.grad_accum_steps`), optimizer `AdamW`, scheduler `CosineAnnealingLR`.

  **AMP (Automatic Mixed Precision):**
  ```python
  scaler = torch.cuda.amp.GradScaler(enabled=use_amp)
  ...
  with torch.cuda.amp.autocast(enabled=use_amp):
      loss = criterion(model(x), y) / accum
  scaler.scale(loss).backward()
  ```
  - `autocast()`: tự động chạy các phép toán "an toàn" (conv, matmul) ở **float16** (half precision) thay vì float32 mặc định, còn các phép nhạy về số học (batchnorm, softmax, tính loss) vẫn giữ float32 — PyTorch tự quyết định per-op. Lợi ích: giảm ~40–50% bộ nhớ GPU và tăng tốc đáng kể trên Tensor Core (RTX 4060 local) → cho phép batch size lớn hơn hoặc chạy được `img_size=448` trong giới hạn 8GB VRAM (xem `docs/ENVIRONMENT.md`).
  - `GradScaler`: float16 có dải số mũ hẹp → gradient nhỏ dễ **underflow về 0** khi backward. `GradScaler` nhân loss lên một hệ số lớn trước `backward()` để gradient không biến mất ở fp16, sau đó tự **unscale** lại đúng tỉ lệ khi gọi `scaler.step(optimizer)`. `scaler.update()` tự điều chỉnh hệ số scale mỗi bước dựa trên việc có xảy ra tràn số (inf/nan) hay không.
  - `use_amp` chỉ bật khi `device == "cuda"` (không có tác dụng/không hỗ trợ tốt trên CPU).

  **Gradient accumulation (`train.grad_accum_steps`, mặc định 1 = tắt):**
  ```python
  loss = criterion(model(x), y) / accum        # chia loss cho accum trước khi backward
  scaler.scale(loss).backward()                # cộng dồn gradient (PyTorch mặc định không zero_grad giữa các backward)
  if (i + 1) % accum == 0 or (i + 1) == n_batches:
      scaler.step(optimizer)                   # chỉ update trọng số mỗi `accum` batch
      scaler.update()
      optimizer.zero_grad(set_to_none=True)
  ```
  Mục đích: **mô phỏng batch size lớn hơn** mức GPU vật lý chứa nổi. Thay vì 1 batch lớn, chạy `accum` batch nhỏ liên tiếp, cộng dồn gradient (chia loss cho `accum` để trung bình đúng), rồi mới `optimizer.step()` 1 lần — tương đương học trên `effective_batch_size = batch_size × accum` mẫu mỗi lần cập nhật trọng số (giá trị này được ghi vào `cost.json` để so sánh chi phí). Quan trọng cho lưới hợp nhất 5×3: ở `img_size=448` bộ nhớ cần tăng theo cấp bậc hai so với 224, có thể không đủ VRAM 8GB nếu giữ nguyên `batch_size` vật lý — tăng `grad_accum_steps` cho phép giữ **cùng effective batch size** (cùng động lực học/learning rate) giữa các cấu hình độ phân giải khác nhau mà không cần đổi batch size vật lý.
- `predict()` / `evaluate()`: chạy no-grad trên loader, trả `(y_true, y_pred, y_prob)` → `compute_metrics()`.
- **Early stopping** theo val F1 (`train.early_stop_patience`); mỗi khi F1 tốt hơn → lưu `best.pt` (state_dict + config + val_metrics) và `best_metrics.json`.
- Sau khi train xong: load lại `best.pt`, đánh giá trên **test set**, xuất `figures/training_curves.png` + báo cáo test (`save_evaluation_report`).
- Đo **chi phí** (S5b.2, phục vụ bảng accuracy-vs-cost): GPU peak memory (`torch.cuda.max_memory_allocated`), GMACs + số tham số qua `thop.profile`, thời gian/epoch → ghi `cost.json`.
- Toàn bộ hyperparameter đọc từ YAML qua `get(cfg, "dotted.key", default)` — không hard-code (config-driven).

### 4.2. Metrics & biểu đồ — [`src/evaluation/metrics.py`](../src/evaluation/metrics.py)

- `compute_metrics()`: Accuracy, Precision, Recall, F1 (sklearn, `zero_division=0`), ROC-AUC (bắt `ValueError` khi chỉ có 1 lớp trong batch), confusion matrix 2×2.
- `plot_confusion_matrix()`, `plot_roc_curve()`, `plot_pr_curve()`, `plot_training_curves()`: xuất PNG (matplotlib backend `Agg`, không cần display).
- `save_evaluation_report()`: hàm tổng hợp — tính metrics + lưu JSON + 3 biểu đồ, dùng chung cho val (trong lúc train) và test (cuối cùng).

### 4.3. Kiểm định thống kê — [`src/evaluation/stats.py`](../src/evaluation/stats.py)

- `paired_ttest(scores_a, scores_b)`: paired t-test trên điểm số theo từng seed (từ `cost.json`/`test_metrics.json`) — dùng để chứng minh "224 ≈ 336 ≈ 448" có ý nghĩa thống kê hay chỉ là nhiễu (`docs/EXPERIMENTS.md` §6).
- `mcnemar_test(y_true, pred_a, pred_b)`: McNemar test (continuity-corrected) so 2 model trực tiếp trên từng mẫu test — tuỳ chọn, ít dùng vì `train.py` hiện không lưu raw predictions.

### 4.4. Tiện ích dùng chung — `src/utils/`

- [`config.py`](../src/utils/config.py): `load_config()` đọc YAML; `get()` truy cập khoá lồng nhau kiểu `a.b.c`; `native_height()` tính chiều cao ảnh native.
- [`seed.py`](../src/utils/seed.py): `set_seed()` — đặt seed cho `random`/`numpy`/`torch`/CUDA, bật `cudnn.deterministic`; import `torch` có điều kiện (máy tiền xử lý không cần cài torch).
- [`logger.py`](../src/utils/logger.py): logger dùng chung, ghi ra cả console lẫn file log của từng run.

### 4.5. Tổng hợp kết quả nhiều run

- [`scripts/aggregate_results.py`](../scripts/aggregate_results.py): quét toàn bộ thư mục `experiments/<run>/`, đọc `cost.json` + `figures/test_metrics.json` (fallback `best_metrics.json`) → gộp thành 1 bảng CSV so sánh (dùng cho ablation kênh S5b.1 và so sánh model).
- [`scripts/analyze_grid.py`](../scripts/analyze_grid.py): chuyên biệt cho **lưới hợp nhất 5×3** (`sweep_resnet50_*`, `sweep_convnext_tiny_*`) — dựng bảng config-kênh × độ phân giải, chạy `paired_ttest`/thống kê qua `evaluation/stats.py`, xuất `grid_resnet50.csv` / `grid_convnext_tiny.csv` + biểu đồ so sánh.

---

## 5. Bảng tổng hợp nhanh (file → vai trò)

| File | Vai trò | Giai đoạn |
|---|---|---|
| `src/preprocessing/labeling.py` | Dedup SHA-256 + gán nhãn benign/malware | S1 |
| `scripts/make_detection_subset.py` | Tạo tập detection cân bằng 1.5:1 | S1 |
| `scripts/make_valid_list.py` | Lọc mẫu hợp lệ + cờ `res_eligible` | S1→S2 |
| `src/preprocessing/bytes_to_image.py` | Bytes PE → ảnh xám (kênh 1) | S2 |
| `src/preprocessing/channels.py` | Sinh kênh entropy-byte + ascii-ratio | S2 |
| `scripts/preprocess.py` | Điều phối sinh ảnh 3 kênh hàng loạt | S2 |
| `scripts/make_split.py` | Split chống rò rỉ + channel_stats.json | S2 |
| `src/datasets/malware_dataset.py` | `Dataset` PyTorch, ablation kênh | S3 |
| `src/models/factory.py` | Khởi tạo VGG16/ResNet50/DenseNet121/ConvNeXt-Tiny | S4 |
| `scripts/train.py` | Vòng lặp train + eval + cost | S5 |
| `src/evaluation/metrics.py` | Acc/P/R/F1/ROC-AUC + biểu đồ | S6 |
| `src/evaluation/stats.py` | Paired t-test / McNemar | S5b/S6 |
| `src/utils/config.py`, `seed.py`, `logger.py` | Tiện ích dùng chung | mọi giai đoạn |
| `scripts/aggregate_results.py` | Gộp nhiều run thành bảng so sánh | S5b/S6 |
| `scripts/analyze_grid.py` | Phân tích riêng lưới hợp nhất 5×3 | S5b |

---

## 6. Lệnh chạy end-to-end (tham khảo)

```bash
# 1. Gán nhãn
python -m src.preprocessing.labeling --malware-dir data/raw/malware --benign-dir data/raw/benign

# 2. Tập detection cân bằng
python scripts/make_detection_subset.py --ratio 1.5

# 3. Lọc mẫu hợp lệ
python scripts/make_valid_list.py --input data/interim/detect_subset.csv --out data/interim/valid_detect.csv

# 4. Sinh ảnh 3 kênh (224, hoặc 224/336/448 cho sweep)
python scripts/preprocess.py --input data/interim/valid_detect.csv --sizes 224 --workers 4

# 5. Split chống rò rỉ + channel stats
python scripts/make_split.py --input data/interim/valid_detect.csv --image-dir data/processed/224

# 6. Train
python scripts/train.py --config configs/detect_resnet50_224.yaml

# 7. Tổng hợp kết quả nhiều run
python scripts/aggregate_results.py
python scripts/analyze_grid.py
```

---

## 7. Số liệu dataset thực tế (đo trên `split_*.csv`, 2026-07-08)

Đếm bằng [`scripts/count_families.py`](../scripts/count_families.py) và [`scripts/count_by_ext.py`](../scripts/count_by_ext.py) trên bộ split headline (`split_train/val/test.csv`, toàn bộ mẫu hợp lệ dùng cho phát hiện nhị phân @224).

- **Tổng số mẫu:** 14.547 (benign 5.810 / malware 8.737)
- **Số family malware khác nhau:** **15**

| Family | Số mẫu | Ghi chú |
|---|---:|---|
| Zbot | 1.746 | |
| Winwebsec | 1.746 | |
| RAT | 1.741 | gộp cứng theo `source="rat"` trong `labeling.py` (mọi builder Ultimate-RAT-Collection) |
| Mediyes | 1.450 | |
| Zeroaccess | 690 | |
| Locker | 330 | |
| Trickbot | 175 | |
| RedLineStealer | 160 | |
| njrat | 159 | từ MalwareBazaar (`signature=njrat`) — **KHÔNG** bị gộp vào nhãn `"RAT"` vì nguồn khác `source="rat"` |
| Heodo | 152 | |
| Formbook | 113 | |
| Emotet | 95 | |
| SnakeKeylogger | 82 | |
| AgentTesla | 62 | |
| RemcosRAT | 36 | từ MalwareBazaar — cùng lý do như `njrat`, không gộp vào `"RAT"` |

> **Lưu ý nhất quán:** cột `family` chỉ gộp thành `"RAT"` khi mẫu đến từ thư mục nguồn `source="rat"` (Ultimate-RAT-Collection). Các họ RAT khác thu qua MalwareBazaar theo signature (`njrat`, `RemcosRAT`) vẫn giữ tên gốc và **không** được tính chung vào nhóm `RAT` — nếu nhánh phân loại họ (phụ) muốn "RAT là một nhóm" đúng như `docs/BACKLOG.md` mô tả, cần gộp thêm `njrat` + `RemcosRAT` (và mọi family khác có gốc RAT) vào `"RAT"` trước khi train, hoặc làm rõ đây là 2 khái niệm khác nhau (nguồn thu thập vs. họ thực sự).

> Đây là số liệu trên **tập split headline** (`split_*.csv`, đã lọc `valid_detect.csv` + bỏ mẫu preprocess lỗi). Tập `labels.csv` gốc (trước lọc min/max bytes) trên máy VM có thể có thêm vài family hiếm bị loại ở bước `make_valid_list.py`/`preprocess.py` — chạy `python scripts/count_families.py data/interim/labels.csv` trên máy VM để đối chiếu nếu cần.
