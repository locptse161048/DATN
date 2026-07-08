# Phân tích chi tiết: VGG16

> Số liệu trong file này được **đo trực tiếp** bằng cách khởi tạo `torchvision.models.vgg16()` và `src.models.factory.build_model("vgg16", ...)` (Python 3.x, torch 2.13 / torchvision 0.28 CPU), không suy đoán từ tài liệu. Xem lệnh kiểm chứng ở §6.

## 1. Cách khởi tạo trong dự án

[`src/models/factory.py:59-65`](../src/models/factory.py):
```python
if name == "vgg16":
    w = models.VGG16_Weights.IMAGENET1K_V1 if pretrained else None
    m = models.vgg16(weights=w)
    m.classifier[6] = nn.Linear(m.classifier[6].in_features, num_classes)
    head = m.classifier[6]
    if in_chans != 3:
        m.features[0] = _new_first_conv(m.features[0], in_chans)
```

## 1.1. "1000 lớp" nghĩa là gì? Vì sao dùng được cho bài toán 2 lớp?

`weights=VGG16_Weights.IMAGENET1K_V1` là bộ trọng số **pretrained trên ImageNet** — bộ ảnh benchmark ~1,2 triệu ảnh, **1000 danh mục đối tượng đời thường** (chó, mèo, xe hơi, bàn phím, quả chuối...). Model gốc được huấn luyện để trả lời "ảnh này thuộc 1 trong 1000 loại nào?", nên lớp cuối cùng có đúng 1000 đầu ra:
```python
classifier[6] == Linear(in_features=4096, out_features=1000)
```
"1000 lớp" ở đây là **số nhãn phân loại (class)**, không liên quan đến số "layer" (tầng mạng) nói ở §3.

Đề tài này chỉ có **2 lớp: benign vs malware**, nên phải thay `Linear(4096, 1000)` → `Linear(4096, 2)` — đây chính là thao tác **"thay head"** ở §5. Phần backbone (13 lớp `Conv2d` + 2 lớp `Linear` đầu của `classifier`, tổng ~130 triệu tham số) **giữ nguyên trọng số ImageNet**, vì các đặc trưng cạnh/texture/hoạ tiết cấp thấp-trung học được từ 1,2 triệu ảnh tự nhiên vẫn hữu ích để nhận diện hoạ tiết trên ảnh byte PE — đây là kỹ thuật **transfer learning**: giữ "con mắt nhìn hoạ tiết" đã học sẵn, chỉ huấn luyện lại "câu trả lời cuối" cho bài toán mới, hiệu quả hơn train from scratch trên tập dữ liệu ~14.500 mẫu (nhỏ hơn ImageNet rất nhiều).

## 2. Cấu trúc gốc (pretrained ImageNet, 1000 lớp)

```
VGG(
  (features): Sequential(            # 31 modules — 5 "khối" conv phân tách bởi MaxPool
    (0):  Conv2d(3, 64,   k=3, s=1, p=1)   (1):  ReLU
    (2):  Conv2d(64, 64,  k=3, s=1, p=1)   (3):  ReLU
    (4):  MaxPool2d(k=2, s=2)                                    # ── khối 1: 2 conv
    (5):  Conv2d(64, 128, k=3, s=1, p=1)   (6):  ReLU
    (7):  Conv2d(128,128, k=3, s=1, p=1)   (8):  ReLU
    (9):  MaxPool2d(k=2, s=2)                                    # ── khối 2: 2 conv
    (10): Conv2d(128,256, k=3, s=1, p=1)   (11): ReLU
    (12): Conv2d(256,256, k=3, s=1, p=1)   (13): ReLU
    (14): Conv2d(256,256, k=3, s=1, p=1)   (15): ReLU
    (16): MaxPool2d(k=2, s=2)                                    # ── khối 3: 3 conv
    (17): Conv2d(256,512, k=3, s=1, p=1)   (18): ReLU
    (19): Conv2d(512,512, k=3, s=1, p=1)   (20): ReLU
    (21): Conv2d(512,512, k=3, s=1, p=1)   (22): ReLU
    (23): MaxPool2d(k=2, s=2)                                    # ── khối 4: 3 conv
    (24): Conv2d(512,512, k=3, s=1, p=1)   (25): ReLU
    (26): Conv2d(512,512, k=3, s=1, p=1)   (27): ReLU
    (28): Conv2d(512,512, k=3, s=1, p=1)   (29): ReLU
    (30): MaxPool2d(k=2, s=2)                                    # ── khối 5: 3 conv
  )
  (avgpool): AdaptiveAvgPool2d(output_size=(7, 7))
  (classifier): Sequential(           # 7 modules
    (0): Linear(25088 → 4096)   (1): ReLU   (2): Dropout(0.5)
    (3): Linear(4096 → 4096)    (4): ReLU   (5): Dropout(0.5)
    (6): Linear(4096 → 1000)                                     # ← head gốc (1000 lớp ImageNet)
  )
)
```

## 3. Đếm layer

| Loại module | Số lượng | Ghi chú |
|---|---:|---|
| `Conv2d` | **13** | phân bố 2-2-3-3-3 qua 5 khối (phân tách bởi 5 `MaxPool2d`) |
| `Linear` | **3** | trong `classifier` |
| `MaxPool2d` | 5 | biên giới giữa các khối |
| `ReLU` | 15 | sau mỗi conv + sau 2 Linear đầu |
| `Dropout` | 2 | trong `classifier`, p=0.5 |
| `AdaptiveAvgPool2d` | 1 | ép output của `features` về đúng 7×7 bất kể `img_size` đầu vào (224/336/448) |

**"16" trong tên "VGG16"** = 13 `Conv2d` + 3 `Linear` = **16 lớp có trọng số** (weight layers) — đúng quy ước đặt tên gốc của kiến trúc (không tính ReLU/Pool/Dropout vì không có tham số học được).

### 3.1. Giải thích từng loại module

| Module | Có tham số học được? | Vai trò |
|---|---|---|
| **`Conv2d`** | Có (weight + bias) | Trượt bộ lọc (kernel) 3×3 qua ảnh để trích đặc trưng cục bộ (cạnh, góc, texture...). Toàn bộ 13 conv của VGG16 dùng kernel 3×3, `stride=1`, `padding=1` → **giữ nguyên kích thước H×W**, chỉ đổi số kênh (VD 64→128). Đây là lớp duy nhất "nhìn thấy" ảnh và học được từ dữ liệu. |
| **`ReLU`** | Không | Hàm kích hoạt phi tuyến `max(0, x)`. Không có tham số, chỉ cắt bỏ giá trị âm — nếu bỏ ReLU, xếp chồng nhiều Conv2d tuyến tính cũng chỉ tương đương 1 Conv2d duy nhất (không học được đặc trưng phức tạp). |
| **`MaxPool2d`** | Không | Lấy giá trị lớn nhất trong mỗi cửa sổ 2×2 → giảm H×W đi một nửa mỗi lần, giúp mạng "nhìn" vùng ảnh rộng hơn ở các lớp sâu và giảm chi phí tính toán. VGG16 có 5 lớp này → ảnh co lại 2⁵=32 lần (VD 224×224 → 7×7 trước `avgpool`). |
| **`Dropout`** | Không (nhưng có tham số `p`) | Trong lúc train, ngẫu nhiên "tắt" 50% neuron (`p=0.5`) ở mỗi lượt forward → chống overfitting cho 2 lớp `Linear` khổng lồ (25088→4096, 4096→4096). Tự động tắt khi `model.eval()` (lúc validate/test). Chi tiết cơ chế xem §3.2. |
| **`Linear`** | Có (weight + bias) | Lớp kết nối đầy đủ (fully-connected): mỗi neuron output nối với MỌI neuron input. 2 lớp đầu học tổ hợp đặc trưng toàn cục, lớp cuối (`classifier[6]`) là **head phân loại** — quyết định benign/malware. |
| **`AdaptiveAvgPool2d`** | Không | Lấy trung bình cộng để ép output của `features` về đúng kích thước cố định `7×7` **bất kể `img_size` đầu vào** (224/336/448) — nhờ vậy `classifier[0]` luôn nhận đúng `512×7×7=25088` chiều, không cần sửa code khi đổi độ phân giải. |

### 3.2. Dropout — giải thích kỹ

VGG16 là **model duy nhất trong 3 model của đề tài có Dropout** (đã kiểm chứng: ResNet50 và DenseNet121 bản gốc torchvision đều **0 Dropout** — xem `docs/code_RESNET50_reference.md` §3.1 và `docs/code_DENSENET121_reference.md` §3.1). Vị trí chính xác trong `classifier`:
```
(0): Linear(25088 → 4096)
(1): ReLU
(2): Dropout(p=0.5, inplace=False)      # ← Dropout thứ 1
(3): Linear(4096 → 4096)
(4): ReLU
(5): Dropout(p=0.5, inplace=False)      # ← Dropout thứ 2
(6): Linear(4096 → 2)                    # head (đã sửa cho bài toán 2 lớp)
```

**Cơ chế hoạt động (lúc train, `model.train()`):**
- Với xác suất `p=0.5`, mỗi neuron ở output của `ReLU` bị **gán về 0** hoàn toàn ngẫu nhiên và độc lập ở mỗi lượt forward (mỗi batch có 1 "mặt nạ" — mask — ngẫu nhiên khác nhau).
- Các neuron còn sống (50% còn lại) được **nhân lên 1/(1-p) = 2 lần** ("inverted dropout") để giữ nguyên kỳ vọng tổng giá trị đầu ra — nhờ vậy không cần chỉnh gì thêm lúc test.
- Tác dụng: buộc mạng **không được phụ thuộc quá mức vào 1 vài neuron cụ thể** — mỗi neuron phải học biểu diễn "đủ tổng quát" để hữu ích ngay cả khi một nửa neuron khác bị tắt ngẫu nhiên. Về bản chất tương đương huấn luyện đồng thời rất nhiều mạng con (sub-network) chia sẻ trọng số, rồi lấy trung bình — giảm overfitting.

**Lúc eval (`model.eval()`, dùng trong `predict()`/`evaluate()` của `train.py`):** Dropout **tự động tắt hoàn toàn** — mọi neuron đều hoạt động, không nhân hệ số, không mask ngẫu nhiên. Đây là lý do `train.py` luôn gọi `model.eval()` trước khi đánh giá val/test ([scripts/train.py:70](../scripts/train.py)) — nếu quên, kết quả đánh giá sẽ ngẫu nhiên/không ổn định giữa các lần chạy.

**Vì sao VGG16 cần Dropout còn ResNet50/DenseNet121 thì không:** VGG16 có 2 lớp `Linear` cực lớn (25088→4096 và 4096→4096, tổng ~119 triệu tham số — chiếm ~88% toàn bộ model) → rất dễ overfitting nếu không có cơ chế chống lại, vì số tham số ở khu vực này lớn hơn nhiều so với ~14.500 mẫu train. Ngược lại, ResNet50/DenseNet121 chỉ có **1 lớp `Linear` duy nhất** nhỏ (2048→2 hoặc 1024→2) nối sau `AdaptiveAvgPool2d` — phần dễ overfit nhất đã bị loại bỏ nhờ thiết kế kiến trúc, và cả 2 model đều dùng `BatchNorm2d` dày đặc (53/121 lớp) làm cơ chế chống overfitting/ổn định huấn luyện thay thế, nên không cần thêm Dropout.

## 4. Tổng số tham số

| Cấu hình | Tổng tham số | Chênh lệch |
|---|---:|---:|
| Gốc pretrained (1000 lớp, `in_chans=3`) | 138.357.544 | — |
| Sau `build_model` cho bài toán 2 lớp (`in_chans=3`) | **134.268.738** | −4.088.806 (do `classifier[6]`: 4096→1000 co lại thành 4096→2) |
| Sau `build_model`, ablation `in_chans=1` | **134.267.586** | −1.152 so với `in_chans=3` (do `features[0]`: Conv2d(3,64,3×3) → Conv2d(1,64,3×3), giảm đúng 64×3×3×(3−1)=1.152 trọng số) |

## 5. Các thay đổi `build_model()` thực sự áp dụng (so với model gốc)

| Vị trí | Trước | Sau | Điều kiện |
|---|---|---|---|
| `classifier[6]` | `Linear(4096, 1000)` | `Linear(4096, num_classes=2)` | **luôn luôn** (mọi cấu hình) |
| `features[0]` | `Conv2d(3, 64, k=3,s=1,p=1)` | `Conv2d(in_chans, 64, k=3,s=1,p=1)`, trọng số kế thừa từ pretrained qua `_new_first_conv()` | **chỉ khi `in_chans != 3`** (ablation `gray1`) |

**Không có gì khác bị đổi** — toàn bộ 12 conv còn lại trong `features`, `avgpool`, và 2 lớp `Linear` đầu của `classifier` (`classifier[0]`, `classifier[3]`) giữ nguyên 100% kiến trúc và trọng số pretrained ImageNet.

Với `freeze_backbone=True`: toàn bộ tham số bị `requires_grad=False`, chỉ `head` (`classifier[6]`) được bật lại `requires_grad=True` để train.

## 6. Kiểm chứng bằng code (đã chạy thật)

```python
from src.models.factory import build_model
import torch

m3 = build_model("vgg16", num_classes=2, pretrained=False, in_chans=3)
m1 = build_model("vgg16", num_classes=2, pretrained=False, in_chans=1)

print(m3.classifier[6])   # Linear(in_features=4096, out_features=2, bias=True)
print(m3.features[0])     # Conv2d(3, 64, kernel_size=(3, 3), stride=(1, 1), padding=(1, 1))
print(m1.features[0])     # Conv2d(1, 64, kernel_size=(3, 3), stride=(1, 1), padding=(1, 1))

x3 = torch.randn(1, 3, 224, 224); x1 = torch.randn(1, 1, 224, 224)
print(m3(x3).shape)  # torch.Size([1, 2])
print(m1(x1).shape)  # torch.Size([1, 2])
```
Kết quả khớp đúng bảng ở §4/§5 — forward pass ra đúng `(1, 2)` cho cả 2 cấu hình kênh.

## 7. Lưu ý riêng cho VGG16

- **Không có skip connection** (khác ResNet50/DenseNet121) — chỉ là chồng thẳng 13 conv 3×3 + 5 max-pool. Đây là kiến trúc "cổ điển" nhất trong 4 model so sánh của đề tài, dùng làm baseline.
- `AdaptiveAvgPool2d((7,7))` làm cho `classifier[0]` luôn nhận đúng `512×7×7=25088` đầu vào **bất kể `img_size`** (224/336/448) — đây là lý do đổi `img_size` trong config chỉ cần sửa 1 dòng, không phải sửa kiến trúc.
- VGG16 có **nhiều tham số nhất** trong 3 model (134,3M sau khi sửa head) — phần lớn nằm ở 2 lớp `Linear` đầu của `classifier` (`25088×4096` và `4096×4096` ≈ 119M tham số, chiếm ~88% tổng model) chứ không phải phần conv.
