# Phân tích chi tiết: DenseNet121

> Số liệu trong file này được **đo trực tiếp** bằng cách khởi tạo `torchvision.models.densenet121()` và `src.models.factory.build_model("densenet121", ...)` (torch 2.13 / torchvision 0.28 CPU), không suy đoán từ tài liệu. Xem lệnh kiểm chứng ở §6.

## 1. Cách khởi tạo trong dự án

[`src/models/factory.py:75-81`](../src/models/factory.py):
```python
elif name == "densenet121":
    w = models.DenseNet121_Weights.IMAGENET1K_V1 if pretrained else None
    m = models.densenet121(weights=w)
    m.classifier = nn.Linear(m.classifier.in_features, num_classes)
    head = m.classifier
    if in_chans != 3:
        m.features.conv0 = _new_first_conv(m.features.conv0, in_chans)
```

## 1.1. "1000 lớp" nghĩa là gì? Vì sao dùng được cho bài toán 2 lớp?

`weights=DenseNet121_Weights.IMAGENET1K_V1` là bộ trọng số **pretrained trên ImageNet** — bộ ảnh benchmark ~1,2 triệu ảnh, **1000 danh mục đối tượng đời thường** (chó, mèo, xe hơi, bàn phím, quả chuối...). Model gốc được huấn luyện để trả lời "ảnh này thuộc 1 trong 1000 loại nào?", nên lớp cuối cùng có đúng 1000 đầu ra:
```python
classifier == Linear(in_features=1024, out_features=1000)
```
"1000 lớp" ở đây là **số nhãn phân loại (class)**, không liên quan đến số "layer" (tầng mạng, con số 121 trong "DenseNet121") nói ở §3.

Đề tài này chỉ có **2 lớp: benign vs malware**, nên phải thay `Linear(1024, 1000)` → `Linear(1024, 2)` — đây chính là thao tác **"thay head"** ở §5. Phần backbone (120 lớp `Conv2d` xếp trong 58 `_DenseLayer`, ~7 triệu tham số) **giữ nguyên trọng số ImageNet**, vì các đặc trưng cạnh/texture/hoạ tiết cấp thấp-trung học được từ 1,2 triệu ảnh tự nhiên vẫn hữu ích để nhận diện hoạ tiết trên ảnh byte PE — đây là kỹ thuật **transfer learning**: giữ "con mắt nhìn hoạ tiết" đã học sẵn, chỉ huấn luyện lại "câu trả lời cuối" cho bài toán mới, hiệu quả hơn train from scratch trên tập dữ liệu ~14.500 mẫu (nhỏ hơn ImageNet rất nhiều).

## 2. Cấu trúc gốc (pretrained ImageNet, 1000 lớp)

```
DenseNet(
  (features): Sequential-like (module con đặt tên):
    conv0 -> Conv2d(3, 64, k=7, s=2, p=3, bias=False)     # stem
    norm0 -> BatchNorm2d(64)
    relu0 -> ReLU
    pool0 -> MaxPool2d(k=3, s=2, p=1)

    denseblock1 -> 6  × _DenseLayer      # kênh: 64  → 64+6×32  = 256
    transition1 -> _Transition            # nén kênh 256 → 128, giảm 1/2 H×W
    denseblock2 -> 12 × _DenseLayer      # kênh: 128 → 128+12×32 = 512
    transition2 -> _Transition            # nén kênh 512 → 256, giảm 1/2 H×W
    denseblock3 -> 24 × _DenseLayer      # kênh: 256 → 256+24×32 = 1024
    transition3 -> _Transition            # nén kênh 1024 → 512, giảm 1/2 H×W
    denseblock4 -> 16 × _DenseLayer      # kênh: 512 → 512+16×32 = 1024
    norm5 -> BatchNorm2d(1024)             # BN cuối, KHÔNG có transition sau denseblock4

  (classifier): Linear(in_features=1024, out_features=1000, bias=True)   # head gốc
)
```

Cấu trúc 1 **`_DenseLayer`** (vd `denseblock1.denselayer1` — mọi dense layer trong cùng 1 denseblock có cấu trúc giống hệt, chỉ khác số kênh input do nhận nối chồng (concat) output của mọi layer trước đó trong cùng block):
```
_DenseLayer(
  (norm1) (relu1)
  (conv1): Conv2d(in, 128, k=1)     # bottleneck 1×1, nén kênh trước khi conv 3×3 (growth_rate×4=32×4=128)
  (norm2) (relu2)
  (conv2): Conv2d(128, 32, k=3, p=1)  # sinh ra đúng growth_rate=32 kênh mới
)
# output = concat([input, conv2_output], dim=kênh)   ← "dense connection": nối chồng, KHÔNG cộng như ResNet
```

Cấu trúc 1 **`_Transition`** (giữa các denseblock, nén kênh + giảm kích thước ảnh):
```
_Transition(
  (norm) (relu)
  (conv): Conv2d(in, in/2, k=1)     # nén kênh còn 1 nửa
  (pool): AvgPool2d(k=2, s=2)       # giảm H×W còn 1 nửa
)
```

## 3. Đếm layer

| Loại module | Số lượng | Ghi chú |
|---|---:|---|
| `Conv2d` | **120** | = 1 (`conv0` stem) + 116 (58 dense layer × 2 conv) + 3 (`conv` trong `transition1/2/3`) |
| `BatchNorm2d` | 121 | = 120 (1-1 theo mỗi conv) + 1 (`norm5` cuối) |
| `_DenseLayer` | **58** | phân bố `denseblock1..4` = **6 + 12 + 24 + 16** |
| `_Transition` | 3 | giữa denseblock1↔2, 2↔3, 3↔4 (không có transition sau denseblock4) |
| `Linear` | 1 | `classifier` (head) |

**"121" trong tên "DenseNet121"** = 120 `Conv2d` + 1 `Linear` (`classifier`) = **121 lớp có trọng số**.

### 3.1. Giải thích từng loại module

| Module | Có tham số học được? | Vai trò |
|---|---|---|
| **`Conv2d`** | Có (`bias=False` vì có `BatchNorm2d` ngay trước) | Trích đặc trưng. Trong mỗi `_DenseLayer`: `conv1` (1×1) nén số kênh input (đang tăng dần do concat) xuống còn 128 trước khi `conv2` (3×3) sinh ra đúng 32 kênh mới (`growth_rate`). Trong `_Transition`: 1 `conv` (1×1) nén kênh còn một nửa. |
| **`BatchNorm2d`** | Có (γ, β + running stats) | Chuẩn hoá phân phối trước mỗi ReLU/Conv, giúp train ổn định. DenseNet đặt **BN trước Conv** trong mỗi `_DenseLayer` (thứ tự "pre-activation": norm→relu→conv), khác ResNet đặt BN **sau** Conv — đây là khác biệt thiết kế giữa 2 kiến trúc. |
| **`ReLU`** | Không | Hàm kích hoạt phi tuyến, đứng giữa mỗi cặp `norm→relu→conv` trong `_DenseLayer` và `_Transition`. |
| **`MaxPool2d`** | Không | Chỉ 1 lần duy nhất ở `pool0` ngay sau stem, giống vai trò trong ResNet50 — giảm nhanh H×W trước khi vào `denseblock1`. |
| **`_DenseLayer`** | (khối ghép) | Đơn vị lặp lại cơ bản: nhận **toàn bộ output của mọi layer trước đó trong cùng denseblock** (nối chồng theo kênh, `concat`), xử lý qua `conv1`(1×1)→`conv2`(3×3), rồi **nối** (không phải cộng) kết quả mới vào chuỗi input cho layer tiếp theo. Đây là "dense connection" — khác hẳn "residual connection" (cộng) của ResNet. |
| **`_Transition`** | (khối ghép: BN + ReLU + Conv1×1 + AvgPool) | Đứng giữa 2 denseblock liên tiếp: **bắt buộc phải có** vì nếu không, số kênh sẽ cộng dồn tăng vô hạn qua từng denseblock (mỗi denseblock tự nó đã làm kênh tăng gấp nhiều lần). Nén kênh còn 1 nửa + giảm H×W còn 1 nửa (đóng vai trò tương đương `MaxPool2d` lặp lại của VGG16 hay stride-2 conv của ResNet50). |
| **`AvgPool2d`** | Không | Nằm trong `_Transition`, lấy trung bình cửa sổ 2×2 để giảm H×W — dùng **trung bình** thay vì **max** (như VGG16/ResNet) vì mục tiêu là nén mượt thông tin đã tích luỹ từ nhiều layer trước, không phải chỉ giữ đặc trưng nổi bật nhất. |
| **`Linear`** | Có (weight + bias) | Chỉ 1 lớp duy nhất (`classifier`) — nhận vector 1024 chiều sau `norm5` + global pooling, là **head phân loại** quyết định benign/malware. |


### 3.2. BatchNorm2d — giải thích kỹ

**Std (độ lệch chuẩn — standard deviation)** là một con số đo **mức độ phân tán/dao động** của một tập giá trị quanh giá trị trung bình (mean) của chúng. Cách tính: lấy độ lệch của từng giá trị so với mean, bình phương lên (để loại dấu âm), lấy trung bình các bình phương đó (= **variance**, phương sai), rồi khai căn bậc 2 → ra **std**. Ví dụ tập `[2,4,4,4,6,6,6,8]` có mean=5, variance=3, std=√3≈1.73. Std càng lớn thì giá trị càng tản mát, càng nhỏ thì càng co cụm quanh mean.

**"Trừ mean, chia std" (chuẩn hoá)** là phép biến đổi:
```
x_norm = (x - mean) / std
```
Áp dụng công thức này lên bất kỳ tập giá trị nào, kết quả luôn có **mean ≈ 0 và std ≈ 1** — dù giá trị gốc dao động trong khoảng nào, sau chuẩn hoá đều quy về cùng 1 "thang đo chung".

**Áp dụng trong `BatchNorm2d`:** sau mỗi `Conv2d`, giá trị pixel ở mỗi kênh (channel) output có thể dao động rất khác nhau giữa các kênh (do trọng số conv khuếch đại/thu nhỏ khác nhau). `BatchNorm2d` tính **mean và std riêng cho từng kênh, trên toàn bộ batch**, rồi chuẩn hoá:
```
x_norm = (x - mean_kênh) / std_kênh        # đưa mọi kênh về mean≈0, std≈1
y = γ × x_norm + β                          # γ, β là 2 tham số HỌC ĐƯỢC, cho phép mạng tự điều chỉnh lại thang đo nếu cần
```
Lợi ích: train ổn định hơn (lớp sau không bị "sốc" vì input dao động thất thường giữa các kênh), cho phép learning rate cao hơn, giảm phụ thuộc vào cách khởi tạo trọng số ban đầu.

Điểm đáng chú ý ở DenseNet121: thứ tự trong mỗi `_DenseLayer` là **`norm→relu→conv`** (BatchNorm đặt **trước** Conv, gọi là "pre-activation") — ngược với ResNet50 đặt BatchNorm **sau** Conv (`conv→bn→relu`). Trong code, `mean`/`std` lúc **train** tính trên chính batch hiện tại; BatchNorm đồng thời âm thầm cập nhật `running_mean`/`running_var` (trung bình trượt qua các batch) — lúc `model.eval()` (validate/test), dùng thẳng `running_mean`/`running_var` đã tích luỹ thay vì tính lại trên batch.

## 4. Tổng số tham số

| Cấu hình | Tổng tham số | Chênh lệch |
|---|---:|---:|
| Gốc pretrained (1000 lớp, `in_chans=3`) | 7.978.856 | — |
| Sau `build_model` cho bài toán 2 lớp (`in_chans=3`) | **6.955.906** | −1.022.950 (do `classifier`: 1024→1000 co lại thành 1024→2) |
| Sau `build_model`, ablation `in_chans=1` | **6.949.634** | −6.272 so với `in_chans=3` (do `features.conv0`: Conv2d(3,64,7×7) → Conv2d(1,64,7×7), giảm đúng 64×7×7×(3−1)=6.272 trọng số) |

DenseNet121 là model **nhẹ nhất** trong 3 model (~7M tham số, chỉ bằng ~5% VGG16 và ~30% ResNet50) — nhờ cơ chế "dense connection" tái sử dụng đặc trưng (feature reuse) nên mỗi lớp chỉ cần sinh thêm `growth_rate=32` kênh mới thay vì phải học lại từ đầu, giảm mạnh số tham số dù có tới 121 lớp.

## 5. Các thay đổi `build_model()` thực sự áp dụng (so với model gốc)

| Vị trí | Trước | Sau | Điều kiện |
|---|---|---|---|
| `classifier` | `Linear(1024, 1000)` | `Linear(1024, num_classes=2)` | **luôn luôn** |
| `features.conv0` | `Conv2d(3, 64, k=7,s=2,p=3, bias=False)` | `Conv2d(in_chans, 64, k=7,s=2,p=3, bias=False)`, trọng số kế thừa qua `_new_first_conv()` | **chỉ khi `in_chans != 3`** (ablation `gray1`) |

**Không đổi gì khác** — toàn bộ 58 `_DenseLayer` (116 conv) + 3 `_Transition` (3 conv) + `norm5` giữ nguyên kiến trúc và trọng số pretrained `IMAGENET1K_V1`.

`freeze_backbone=True`: đóng băng toàn bộ, chỉ `classifier` được train.

## 6. Kiểm chứng bằng code (đã chạy thật)

```python
from src.models.factory import build_model
import torch

m3 = build_model("densenet121", num_classes=2, pretrained=False, in_chans=3)
m1 = build_model("densenet121", num_classes=2, pretrained=False, in_chans=1)

print(m3.classifier)        # Linear(in_features=1024, out_features=2, bias=True)
print(m3.features.conv0)    # Conv2d(3, 64, kernel_size=(7, 7), stride=(2, 2), padding=(3, 3), bias=False)
print(m1.features.conv0)    # Conv2d(1, 64, kernel_size=(7, 7), stride=(2, 2), padding=(3, 3), bias=False)

x3 = torch.randn(1, 3, 224, 224); x1 = torch.randn(1, 1, 224, 224)
print(m3(x3).shape)  # torch.Size([1, 2])
print(m1(x1).shape)  # torch.Size([1, 2])
```
Kết quả khớp đúng bảng ở §4/§5.

## 7. Lưu ý riêng cho DenseNet121

- **Dense connection ≠ Residual connection (ResNet):** ResNet **cộng** (`+`) output vào input; DenseNet **nối chồng theo chiều kênh** (`concat`) output của MỌI layer trước đó trong cùng denseblock vào input của layer hiện tại. Vì vậy số kênh input của mỗi `_DenseLayer` **tăng dần** trong cùng 1 denseblock (VD `denseblock1`: layer1 nhận 64 kênh, layer6 nhận 64+5×32=224 kênh).
- `_Transition` là bước bắt buộc giữa các denseblock để **nén kênh lại** (nếu không, số kênh sẽ tăng vô hạn qua các block) và giảm H×W — tương tự vai trò của `MaxPool2d` trong VGG hay stride-2 conv trong ResNet, nhưng dùng `AvgPool2d` + conv 1×1 nén kênh trước.
- `growth_rate=32` (số kênh mới mỗi `_DenseLayer` sinh ra) là hằng số kiến trúc gốc, không đổi trong `factory.py`.
- Vì tham số ít nhất trong 3 model nhưng số lớp danh nghĩa nhiều nhất (121), DenseNet121 thường **chậm hơn** về tốc độ thực thi (nhiều lệnh gọi tuần tự nhỏ) dù nhẹ hơn về bộ nhớ tham số — đáng lưu ý khi so sánh trong bảng accuracy-vs-cost (`cost.json` đo cả GMACs lẫn thời gian thực tế, không chỉ số tham số).
