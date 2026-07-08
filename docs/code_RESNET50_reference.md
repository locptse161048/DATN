# Phân tích chi tiết: ResNet50

> Số liệu trong file này được **đo trực tiếp** bằng cách khởi tạo `torchvision.models.resnet50()` và `src.models.factory.build_model("resnet50", ...)` (torch 2.13 / torchvision 0.28 CPU), không suy đoán từ tài liệu. Xem lệnh kiểm chứng ở §6.

## 1. Cách khởi tạo trong dự án

[`src/models/factory.py:67-73`](../src/models/factory.py):
```python
elif name == "resnet50":
    w = models.ResNet50_Weights.IMAGENET1K_V2 if pretrained else None
    m = models.resnet50(weights=w)
    m.fc = nn.Linear(m.fc.in_features, num_classes)
    head = m.fc
    if in_chans != 3:
        m.conv1 = _new_first_conv(m.conv1, in_chans)
```
Lưu ý: dùng bộ trọng số **`IMAGENET1K_V2`** (bản huấn luyện lại với recipe cải tiến của torchvision, accuracy ImageNet cao hơn V1), khác với VGG16/DenseNet121 đang dùng `V1`.

## 1.1. "1000 lớp" nghĩa là gì? Vì sao dùng được cho bài toán 2 lớp?

`weights=ResNet50_Weights.IMAGENET1K_V2` là bộ trọng số **pretrained trên ImageNet** — bộ ảnh benchmark ~1,2 triệu ảnh, **1000 danh mục đối tượng đời thường** (chó, mèo, xe hơi, bàn phím, quả chuối...). Model gốc được huấn luyện để trả lời "ảnh này thuộc 1 trong 1000 loại nào?", nên lớp cuối cùng có đúng 1000 đầu ra:
```python
fc == Linear(in_features=2048, out_features=1000)
```
"1000 lớp" ở đây là **số nhãn phân loại (class)**, không liên quan đến số "layer" (tầng mạng, con số 50 trong "ResNet50") nói ở §3.

Đề tài này chỉ có **2 lớp: benign vs malware**, nên phải thay `Linear(2048, 1000)` → `Linear(2048, 2)` — đây chính là thao tác **"thay head"** ở §5. Phần backbone (49 lớp `Conv2d` xếp trong 16 `Bottleneck` block, ~23,5 triệu tham số) **giữ nguyên trọng số ImageNet**, vì các đặc trưng cạnh/texture/hoạ tiết cấp thấp-trung học được từ 1,2 triệu ảnh tự nhiên vẫn hữu ích để nhận diện hoạ tiết trên ảnh byte PE — đây là kỹ thuật **transfer learning**: giữ "con mắt nhìn hoạ tiết" đã học sẵn, chỉ huấn luyện lại "câu trả lời cuối" cho bài toán mới, hiệu quả hơn train from scratch trên tập dữ liệu ~14.500 mẫu (nhỏ hơn ImageNet rất nhiều).

## 2. Cấu trúc gốc (pretrained ImageNet, 1000 lớp)

```
ResNet(
  (conv1): Conv2d(3, 64, kernel_size=7, stride=2, padding=3, bias=False)   # stem
  (bn1):   BatchNorm2d(64)
  (relu):  ReLU
  (maxpool): MaxPool2d(kernel_size=3, stride=2, padding=1)

  (layer1): Sequential[ 3 × Bottleneck ]   # 64→256 kênh,  stride 1 (giữ H×W)
  (layer2): Sequential[ 4 × Bottleneck ]   # 256→512 kênh, stride 2 ở block đầu (giảm 1/2 H×W)
  (layer3): Sequential[ 6 × Bottleneck ]   # 512→1024 kênh, stride 2 ở block đầu
  (layer4): Sequential[ 3 × Bottleneck ]   # 1024→2048 kênh, stride 2 ở block đầu

  (avgpool): AdaptiveAvgPool2d(output_size=(1, 1))
  (fc): Linear(in_features=2048, out_features=1000, bias=True)           # head gốc
)
```

Cấu trúc 1 **Bottleneck block** (vd `layer1[0]`, block đầu tiên có thêm nhánh `downsample` để khớp shape với skip connection):
```
Bottleneck(
  (conv1): Conv2d(64,  64,  k=1)  (bn1)  # nén kênh (1×1)
  (conv2): Conv2d(64,  64,  k=3, padding=1[, stride=2 nếu là block đầu của layer2/3/4])  (bn2)  # conv chính (3×3)
  (conv3): Conv2d(64,  256, k=1)  (bn3)  # mở rộng kênh lại (1×1) ×4
  (relu)
  (downsample): Sequential(Conv2d(64, 256, k=1[, stride=2]), BatchNorm2d(256))  # chỉ có ở block ĐẦU mỗi layer
)
# output = relu(conv3(...) + downsample(input))   ← skip connection (residual)
```

## 3. Đếm layer

| Loại module | Số lượng | Ghi chú |
|---|---:|---|
| `Conv2d` | **53** | = 1 (stem `conv1`) + 48 (16 block × 3 conv/block) + 4 (`downsample` conv, 1 mỗi layer1-4) |
| `BatchNorm2d` | 53 | 1-1 theo từng `Conv2d` |
| `Bottleneck` block | **16** | phân bố `layer1..4` = **3 + 4 + 6 + 3** |
| `Linear` | 1 | `fc` (head) |
| `MaxPool2d` | 1 | ngay sau stem |

**"50" trong tên "ResNet50"** = 49 `Conv2d` (1 stem + 48 trong bottleneck) + 1 `Linear` (`fc`) = **50 lớp có trọng số**. Số 4 `downsample` conv (projection shortcut) **không tính** vào con số 50 theo quy ước gốc của paper (chúng chỉ để khớp shape cho phép cộng residual, không nằm trên "main path" chính).

### 3.1. Giải thích từng loại module

| Module | Có tham số học được? | Vai trò |
|---|---|---|
| **`Conv2d`** | Có (weight, `bias=False` vì đã có `BatchNorm2d` ngay sau) | Trích đặc trưng cục bộ. ResNet50 dùng 3 loại kernel: `conv1` stem (7×7, stride 2 — nhìn vùng rộng ngay từ đầu để giảm nhanh kích thước ảnh); `conv1`/`conv3` trong mỗi Bottleneck (1×1 — chỉ trộn/nén kênh, không nhìn không gian xung quanh); `conv2` trong Bottleneck (3×3 — lớp duy nhất thực sự "nhìn" không gian trong mỗi block). |
| **`BatchNorm2d`** | Có (scale `γ` + shift `β`, cộng thống kê running mean/var) | Chuẩn hoá lại phân phối giá trị sau mỗi conv (trừ mean, chia std theo từng kênh) trước khi vào ReLU → giúp train ổn định hơn, cho phép learning rate cao hơn, giảm phụ thuộc vào cách khởi tạo trọng số. Đây là lý do ResNet50 có đúng 53 `BatchNorm2d` đi kèm 53 `Conv2d` (1-1). |
| **`ReLU`** | Không | Hàm kích hoạt phi tuyến `max(0,x)`, dùng lại **cùng 1 instance** cho nhiều vị trí trong mỗi Bottleneck (tiết kiệm bộ nhớ vì `inplace=True`, không cần tham số). |
| **`MaxPool2d`** | Không | Chỉ xuất hiện **1 lần duy nhất** ngay sau stem (`conv1`+`bn1`+`relu`) để giảm nhanh H×W trước khi vào `layer1` — khác VGG16 dùng MaxPool lặp lại 5 lần xen giữa các conv. |
| **`Bottleneck`** | (khối ghép, không phải 1 loại module đơn) | Đơn vị lặp lại cơ bản của ResNet: nén kênh (1×1) → xử lý không gian (3×3) → mở rộng kênh lại (1×1), rồi **cộng (add) trực tiếp input vào output** (residual/skip connection) trước ReLU cuối. Đây là điểm khác biệt cốt lõi so với VGG16 (không có phép cộng này) — cho phép huấn luyện mạng sâu (50 lớp) mà gradient không bị triệt tiêu. |
| **`downsample` (Sequential: Conv2d 1×1 + BatchNorm2d)** | Có | Chỉ xuất hiện ở **block đầu tiên** của mỗi `layer1..4`, dùng để biến đổi input (đổi số kênh/giảm H×W bằng stride) cho khớp shape với output `conv3`, để phép cộng residual thực hiện được. |
| **`AdaptiveAvgPool2d`** | Không | Ép feature map cuối cùng (2048 kênh, H×W bất kỳ tuỳ `img_size`) về đúng `1×1` bằng cách lấy trung bình toàn bộ không gian mỗi kênh → ra thẳng vector 2048 chiều cho `fc`, không cần lớp `Linear` trung gian khổng lồ như VGG16. |
| **`Linear`** | Có (weight + bias) | Chỉ 1 lớp duy nhất (`fc`) — nhận vector 2048 chiều, là **head phân loại** quyết định benign/malware. |


### 3.2. BatchNorm2d — giải thích kỹ

**Std (độ lệch chuẩn — standard deviation)** là một con số đo **mức độ phân tán/dao động** của một tập giá trị quanh giá trị trung bình (mean) của chúng. Cách tính: lấy độ lệch của từng giá trị so với mean, bình phương lên (để loại dấu âm), lấy trung bình các bình phương đó (= **variance**, phương sai), rồi khai căn bậc 2 → ra **std**. Ví dụ tập `[2,4,4,4,6,6,6,8]` có mean=5, variance=3, std=√3≈1.73. Std càng lớn thì giá trị càng tản mát, càng nhỏ thì càng co cụm quanh mean.

**"Trừ mean, chia std" (chuẩn hoá)** là phép biến đổi:
```
x_norm = (x - mean) / std
```
Áp dụng công thức này lên bất kỳ tập giá trị nào, kết quả luôn có **mean ≈ 0 và std ≈ 1** — dù giá trị gốc dao động trong khoảng nào (2–8, hay 200–800, hay âm), sau chuẩn hoá đều quy về cùng 1 "thang đo chung".

**Áp dụng trong `BatchNorm2d`:** sau mỗi `Conv2d`, giá trị pixel ở mỗi kênh (channel) output có thể dao động rất khác nhau giữa các kênh (kênh này quanh 0, kênh kia quanh 1000, do trọng số conv khuếch đại/thu nhỏ khác nhau). `BatchNorm2d` tính **mean và std riêng cho từng kênh, trên toàn bộ batch**, rồi chuẩn hoá:
```
x_norm = (x - mean_kênh) / std_kênh        # đưa mọi kênh về mean≈0, std≈1
y = γ × x_norm + β                          # γ, β là 2 tham số HỌC ĐƯỢC, cho phép mạng tự điều chỉnh lại thang đo nếu cần
```
Lợi ích:
- **Train ổn định hơn** — lớp sau không bị "sốc" vì input dao động thất thường giữa các kênh.
- **Cho phép learning rate cao hơn** — gradient không dễ "nổ" hay "biến mất" do input lệch thang đo.
- **Giảm phụ thuộc vào cách khởi tạo trọng số ban đầu** — dù trọng số conv làm output lệch thang đo thế nào, BatchNorm cũng kéo nó về chuẩn trước khi truyền tiếp lớp sau.

Trong code, `mean`/`std` lúc **train** tính trên chính batch hiện tại; đồng thời BatchNorm âm thầm cập nhật `running_mean`/`running_var` (trung bình trượt qua các batch) — lúc `model.eval()` (validate/test), dùng thẳng `running_mean`/`running_var` đã tích luỹ thay vì tính lại trên batch, để kết quả dự đoán không phụ thuộc vào các mẫu khác cùng batch.

## 4. Tổng số tham số

| Cấu hình | Tổng tham số | Chênh lệch |
|---|---:|---:|
| Gốc pretrained (1000 lớp, `in_chans=3`) | 25.557.032 | — |
| Sau `build_model` cho bài toán 2 lớp (`in_chans=3`) | **23.512.130** | −2.044.902 (do `fc`: 2048→1000 co lại thành 2048→2) |
| Sau `build_model`, ablation `in_chans=1` | **23.505.858** | −6.272 so với `in_chans=3` (do `conv1`: Conv2d(3,64,7×7) → Conv2d(1,64,7×7), giảm đúng 64×7×7×(3−1)=6.272 trọng số) |

So với VGG16 (134,3M), ResNet50 **nhẹ hơn ~5,7 lần** dù có nhiều "lớp" hơn về danh nghĩa (50 vs 16) — vì không có 2 lớp `Linear` khổng lồ (VGG có `25088×4096` và `4096×4096`), thay vào đó dùng `AdaptiveAvgPool2d(1,1)` nén thẳng về vector 2048 chiều rồi mới vào `Linear` duy nhất.

## 5. Các thay đổi `build_model()` thực sự áp dụng (so với model gốc)

| Vị trí | Trước | Sau | Điều kiện |
|---|---|---|---|
| `fc` | `Linear(2048, 1000)` | `Linear(2048, num_classes=2)` | **luôn luôn** |
| `conv1` (stem) | `Conv2d(3, 64, k=7,s=2,p=3, bias=False)` | `Conv2d(in_chans, 64, k=7,s=2,p=3, bias=False)`, trọng số kế thừa qua `_new_first_conv()` | **chỉ khi `in_chans != 3`** (ablation `gray1`) |

**Không đổi gì khác** — toàn bộ 16 `Bottleneck` block trong `layer1..4` (48 conv + 4 downsample conv + 53 BatchNorm) giữ nguyên kiến trúc và trọng số pretrained `IMAGENET1K_V2`.

`freeze_backbone=True`: đóng băng toàn bộ, chỉ `fc` được train.

## 6. Kiểm chứng bằng code (đã chạy thật)

```python
from src.models.factory import build_model
import torch

m3 = build_model("resnet50", num_classes=2, pretrained=False, in_chans=3)
m1 = build_model("resnet50", num_classes=2, pretrained=False, in_chans=1)

print(m3.fc)      # Linear(in_features=2048, out_features=2, bias=True)
print(m3.conv1)   # Conv2d(3, 64, kernel_size=(7, 7), stride=(2, 2), padding=(3, 3), bias=False)
print(m1.conv1)   # Conv2d(1, 64, kernel_size=(7, 7), stride=(2, 2), padding=(3, 3), bias=False)

x3 = torch.randn(1, 3, 224, 224); x1 = torch.randn(1, 1, 224, 224)
print(m3(x3).shape)  # torch.Size([1, 2])
print(m1(x1).shape)  # torch.Size([1, 2])
```
Kết quả khớp đúng bảng ở §4/§5.

## 7. Lưu ý riêng cho ResNet50

- **Có skip connection (residual)** — mỗi `Bottleneck` cộng thẳng input vào output (`output = F(x) + x`, hoặc `F(x) + downsample(x)` khi shape đổi). Đây là khác biệt kiến trúc quan trọng nhất so với VGG16 (không có), giúp gradient truyền sâu hơn qua 50 lớp mà không bị vanishing.
- 4 `downsample` conv (projection shortcut, kernel 1×1) chỉ xuất hiện ở **block đầu tiên** của mỗi `layer1..4` — nơi số kênh hoặc stride thay đổi (VD `layer2[0]` giảm H×W một nửa và tăng kênh 256→512), cần conv 1×1 để khớp shape trước khi cộng residual. Từ block thứ 2 trở đi trong cùng layer, input/output cùng shape nên không cần downsample.
- Dùng bộ trọng số `IMAGENET1K_V2` (không phải V1 như 2 model kia) — nếu so sánh công bằng độ "mạnh" của pretrained giữa các model trong lưới 5×3, cần lưu ý ResNet50 đang dùng recipe pretrain mới hơn/tốt hơn V1.
