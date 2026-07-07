# COLAB.md — Hướng dẫn train trên Google Colab

Bổ sung cho `docs/ENVIRONMENT.md` (phân vai môi trường) và `docs/WORKFLOW.md`. Dùng khi cần
train việc nặng (448², nhiều seed, chạy song song với local RTX 4060).

> **An toàn dữ liệu:** chỉ đưa lên Colab/Drive **ảnh PNG 3 kênh đã sinh** (vô hại) + file CSV/JSON
> (`data/interim/*.csv`, `channel_stats.json`) + code (`src/`, `scripts/`, `configs/`).
> **KHÔNG BAO GIỜ** đưa `data/raw/malware/` (PE thật) lên Colab/Drive.

---

## 0. Trạng thái dữ liệu hiện tại (đọc trước khi làm)

| Cái gì | Sẵn sàng? |
|--------|-----------|
| `data/processed/224/` (14,547 ảnh) | ✅ có sẵn, đã đóng gói ở `detect224.tar.gz` (~800 MB, gốc repo) |
| `data/interim/split_{train,val,test}.csv` + `channel_stats.json` | ✅ có sẵn |
| `configs/detect_{vgg16,resnet50,densenet121,convnext_tiny}_224.yaml` | ✅ có sẵn |
| `data/processed/336/`, `data/processed/448/` | ❌ **chưa sinh** |
| `data/interim/valid_*.csv` (cờ `res_eligible`), `sweep_*.csv` | ❌ **chưa có** |
| Config 336/448 | ❌ **chưa có file** |

→ Phần **1–5** dưới đây dùng được **ngay bây giờ** để train 4 model @224 (S5.3) trên Colab.
Phần **6 (lưới hợp nhất 5×3, trục 336/448 — S5b.1)** là khung sẵn, chỉ chạy được sau khi hoàn thiện
tiền xử lý 336/448 ở Giai đoạn 2 (xem checklist ở cuối file).

---

## 1. Đóng gói & tải lên Google Drive (làm 1 lần trên máy local)

```powershell
# Ở D:\DATN — đóng gói code (không kèm data/raw, datn-env, data/processed)
# detect224.tar.gz đã có sẵn ở gốc repo — dùng luôn, không cần nén lại.

# Nén phần interim (CSV/JSON — nhẹ, vô hại) + code
tar -czf datn_code.tar.gz src scripts configs requirements.txt
tar -czf datn_interim.tar.gz data/interim
```

Tải 3 file lên Google Drive, ví dụ vào `My Drive/DATN/`:
- `detect224.tar.gz` (ảnh 224)
- `datn_interim.tar.gz` (split CSV + channel_stats.json)
- `datn_code.tar.gz` (src/scripts/configs/requirements.txt)

> Chỉ cần làm lại bước này khi code hoặc data thay đổi. Không cần tải lại mỗi phiên Colab.

---

## 2. Notebook Colab — thiết lập môi trường

Tạo notebook mới, chọn **Runtime → Change runtime type → GPU (T4)**.

```python
# Cell 1 — mount Drive
from google.colab import drive
drive.mount('/content/drive')

DRIVE_DIR = '/content/drive/MyDrive/DATN'
```

```python
# Cell 2 — giải nén vào /content (đĩa cục bộ Colab, nhanh hơn đọc trực tiếp từ Drive)
import os
os.makedirs('/content/DATN', exist_ok=True)
%cd /content/DATN

!tar -xzf {DRIVE_DIR}/datn_code.tar.gz
!tar -xzf {DRIVE_DIR}/datn_interim.tar.gz
!mkdir -p data/processed
!tar -xzf {DRIVE_DIR}/detect224.tar.gz    # giải nén thẳng data/processed/224/
```

```python
# Cell 3 — cài dependency
# Colab đã có torch/torchvision sẵn (thường khá mới) — chỉ cài thêm phần thiếu để tránh
# xung đột version torch (KHÔNG chạy "pip install -r requirements.txt" nguyên văn).
!pip install -q scikit-learn scikit-image pyyaml tqdm thop
import torch
print(torch.__version__, 'cuda:', torch.cuda.is_available(), torch.cuda.get_device_name(0))
```

```python
# Cell 4 — sanity check dữ liệu đã giải nén đúng
!python -c "import csv; print(sum(1 for _ in csv.DictReader(open('data/interim/split_train.csv', encoding='utf-8'))))"
!find data/processed/224 -name '*.png' | wc -l
```

---

## 3. Chỉnh config để checkpoint sống sót qua ngắt phiên

Colab giới hạn phiên ~12h và có thể ngắt bất kỳ lúc nào. Sửa `paths.out_dir` trong config để
lưu thẳng vào Drive (không lưu ở `/content` vì mất khi phiên kết thúc):

```python
# Cell 5 — patch out_dir sang Drive cho tất cả config 224
import yaml, glob

os.makedirs(f'{DRIVE_DIR}/experiments', exist_ok=True)
for f in glob.glob('configs/detect_*_224.yaml'):
    cfg = yaml.safe_load(open(f, encoding='utf-8'))
    cfg['paths']['out_dir'] = f'{DRIVE_DIR}/experiments'
    yaml.safe_dump(cfg, open(f, 'w', encoding='utf-8'), allow_unicode=True, sort_keys=False)
print('Đã patch out_dir -> Drive')
```

> **Giới hạn hiện tại (nêu rõ để không bất ngờ):** `train.py` chỉ lưu `best.pt` khi F1 val cải
> thiện, **không** checkpoint mỗi epoch và **không hỗ trợ resume** giữa chừng. Nếu phiên Colab bị
> ngắt giữa lúc train, phải chạy lại từ epoch 1 cho run đó (các run đã `XONG` trước đó không mất).
> Với 4 model @224 (~35–45 phút/model theo log VGG16 thực tế), 1 phiên Colab là đủ chạy hết —
> chưa cần resume. Sẽ cần bổ sung resume nếu sau này chạy sweep 448 nhiều seed (rủi ro vượt 12h).

---

## 4. Batch size theo GPU (T4 16GB) — theo `docs/ENVIRONMENT.md`

Config hiện tại để `batch_size: 32` cho cả 4 model (an toàn cho RTX 4060 8GB). Trên T4 16GB có
thể tăng gấp đôi để train nhanh hơn — sửa trực tiếp trong config hoặc patch nhanh:

```python
# Cell 6 (tuỳ chọn) — tăng batch_size cho T4 16GB
for f in glob.glob('configs/detect_*_224.yaml'):
    cfg = yaml.safe_load(open(f, encoding='utf-8'))
    cfg['data']['batch_size'] = 64
    yaml.safe_dump(cfg, open(f, 'w', encoding='utf-8'), allow_unicode=True, sort_keys=False)
```

| img_size | Batch 4060 8GB | Batch T4 16GB (gợi ý) |
|----------|---------------|------------------------|
| 224² | 32 (VGG16) / 64 (ResNet50, ConvNeXt, DenseNet) | 64 / 128 |
| 336² (sweep, sau này) | ~24–32 | ~48–64 |
| 448² (sweep, sau này) | 8–16 + grad accumulation | 16–32 |

---

## 5. Chạy train 4 model @224 (S5.3)

VGG16 đã train xong ở local — nếu chỉ cần 3 model còn lại:

```python
# Cell 7 — chạy lần lượt (mỗi lệnh ~35–45 phút trên GPU tương đương 4060; T4 có thể nhanh hơn)
!python scripts/train.py --config configs/detect_resnet50_224.yaml
```
```python
!python scripts/train.py --config configs/detect_densenet121_224.yaml
```
```python
!python scripts/train.py --config configs/detect_convnext_tiny_224.yaml
```

Mỗi lệnh tự sinh khi xong:
- `{DRIVE_DIR}/experiments/detect_<model>_224_<timestamp>/best.pt`
- `.../best_metrics.json`, `.../train.log`
- `.../figures/test_metrics.json`, `test_confusion_matrix.png`, `test_roc_curve.png`, `test_pr_curve.png`, `training_curves.png`

## Đồng bộ kết quả về máy local

Sau khi train xong trên Colab, tải thư mục `experiments/detect_<model>_224_<timestamp>/` từ
Drive về `D:\DATN\experiments\` (qua Google Drive Desktop hoặc tải zip thủ công), rồi cập nhật
trạng thái task `S5.3` trong `docs/BACKLOG.md` + `progress_dashboard.html`.

---

## 6. Lưới hợp nhất 5×3 — trục độ phân giải 224/336/448 (S5b.1) — CHƯA CHẠY ĐƯỢC, cần hoàn thiện trước

Checklist phải xong **trước khi** áp dụng phần này (xem mục 0):

1. Sinh ảnh native + resize 336/448 cho tập `res_eligible` (`scripts/preprocess.py`, xem `docs/EXPERIMENTS.md` §"Tập dữ liệu cho sweep").
2. Gắn cờ `res_eligible` vào `valid_*.csv` (`scripts/make_valid_list.py`).
3. Tạo split cố định cho sweep (cùng danh sách mẫu cho cả 3 độ phân giải):
   ```bash
   python scripts/make_split.py --input data/interim/valid_detect.csv \
       --image-dir data/processed/336 --only-res-eligible --out-prefix sweep \
       --out-dir data/interim
   ```
   (Sinh `sweep_train.csv` / `sweep_val.csv` / `sweep_test.csv` — danh sách mẫu giữ nguyên,
   chỉ đổi `image_path` khi đổi độ phân giải; nếu cần ảnh 224/448 cho đúng mẫu này, generate ảnh ở
   `data/processed/{224,336,448}` cho cùng danh sách `sha256` rồi trỏ `--image-dir` tương ứng.)
4. Tạo config `detect_{resnet50,convnext_tiny}_{224,336,448}_s{seed}.yaml` — copy từ config 224
   hiện có, đổi `img_size`, `split_prefix: sweep`, `batch_size` theo bảng ở mục 4, và `seed` (≥3 seed
   khác nhau, ví dụ 42/123/2026).

Khi đã đủ 4 điều kiện trên, chạy tương tự Cell 7 nhưng lặp qua ma trận
`{resnet50, convnext_tiny} × {224,336,448} × {seed1,seed2,seed3}` (18 run) — nên tách các seed
thành các lần gọi `!python scripts/train.py --config ...` riêng để dễ theo dõi log từng run.

Sau khi có đủ 18 run: tổng hợp bảng accuracy/F1 (mean±std) + thời gian/epoch + GPU mem (đo bằng
`torch.cuda.max_memory_allocated()`) + FLOPs (`thop`) theo đúng yêu cầu ở `docs/EXPERIMENTS.md`,
rồi chạy kiểm định thống kê (paired t-test/McNemar) giữa các độ phân giải — phần này chưa có code
sẵn, cần viết thêm (ngoài phạm vi `train.py`).

---

## 7. Sự cố thường gặp

| Lỗi | Nguyên nhân | Cách xử lý |
|-----|-------------|-----------|
| `FileNotFoundError: data/interim/split_train.csv` | Chưa giải nén `datn_interim.tar.gz` hoặc sai `%cd` | Kiểm tra Cell 2, `!pwd` |
| `CUDA out of memory` | batch_size quá lớn cho model/img_size | Giảm `batch_size` trong config, giữ `amp: true` |
| Phiên Colab ngắt giữa chừng | Giới hạn ~12h hoặc idle timeout | Chạy lại `train.py` cho model đó (không resume được — xem mục 3); các model đã `XONG` không ảnh hưởng |
| Kết quả 336/448 không xuất hiện | Chưa hoàn thiện checklist mục 6 | Không phải lỗi — tính năng chưa sẵn sàng, làm mục 6 trước |
