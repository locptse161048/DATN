# ConvNeXt-Tiny — kiến trúc và vai trò trong đồ án

> Tài liệu giải thích model **ConvNeXt-Tiny** dùng làm một trong bốn kiến trúc so sánh của đồ án (VGG16 · ResNet50 · DenseNet121 · **ConvNeXt-Tiny**). Nguồn gốc: Zhuang Liu và cộng sự, *"A ConvNet for the 2020s"*, CVPR 2022. Bản dùng trong đồ án: `torchvision.models.convnext_tiny` (pretrained ImageNet-1k), sửa lớp conv đầu để nhận 3 kênh composite.

---

## 0. Thông số nhanh

| Chỉ số | Giá trị |
| :---- | :---- |
| Tham số (parameters) | ~28,6 triệu |
| FLOPs @224×224 | ~4,5 GFLOPs |
| Cấu trúc stage (số block) | **[3, 3, 9, 3] = 18 block** |
| Số kênh mỗi stage (dims) | [96, 192, 384, 768] |
| Top-1 ImageNet-1k | ~82,1% |
| Lớp có trọng số chính (conv + linear) | **≈ 59 lớp** (xem §1) |

Để đối chiếu: ResNet-50 có ~25,6M tham số, ~4,1 GFLOPs — **cùng hạng** với ConvNeXt-Tiny. Đây là điểm mấu chốt của §2.

---

## 1. Có bao nhiêu lớp có trọng số?

### 1.1. Trả lời ngắn

Nếu đếm theo **đúng quy ước đặt tên độ sâu** của họ ResNet (ResNet-50 = 50 lớp = 49 conv + 1 fully-connected), thì ConvNeXt-Tiny có **≈ 59 lớp có trọng số** (tích chập + tuyến tính). Con số này **không** phải là tên gọi chính thức (người ta gọi nó là "Tiny" theo kích thước, không theo số lớp), nhưng đếm ra được minh bạch như dưới đây.

### 1.2. Cách đếm (minh bạch để bảo vệ)

ConvNeXt-Tiny gồm 4 khối chính: **stem → 4 stage (18 block) → các lớp hạ mẫu xen giữa → đầu phân loại**.

| Thành phần | Số lớp trọng số (conv/linear) | Chi tiết |
| :---- | :----: | :---- |
| **Stem** ("patchify") | 1 | 1 conv 4×4, stride 4 (biến ảnh thành các "mảnh" 4×4) |
| **Lớp hạ mẫu** giữa các stage | 3 | 3 conv 2×2, stride 2 (giữa stage 1→2, 2→3, 3→4) |
| **18 block** × 3 lớp/block | 54 | mỗi block = *depthwise conv 7×7* + *pointwise conv 1×1 (mở rộng ×4)* + *pointwise conv 1×1 (thu về)* |
| **Đầu phân loại** (head) | 1 | 1 lớp fully-connected (768 → số lớp) |
| **TỔNG (conv + linear)** | **59** | |

Phép tính phần block: 18 block × 3 = 54. Cộng stem (1) + hạ mẫu (3) + head (1) = **59**.

### 1.3. Vì sao mỗi block có đúng 3 lớp trọng số

Một block ConvNeXt mô phỏng cấu trúc của một khối Transformer, gồm ba lớp **có trọng số** xếp liên tiếp:

1. **Depthwise conv 7×7** — mỗi kênh được tích chập riêng bằng một nhân 7×7 lớn. Vai trò giống "trộn thông tin theo không gian" (tương tự self-attention thu thập ngữ cảnh rộng), nhưng rất rẻ vì tách theo kênh.
2. **Pointwise conv 1×1 (mở rộng)** — nở số kênh lên gấp 4 lần. Đây là lớp "trộn thông tin giữa các kênh" đầu tiên của khối MLP.
3. **Pointwise conv 1×1 (thu hẹp)** — ép số kênh về như cũ. Hoàn tất khối MLP kiểu "nút cổ chai ngược" (inverted bottleneck).

Giữa chúng có GELU (hàm kích hoạt, **không** có trọng số) và các phép chuẩn hoá.

### 1.4. Những thành phần CÓ tham số học được nhưng KHÔNG tính là "lớp"

Để trung thực trong báo cáo, cần phân biệt: ngoài 59 lớp trên, ConvNeXt-Tiny còn nhiều **tham số học được** khác nhưng theo quy ước không đếm vào "số lớp":

- **LayerNorm** — có **23** lớp chuẩn hoá (1 ở stem + 3 ở các lớp hạ mẫu + 18 trong các block + 1 trước head). Mỗi cái có hệ số γ, β học được, nhưng là *chuẩn hoá* chứ không phải lớp biến đổi đặc trưng.
- **Layer Scale** — mỗi block có một vector hệ số γ (per-channel) nhân vào đầu ra: **18** vector.
- **Bias** của các conv/linear.

=> Nếu đếm **mọi mô-đun có tham số học được** thì ra ~100; nếu đếm **đúng như cách đặt tên độ sâu ResNet** (chỉ conv + linear trên đường truyền chính) thì ra **≈ 59**. Con số đáng dùng trong báo cáo là **59 lớp trọng số**, kèm ghi chú rằng độ sâu này tương đương ResNet-50 về hạng tham số/FLOPs.

> Lưu ý phân biệt: **"số lớp có trọng số" khác "số tham số"**. ConvNeXt-Tiny có ~59 lớp nhưng ~28,6M tham số — phần lớn tham số nằm ở các stage sâu (kênh 384, 768) chứ không phải ở số lớp.

---

## 2. Vì sao chọn ConvNeXt-Tiny làm đại diện cho "ResNet hiện đại hoá"

### 2.1. Vì đó chính là mục tiêu thiết kế gốc của ConvNeXt

Điểm đặc biệt của bài báo ConvNeXt (2022) là: các tác giả **xuất phát thẳng từ một ResNet-50** rồi áp dụng lần lượt các cải tiến "hiện đại" (học được từ Vision Transformer / Swin Transformer), đo lại độ chính xác sau **mỗi** bước. Nói cách khác, ConvNeXt **theo đúng nghĩa đen là "ResNet được hiện đại hoá từng bước"** — không phải một kiến trúc mới không liên quan. Lộ trình cải tiến đó gồm:

1. **Công thức huấn luyện hiện đại** — AdamW, nhiều epoch hơn, augmentation mạnh (Mixup, CutMix, RandAugment). Chỉ riêng đổi cách train đã nâng ResNet-50 từ ~76,1% lên ~78,8%.
2. **Thiết kế vĩ mô** — đổi tỉ lệ tính toán giữa các stage thành (3,3,9,3) giống Swin-Tiny; thay stem 7×7/maxpool của ResNet bằng **"patchify" conv 4×4 stride 4** (giống cách ViT cắt ảnh thành mảnh).
3. **"ResNeXt-hoá"** — dùng **depthwise convolution** và tăng độ rộng, tách phần trộn-không-gian khỏi phần trộn-kênh.
4. **Nút cổ chai ngược (inverted bottleneck)** — mở rộng kênh gấp 4 rồi thu lại, đúng như khối MLP trong Transformer.
5. **Nhân tích chập lớn 7×7** — mở rộng vùng tiếp nhận để bắt chước tầm nhìn toàn cục của self-attention.
6. **Thiết kế vi mô** — thay ReLU bằng **GELU**, giảm số hàm kích hoạt và số lớp chuẩn hoá, thay **BatchNorm bằng LayerNorm**, tách riêng lớp hạ mẫu.

Kết quả: một mạng **thuần tích chập** đạt/vượt Swin Transformer cùng hạng. Vì vậy ConvNeXt là *ứng viên tự nhiên nhất* để đại diện cho "ResNet của thập niên 2020".

### 2.2. Vì Tiny là biến thể "cùng hạng" với ResNet-50 → so sánh công bằng

Đồ án so sánh 4 kiến trúc để xem **thiết kế** ảnh hưởng thế nào đến việc phát hiện mã độc bằng ảnh. Muốn công bằng thì phải so ở **cùng tầm chi phí**:

| Model | Tham số | FLOPs @224 | Vai trò trong đồ án |
| :---- | :----: | :----: | :---- |
| VGG16 | ~138 M | ~15,5 G | Kiến trúc cổ điển (2014), xếp lớp tuần tự |
| ResNet-50 | ~25,6 M | ~4,1 G | Bước ngoặt "kết nối tắt" (residual, 2015) |
| DenseNet-121 | ~8,0 M | ~2,9 G | Kết nối dày đặc (2017), tiết kiệm tham số |
| **ConvNeXt-Tiny** | **~28,6 M** | **~4,5 G** | **Thiết kế hiện đại (2022), thuần conv** |

ConvNeXt-Tiny (**28,6M / 4,5G**) nằm **đúng cùng hạng** với ResNet-50 (**25,6M / 4,1G**). Nhờ vậy, khi so hai model này, chênh lệch kết quả (nếu có) phản ánh **sự khác biệt về thiết kế kiến trúc**, chứ không phải do model to hơn ăn gian bằng nhiều tham số hơn. Đây chính là lý do phương pháp luận: ConvNeXt-Tiny là "phiên bản 2020s" của ResNet-50 ở cùng ngân sách tính toán.

### 2.3. Vì Tiny nhẹ, hợp với ràng buộc phần cứng và triển khai

Trong bốn model, ConvNeXt-Tiny đủ nhẹ để huấn luyện trên GPU của đồ án (RTX 4060 / Colab) và để **triển khai dashboard** sau này. Nó là lựa chọn đại diện "hiện đại" mà vẫn thực tế, không như VGG16 (138M tham số, quá nặng để deploy).

### 2.4. Tóm tắt lý do chọn

Chọn ConvNeXt-Tiny làm đại diện "ResNet hiện đại hoá" vì ba lẽ: (1) bản thân ConvNeXt được thiết kế **bằng cách hiện đại hoá trực tiếp ResNet-50**, nên nó là hiện thân đúng nghĩa của ý tưởng đó; (2) biến thể **Tiny cùng hạng tham số/FLOPs với ResNet-50**, cho phép so sánh công bằng để cô lập ảnh hưởng của thiết kế; và (3) nó **nhẹ, hiện đại, dễ triển khai**, phù hợp cả huấn luyện lẫn dashboard của đồ án.

---

## Nguồn tham khảo

- Zhuang Liu, Hanzi Mao, Chao-Yuan Wu, Christoph Feichtenhofer, Trevor Darrell, Saining Xie. *A ConvNet for the 2020s*. CVPR 2022. arXiv:2201.03545.
- Kaiming He và cộng sự. *Deep Residual Learning for Image Recognition* (ResNet). CVPR 2016.
- `torchvision.models.convnext_tiny` — tài liệu PyTorch.
