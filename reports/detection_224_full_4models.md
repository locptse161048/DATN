# Báo cáo: Phát hiện nhị phân — 224×224, ảnh 3 kênh composite (full)

> Tương ứng `S5.3` trong `docs/BACKLOG.md` (`DONE`, 2026-07-03). Đây là kết quả **headline** của đề tài — so sánh 4 kiến trúc CNN cho bài toán phát hiện nhị phân (benign vs malware) ở cấu hình chuẩn: độ phân giải **224×224**, ảnh **3 kênh composite đầy đủ** (`channels: full` = grayscale + entropy-byte + tỉ lệ ASCII, xem `CLAUDE.md` §4).

## 1. Dataset

Dùng **`data/interim/split_{train,val,test}.csv`** — split phát hiện headline, gồm **toàn bộ mẫu hợp lệ** (không phải tập `res_eligible` thu hẹp dùng cho lưới hợp nhất 5×3, xem `docs/EXPERIMENTS.md`). Thống kê đầy đủ benign/malware theo từng split (đếm trực tiếp từ cột `label`, xem thêm `docs/DATA_COLLECTION.md`):

| Split | Benign | Malware | Tổng | Tỉ lệ malware:benign |
|-------|:------:|:-------:|:----:|:---------------------:|
| `split_train.csv` | 4.066 | 6.115 | 10.181 | 1,50:1 |
| `split_val.csv`   | 872   | 1.311 | 2.183  | 1,50:1 |
| `split_test.csv`  | 872   | 1.311 | 2.183  | 1,50:1 |
| **Tổng**          | **5.810** | **8.737** | **14.547** | **1,50:1** |

- Split chống rò rỉ (grouped/stratified theo dedup SHA-256).
- Ảnh 3 kênh sinh từ `data/processed/224/` (`{sha[:2]}/{sha}.png`).
- Chuẩn hóa per-channel bằng `data/interim/channel_stats.json` (tính trên `split_train`).

## 2. Cấu hình huấn luyện

Cả 4 model dùng **chung cấu hình** (chỉ đổi kiến trúc) — công bằng khi so sánh:

| Tham số | Giá trị |
|---|---|
| `img_size` | 224 |
| `channels` | `full` (gray + entropy + ASCII, `in_chans=3`) |
| `batch_size` | 32 |
| `epochs` (tối đa) | 30, `early_stop_patience=6` |
| Optimizer | AdamW, `lr=1e-4`, `weight_decay=1e-4` |
| AMP | bật |
| `class_weights` | `auto` (bù lệch 1,5:1) |
| Pretrained | ImageNet (`pretrained=true`, không freeze backbone) |
| Seed | 42 |

Config gốc: `configs/detect_{vgg16,resnet50,densenet121,convnext_tiny}_224.yaml`.

## 3. Kết quả — Test set

| Model | Acc | Precision | Recall | F1 | ROC-AUC | Epoch tốt nhất | Tổng epoch chạy | Thời gian/epoch (tb) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| VGG16 | 0.9689 | 0.9777 | 0.9703 | 0.9740 | 0.9901 | 14 | 20 | ~119.5s |
| ResNet50 | 0.9698 | 0.9792 | 0.9703 | 0.9747 | 0.9909 | 16 | 22 | ~66.4s |
| **DenseNet121** ★ | **0.9725** | **0.9830** | 0.9710 | **0.9770** | **0.9940** | 15 | 21 | ~64.8s |
| ConvNeXt-Tiny | 0.9675 | 0.9740 | **0.9718** | 0.9729 | 0.9929 | 5 | 11 | ~73.5s |

★ DenseNet121 tốt nhất trên mọi chỉ số ngoại trừ Recall (ConvNeXt-Tiny nhỉnh hơn không đáng kể). 4 model đều sát nhau (F1 trong khoảng 0.973–0.977) → **pipeline ổn định, không phụ thuộc kiến trúc cụ thể**.

### Ma trận nhầm lẫn (test set, 872 benign + 1.311 malware)

Định dạng `[[TN, FP], [FN, TP]]` (0=benign là lớp âm, 1=malware là lớp dương):

| Model | TN (benign đúng) | FP (benign→malware) | FN (malware→benign) | TP (malware đúng) |
|---|:---:|:---:|:---:|:---:|
| VGG16 | 843 | 29 | 39 | 1.272 |
| ResNet50 | 845 | 27 | 39 | 1.272 |
| DenseNet121 | 850 | 22 | 38 | 1.273 |
| ConvNeXt-Tiny | 838 | 34 | 37 | 1.274 |

- DenseNet121 có FP thấp nhất (22/872 ≈ 2,5% benign bị báo nhầm malware) — quan trọng cho triển khai thực tế (giảm false alarm).
- FN dao động 37–39/1.311 (≈ 2,8–3,0%) ở cả 4 model — khá đồng đều, không model nào bỏ sót malware vượt trội hơn hẳn.

### Kết quả trên validation set (tham khảo, dùng để chọn checkpoint `best.pt`)

| Model | Acc | Precision | Recall | F1 | ROC-AUC |
|---|:---:|:---:|:---:|:---:|:---:|
| VGG16 | 0.9638 | 0.9753 | 0.9641 | 0.9697 | 0.9897 |
| ResNet50 | 0.9679 | 0.9799 | 0.9664 | 0.9731 | 0.9906 |
| DenseNet121 | 0.9684 | 0.9836 | 0.9634 | 0.9734 | 0.9911 |
| ConvNeXt-Tiny | 0.9675 | 0.9762 | 0.9695 | 0.9728 | 0.9913 |

## 4. Nhận định

- **Cả 4 model đều đạt F1 > 0.97, ROC-AUC > 0.99** trên cấu hình 224×224 + full-channel — xác nhận pipeline PE thô → ảnh 3 kênh composite → CNN pretrained hoạt động tốt và ổn định trên kiến trúc.
- **DenseNet121 dẫn đầu** nhưng chênh lệch với ResNet50/VGG16/ConvNeXt-Tiny không lớn (ΔF1 ≤ 0.004) — chưa kiểm định thống kê (n=1 seed/model ở báo cáo này, khác với lưới hợp nhất 5×3 chạy 3 seed cho ResNet50/ConvNeXt-Tiny, xem `docs/EXPERIMENTS.md`).
- **ResNet50 là lựa chọn cân bằng tốc độ/độ chính xác**: F1 chỉ kém DenseNet121 0,0023 nhưng epoch nhanh hơn (~66s vs ~65s tương đương thực ra; VGG16 chậm nhất ~120s/epoch do FC layer lớn).
- ConvNeXt-Tiny hội tụ nhanh nhất (early-stop ở epoch 5) nhưng F1 thấp nhất trong 4 model ở cấu hình này — có thể do learning rate/epoch chưa tối ưu cho kiến trúc transformer-hoá này ở dữ liệu này; điểm cần lưu ý khi so với kết quả tốt hơn nhiều của ConvNeXt-Tiny trong lưới hợp nhất 5×3 trên tập `sweep_*.csv` (F1 lên tới 0,9844 ± 0,0031 ở `full × 224`, xem `docs/EXPERIMENTS.md`) — khác biệt do tập dữ liệu khác nhau (`split_*.csv` toàn bộ ~14.547 mẫu vs `sweep_*.csv` chỉ ~7.860 mẫu res_eligible) và số seed (1 vs 3).

## 5. Nguồn dữ liệu / tái lập

- Config: `configs/detect_{vgg16,resnet50,densenet121,convnext_tiny}_224.yaml`
- Checkpoint + log + figures: `experiments/detect_{vgg16,resnet50,densenet121,convnext_tiny}_224_<timestamp>/`
- Dataset: `data/interim/split_{train,val,test}.csv` + `data/processed/224/`
- Xem thêm: `docs/BACKLOG.md` §S5.3, `docs/DATA_COLLECTION.md` (thống kê split), `docs/EXPERIMENTS.md` (lưới hợp nhất 5×3, kết quả liên quan trên tập khác)
