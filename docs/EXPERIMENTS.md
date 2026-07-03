# Thiết kế thí nghiệm — Kênh ảnh & Đa độ phân giải (cập nhật 2026-06-22)

Hai thí nghiệm có chủ đích, **đều là đóng góp chính (co-primary)** của DATN, chạy song song:
- **A — Ảnh 3-kênh composite** (gray + entropy-byte + tỉ lệ ASCII, đều từ chuỗi byte): biểu diễn đầu vào giàu thông tin hơn ảnh xám 1 kênh.
- **B — Hiệu quả độ phân giải** (224 vs 336 vs 448): chứng minh ảnh nhỏ 224² đạt độ chính xác tương đương/nhỉnh hơn ảnh lớn nhưng rẻ hơn nhiều.

Hai luận điểm độc lập nhau về mặt câu hỏi nghiên cứu nhưng dùng chung pipeline; có thể kết hợp (composite @224) ở cấu hình tốt nhất.

---

## Thí nghiệm A — Ảnh 3-kênh composite (gray + entropy-byte + ASCII) — ĐIỂM MỚI CHÍNH 1

### Giả thuyết
Thay vì nhân bản kênh xám (không thêm thông tin), ta tạo ảnh **3 kênh mang 3 góc nhìn khác nhau** của cùng file:
- **Kênh 1 — Grayscale:** bytes → pixel, **width cố định** (config, chốt sau EDA). Cấu trúc thô của file.
- **Kênh 2 — Entropy (từ chuỗi byte):** Shannon entropy của cửa sổ byte liên tiếp → làm nổi vùng packed/mã hóa/nén.
- **Kênh 3 — Tỉ lệ ASCII (từ chuỗi byte):** tỉ lệ byte in được (0x20–0x7E) trong cửa sổ byte → làm nổi vùng chuỗi/text/resource vs code/packed.

Giả thuyết: 3 kênh kỹ thuật này **thực sự bổ sung thông tin** → tăng accuracy so với chỉ dùng ảnh xám 1 kênh. Vì các kênh KHÔNG redundant, việc dùng 3 kênh + pretrained ImageNet (`in_chans=3`) là chính đáng (khác hẳn nhân bản).

> **Vì sao cả 3 kênh tính TỪ CHUỖI BYTE (không phải từ ảnh 2D):** entropy và tỉ lệ ASCII đều là tính chất của **các byte liên tiếp** trong file (vùng packed = byte liên tiếp entropy cao; chuỗi = byte liên tiếp in được). Tính trên cửa sổ byte 1D rồi trải về đúng vị trí byte → **đúng ngữ nghĩa** và **căn chỉnh pixel hoàn hảo** với kênh 1. (Cách 2D dùng cửa sổ trên ảnh trộn các byte cách nhau `width` → sai ngữ nghĩa "đoạn byte liên tiếp".)

### Cách tạo từng kênh (đã chốt)

**Kênh 1 — Grayscale (width cố định).** Như quy ước `bytes → ảnh xám` trong `CLAUDE.md`: một `image_width` duy nhất cho mọi mẫu (chốt sau EDA), height = ceil(len/width), pad 0 hàng cuối nếu lẻ. Width cố định cho texture đồng nhất giữa các mẫu (khác Nataraj).

**Kênh 2 — Entropy từ chuỗi byte** (cửa sổ 256 byte liên tiếp):
```python
import numpy as np
def byte_entropy(gray_uint8, window=256):
    b = gray_uint8.reshape(-1).astype(np.int64)          # chuỗi byte gốc
    n = b.size; nb = (n + window - 1)//window
    b = np.pad(b, (0, nb*window - n))
    bb = b.reshape(nb, window)
    off = np.arange(nb)[:, None]*256
    cnt = np.bincount((bb+off).ravel(), minlength=nb*256).reshape(nb, 256)
    p = cnt/window
    H = -(np.where(p>0, p*np.log2(p), 0)).sum(1)          # entropy mỗi khối (0–8 bit)
    e = np.repeat(H, window)[:n].reshape(gray_uint8.shape)
    return (e/e.max()*255).astype('uint8')
```
→ mỗi byte nhận entropy của khối 256 byte liền kề chứa nó; **căn chỉnh pixel** với kênh 1.

**Kênh 3 — Tỉ lệ ký tự in được (printable ASCII) từ chuỗi byte.**
```python
def ascii_ratio(gray_uint8, window=256):
    b = gray_uint8.reshape(-1)
    isp = ((b >= 0x20) & (b <= 0x7E)).astype(float)       # byte in được = 1
    n = b.size; nb = (n + window - 1)//window
    isp = np.pad(isp, (0, nb*window - n))
    ratio = isp.reshape(nb, window).mean(1)               # tỉ lệ mỗi khối ∈ [0,1]
    per = np.repeat(ratio, window)[:n]
    return (per.reshape(gray_uint8.shape)*255).astype('uint8')  # ×255 (tuyệt đối)
```
- Cùng cơ chế cửa sổ byte → **cùng H×W kênh 1**, căn chỉnh pixel.
- Vùng chuỗi/text (mật độ ASCII cao) sáng; code/packed (thấp) tối.
- Cơ sở: string là đặc trưng tĩnh mạnh (Wojnowicz 2016: string+entropy ~99% phát hiện, <1% FP). **Trực giao với entropy** (tính văn bản vs độ ngẫu nhiên).

### Lắp ghép & chuẩn hóa
- Tính cả 3 kênh ở **native resolution**, stack thành tensor `[gray, entropy, ascii]` shape `3×H×W`, rồi resize về `img_size` ở transform.
- **Chuẩn hóa per-channel bằng mean/std tính trên tập train** (KHÔNG dùng stat ImageNet RGB vì kênh ta không phải màu). Conv1 pretrained vẫn transfer tốt như bộ trích đặc trưng cấp thấp.
- Lưu ảnh dạng PNG 3 kênh (uint8) hoặc `.npy` float; PNG gọn và đủ.

### Thiết kế ablation (chứng minh từng kênh đóng góp)
Cùng model (ResNet50), cùng split/seed/epoch, chỉ đổi cấu hình kênh:

| Cấu hình | Đầu vào model | `in_chans` | Mục đích |
|----------|---------------|:---:|----------|
| **gray1** | `[gray]` (1 kênh) | **1** | baseline ảnh xám **thuần** — sửa conv đầu thành 1 kênh |
| gray×3 | `[gray, gray, gray]` | 3 | đối chứng: nhân bản gray KHÔNG thêm thông tin |
| +entropy | `[gray, entropy, gray]` | 3 | đo đóng góp riêng entropy |
| +ascii | `[gray, gray, ascii]` | 3 | đo đóng góp riêng ASCII |
| **full (đề xuất)** | `[gray, entropy, ascii]` | 3 | composite đầy đủ |

- **gray1** (1 kênh thật) khác **gray×3** (nhân bản): gray1 sửa lớp conv đầu (`in_chans=1`, khởi tạo = tổng 3 kênh pretrained); gray×3 giữ model 3 kênh, lặp gray. Cả hai đo "baseline không có kênh kỹ thuật", nhưng gray1 gọn hơn (ít tham số conv1).
- **Đo:** accuracy/F1 + bộ nhớ + thời gian/epoch + số tham số.
- **Kỳ vọng:** `full > (+entropy, +ascii) > gray1 ≈ gray×3` → chứng minh kênh entropy/ASCII thêm thông tin thật, còn nhân bản thì không.
- **Cấu hình:** `configs/ablation_resnet50_gray1.yaml` (gray1) + đổi `channels`/`run_name` cho 4 cấu hình còn lại.

### Cách trình bày
Bảng ablation + biểu đồ accuracy theo cấu hình kênh → kết luận: kênh entropy/ASCII có giá trị, biện minh việc dùng 3 kênh. Đây là **đóng góp học thuật chính** của đồ án.

---

## Thí nghiệm B — Hiệu quả độ phân giải: 224 vs 336 vs 448 — ĐIỂM MỚI CHÍNH 2

### Giả thuyết trung tâm (H1)
**Huấn luyện ở 224² cho độ chính xác xấp xỉ (chênh lệch nằm trong nhiễu) hoặc nhỉnh hơn so với 336²/448², trong khi chi phí tính toán thấp hơn nhiều lần.**
→ Kết luận thực tiễn: với bài toán phát hiện/phân loại mã độc bằng ảnh, **không cần ảnh độ phân giải cao** — 224² là điểm cân bằng tối ưu.

Cơ sở để kỳ vọng H1 đúng:
1. **Chữ ký họ mã độc mang tính texture lặp lại, toàn cục** — không nằm ở chi tiết pixel mịn; nhiều công trình đạt >98% ngay ở 64²/32².
2. **Model pretrained ImageNet được tối ưu ở 224²**; đẩy lên 336/448 làm lệch khỏi phân phối pretrain → lợi ích độ phân giải bị triệt tiêu, đôi khi *giảm* nhẹ nếu không fine-tune kỹ → giải thích vì sao 224 có thể nhỉnh hơn.

### TRÁNH bẫy "trivial" — phải dùng ảnh native đủ lớn
Đây là điểm mấu chốt để kết luận đứng vững:
- Phóng to ảnh nhỏ lên 448 chỉ là **upscale nội suy** → 448 không thể hơn 224 là điều *gần như hiển nhiên*, phản biện sẽ bác "đương nhiên vì phóng to ảnh rỗng".
- → Bằng chứng phải đến từ **ảnh native LỚN thật**: bộ phát hiện PE thô (file thường vài trăm KB–vài MB → ảnh native cao hàng nghìn px ở width cố định). Chứng minh **thu nhỏ ảnh to thật xuống 224 vẫn giữ đủ thông tin phân biệt** → 224 ≈ 448 dù 448 là độ phân giải *thật*. Trong EDA (S1.4) phải xác nhận **chiều cao đa số mẫu ≥ 448** trước khi chạy sweep.

### Tập dữ liệu cho sweep — HAI thí nghiệm TÁCH BIỆT (đọc kỹ)
Đây là điểm dễ nhầm. Dự án có **hai thí nghiệm dùng số mẫu khác nhau**, KHÔNG đặt cạnh nhau:

| Thí nghiệm | Tập mẫu | Độ phân giải | Mục đích |
|-----------|---------|--------------|----------|
| **Phát hiện (chính)** | **TOÀN BỘ** valid_detect (~14,547) | chỉ **224** | kết quả phát hiện benign/malware |
| **Resolution sweep (B)** | chỉ **`res_eligible`** (native ≥448², ~7,806) | **224 & 336 & 448** | so sánh độ phân giải |

- **Sweep phải dùng CÙNG một tập mẫu** (7,806 res_eligible) ở cả 224/336/448 → mới so sánh công bằng. **KHÔNG** so 14,547@224 với 7,806@336 (đó là hai thí nghiệm khác nhau).
- Ảnh 224 của 7,806 mẫu này **đã có sẵn** (là tập con của 14,547) → không sinh lại; chỉ **lọc `res_eligible`** rồi lấy ảnh ở `data/processed/{224,336,448}/`.
- Vì sao 336/448 chỉ ~7,806: mẫu native < 448² nếu phóng lên 448 là **nội suy = thông tin giả** (xem mục trên) → loại khỏi sweep.
- Thực hiện: một **split res_eligible cố định** (train/val/test), train 3 lần đổi thư mục ảnh theo độ phân giải, giữ nguyên danh sách mẫu.

### Yêu cầu chặt chẽ về thống kê (BẮT BUỘC để nói "tương đương")
"Xấp xỉ" là một phát biểu thống kê, không phải so 1 con số:
- **Mỗi cấu hình (model × img_size × dataset) chạy ≥ 3 seed** khác nhau; báo cáo **mean ± std**.
- **Kiểm định ý nghĩa thống kê** chênh lệch giữa các độ phân giải: paired t-test (trên seed) hoặc McNemar (trên dự đoán test) → kết luận "khác biệt không có ý nghĩa" hay "224 cao hơn có ý nghĩa".
- Chỉ được nói "224 nhỉnh hơn" khi chênh lệch **vượt** dao động seed; nếu không, kết luận đúng là "tương đương trong nhiễu".
- **Công bằng tuyệt đối:** cùng model/split/seed-set/augment/epoch/normalize, **chỉ đổi `img_size`**.
- **Không model-specific:** chạy ≥ 2 kiến trúc (ResNet50 + ConvNeXt-Tiny) để loại trừ may rủi.

### Điểm bán hàng cốt lõi: ACCURACY-VS-COST
Luận điểm mạnh nhất không phải "224 chính xác hơn" mà là **"224 không kém nhưng rẻ hơn nhiều"**. Bảng kết quả BẮT BUỘC có cột chi phí cạnh accuracy:

| img_size | Accuracy/F1 (mean±std) | Thời gian/epoch | GPU mem đỉnh | FLOPs (GMACs) |
|----------|------------------------|-----------------|--------------|---------------|
| 224² | … | 1× (mốc) | 1× | 1× |
| 336² | … | ~2.25× | ~2.25× | ~2.25× |
| 448² | … | ~4× | ~4× | ~4× |

→ Kết luận: *"tăng độ phân giải không cải thiện độ chính xác một cách có ý nghĩa nhưng tốn gấp ~2–4× tài nguyên → 224² tối ưu cho triển khai thực tế"*. Kết luận này hợp ngành ATTT (máy yếu, quét hàng loạt) và **không thể bị bác**.

### Cơ sở kỹ thuật theo kiến trúc
- **CNN (VGG/ResNet/DenseNet/ConvNeXt):** xử lý được độ phân giải tùy ý nhờ adaptive pooling trước lớp FC → chỉ cần đổi `img_size` trong transform. Không cần sửa model.
- **ViT/Swin:** đổi độ phân giải làm thay đổi số patch → **phải nội suy 2D positional embedding**. Trong timm: truyền `img_size=` khi `create_model` (timm tự nội suy pos-embed của pretrained), hoặc dùng `dynamic_img_size=True`. Phải kiểm tra forward chạy đúng ở 336/448.

### CAVEAT QUAN TRỌNG — độ phân giải nguồn (đã chốt sau EDA 2026-06-28)
- Phóng to ảnh nhỏ lên 448 chỉ là **nội suy**, KHÔNG thêm thông tin thật → thông tin giả.
- **`image_width = 448`** (= độ phân giải lớn nhất). Nhờ vậy: native width = 448 → resize về **224/336 là thu nhỏ THẬT**, về **448 không resample** → KHÔNG có thông tin giả ở chiều rộng tại bất kỳ mức nào.
- **Resolution sweep CHỈ chạy trên mẫu native ≥ 448×448** (cờ `res_eligible=1` trong `valid_for_train.csv`, tức size ≥ 200,704 B ≈ 196 KB). Khi đó cả hai chiều ≥ 448 → 224/336/448 đều là downsample thật. Theo EDA, ~52% mẫu đủ điều kiện (median file 206 KB).
- File quá nhỏ (< 4 KB) bị loại; file khổng lồ (> 30 MB) chỉ đọc 30 MB đầu (`min_bytes`/`max_bytes` trong `configs/data.yaml`).
- Bài toán **phát hiện** (224) vẫn dùng toàn bộ mẫu hợp lệ; chỉ riêng **sweep độ phân giải** lọc theo `res_eligible`.

### Chi phí trên Colab (lưu ý GPU)
- Bộ nhớ/FLOPs tăng ~ bậc hai theo cạnh ảnh: 336² ≈ 2.25×, 448² ≈ 4× so với 224².
- → **Giảm batch size** khi tăng độ phân giải (vd 64 @224 → 32 @336 → 16 @448 trên T4 16GB); bật AMP; có thể dùng gradient accumulation để giữ batch hiệu dụng.

### Thiết kế
- `img_size` là tham số config; mỗi (model × img_size × seed) là 1 run, đặt tên `{dataset}_{model}_{size}_s{seed}_{ngày}`.
- Sweep trên 2 model đại diện (ResNet50 + ConvNeXt-Tiny) × {224,336,448} × ≥3 seed, trên **bộ phát hiện PE thô**.
- **Đo cho mỗi run:** accuracy/F1 macro, thời gian/epoch, bộ nhớ GPU đỉnh, FLOPs (GMACs, tính bằng `thop`/`fvcore`).

### Cách trình bày
- Bảng accuracy/F1 **(mean±std)** theo độ phân giải, kèm cột chi phí (thời gian, GPU mem, FLOPs).
- **Biểu đồ accuracy-vs-resolution có error bar**; biểu đồ accuracy-vs-cost (Pareto) làm nổi điểm 224².
- Ghi rõ **kết quả kiểm định thống kê** (p-value) cho từng cặp so sánh.
- Câu kết luận mẫu: *"trên bộ phát hiện PE thô (ảnh native lớn), 224² đạt F1 = X.XX±0.0Y, không khác biệt có ý nghĩa so với 448² (p > 0.05) nhưng rẻ hơn ~4× → 224² là lựa chọn tối ưu"*.

---

## Ma trận thí nghiệm gợi ý (tránh bùng nổ số run)

| Trục | Giá trị | Phạm vi chạy |
|------|---------|--------------|
| Kiến trúc | VGG16, ResNet50, DenseNet121, ConvNeXt-Tiny, (ViT) | Đủ bộ ở 224², 3 kênh |
| Cấu hình kênh | gray / +entropy / +ascii / full / gray×3 | Chỉ ablation trên ResNet50 @224² |
| Độ phân giải | 224, 336, 448 | Chỉ trên ResNet50 + ConvNeXt-Tiny (3 kênh) |
| Bài toán | Phát hiện nhị phân (chính) · Phân loại họ (phụ) | Bộ phát hiện PE thô |

> Nguyên tắc: cố định mọi yếu tố khác khi quét 1 trục (so sánh công bằng), và **không** chạy tích Descartes đầy đủ để tiết kiệm GPU Colab.

## Nguồn
- [Tri-channel visualised malicious code classification (ResNet cải tiến) — Applied Intelligence 2024](https://link.springer.com/article/10.1007/s10489-024-05707-4)
- [A New Framework for Visual Classification of Multi-Channel Malware — Applied Sciences 2023](https://doi.org/10.3390/app13042484)
- [Using Entropy Analysis to Find Encrypted and Packed Malware](https://www.researchgate.net/publication/3437909_Using_Entropy_Analysis_to_Find_Encrypted_and_Packed_Malware)
- [String + entropy features (Wojnowicz 2016 — Wavelet decomposition of software entropy)](https://arxiv.org/pdf/1607.04950)
- [Signal-Based Malware Classification (byte là tín hiệu 1D)](https://arxiv.org/html/2509.06548v1)
- [ViT — nội suy 2D positional embedding khi đổi độ phân giải (HF docs)](https://huggingface.co/docs/transformers/en/model_doc/vit)
- [An Image is Worth 16x16 Words (ViT) — fine-tune ở độ phân giải cao](https://arxiv.org/pdf/2010.11929)
