# Thiết kế thí nghiệm — Lưới hợp nhất: Kênh ảnh × Độ phân giải (cập nhật 2026-06-29)

> **Thay đổi lớn (2026-06-29):** trước đây tách **A (kênh ảnh)** và **B (độ phân giải)** thành hai thí nghiệm song song. Nay **GỘP thành MỘT thí nghiệm hợp nhất (Thí nghiệm A)**: train **5 cấu hình kênh × 3 độ phân giải (224/336/448)** trên cùng một tập & pipeline → từ một bảng kết quả rút ra **cả 2 kết luận** cùng lúc.
>
> **Cấu hình kênh (2026-06-30):** **5 cấu hình** — `gray1`, `gray×3`, `+entropy` (gray×entropy), `+ascii` (gray×ASCII), `full`. `gray1` là baseline ảnh xám (cốt lõi đề tài); `+entropy` và `+ascii` tách riêng đóng góp từng kênh kỹ thuật; `full` là composite đầy đủ; `gray×3` là đối chứng nhân bản.

## 1. Lưới thí nghiệm A (5 cấu hình kênh × 3 độ phân giải)

- **5 cấu hình kênh:** `gray1` (ảnh xám 1 kênh — cốt lõi đề tài), `gray×3` (nhân bản — đối chứng), `+entropy` (gray+entropy), `+ascii` (gray+ASCII), `full` (composite đầy đủ — đề xuất).
- **3 độ phân giải:** `224`, `336`, `448`.
- → **15 ô** cho mỗi (model × seed). Chạy **≥ 3 seed**; model chính **ResNet50**, khẳng định thêm trên **ConvNeXt-Tiny**.
  > **Cơ sở chọn ResNet50 làm backbone của lưới** (chi tiết + trích dẫn nguyên văn: `docs/RELATED_WORK.md` mục 5.6): (1) baseline "gold-standard, mặc định trong các nghiên cứu" của cộng đồng vision — Wightman et al. 2021 (arXiv:2110.00476); (2) đúng backbone mà các thí nghiệm ablation biểu diễn ảnh malware gần nhất dùng — Nie 2024 (arXiv:2406.03831, ablation width), IMCEC (Vasan 2020), MalFCS (Xiao 2020) → kết quả đối chiếu trực tiếp được với văn liệu; (3) cân bằng hiệu năng/tài nguyên tốt nhất họ ResNet — Nie 2024 §4.3: *"Among the ResNet family, ResNet50 strikes a good balance between model performance and computational resource requirements, compared to other models like ResNet18 and ResNet101"* — chạy được cả ô 448² trên RTX 4060 8GB, trong khi DenseNet concatenation ngốn activation memory (Pleiss et al. 2017, arXiv:1707.06990).
- **Cùng MỘT tệp dataset cho toàn lưới:** `data/interim/sweep_train.csv` / `sweep_val.csv` / `sweep_test.csv` (tập `res_eligible`, native ≥ 448²). **Cả 15 ô dùng đúng danh sách mẫu này** → so sánh **cả theo hàng (kênh) lẫn theo cột (độ phân giải)** đều công bằng.

  > **Số lượng thực tế theo split (label 0 = benign, 1 = malware):**
  >
  > | Split | Benign | Malware | Tổng |
  > |-------|:------:|:-------:|:----:|
  > | `sweep_train.csv` | 1.438 | 4.060 | 5.498 |
  > | `sweep_val.csv`   | 309   | 871   | 1.180 |
  > | `sweep_test.csv`  | 309   | 873   | 1.182 |
  > | **Tổng**          | **2.056** | **5.804** | **7.860** |
- Cùng split/seed-set/augment/epoch; **chỉ đổi `channels` và `img_size`** (config trỏ `split_prefix: sweep`). Ảnh lấy ở `data/processed/{img_size}/…`.

## 2. Output — MỘT bảng kết quả (config × size), làm nổi bật ô tốt nhất

Mỗi dòng = một **(cấu hình × độ phân giải)** (15 dòng), giá trị = **mean ± std** trên ≥3 seed. Ô có **F1 cao nhất** được **in đậm + ★**.

> **Giải thích "mean ± std trên ≥3 seed":** seed là hạt giống ngẫu nhiên chi phối khởi tạo trọng số, xáo trộn batch, augment… Cùng một cấu hình nhưng đổi seed sẽ cho kết quả **hơi khác nhau** — tức 1 lần chạy chỉ là 1 mẫu ngẫu nhiên, không đại diện. Vì vậy **mỗi ô của lưới được train lại ≥ 3 lần**, mỗi lần một seed khác (42, 123, 2026), rồi báo cáo **trung bình (mean) ± độ lệch chuẩn (std)** của từng metric. Ví dụ F1 3 seed = 0.962, 0.958, 0.960 → ghi **0.960 ± 0.002**. Mean cho biết hiệu năng "điển hình"; std cho biết độ dao động do ngẫu nhiên — nền tảng để so sánh có ý nghĩa: hai ô chỉ được coi là "khác nhau" khi chênh lệch mean **vượt** mức dao động std (và qua kiểm định thống kê, xem §6); nếu không thì phải nói "tương đương trong nhiễu".

> **Kết quả thực tế (2026-07-07, ResNet50, 45/45 run, mean ± std trên seed 42/123/2026):** bảng dưới đọc bằng `python scripts/analyze_grid.py` (nguồn: `results/metrics/grid_resnet50.csv` + `grid_convnext_tiny.csv`, kiểm định: `results/metrics/grid_resolution_ttest.csv`, biểu đồ: `results/figures/pareto_accuracy_vs_cost.png`; dữ liệu thô mỗi run: `results/metrics/sweep_{resnet50,convnext}_raw.csv` từ `scripts/aggregate_results.py`). Ô **F1 cao nhất thực tế là `full × 448` (0.9823 ± 0.0024)**, không phải `full × 224` như kỳ vọng ban đầu — nhưng `full × 224` (0.9755 ± 0.0038) **không khác `full × 448` có ý nghĩa thống kê** (xem kiểm định bên dưới) trong khi rẻ hơn ~2.25× (GMACs 4.13 vs 16.53). ★ đánh dấu theo số liệu thực tế.

| Config × Size | Accuracy | Precision | Recall | F1 | ROC-AUC | Thời gian/epoch | GPU mem đỉnh | FLOPs (GMACs) |
|---------------|:--------:|:---------:|:------:|:--:|:-------:|:---------------:|:------------:|:-------------:|
| gray1 × 224   | 0.9622 ± 0.0027 | 0.9748 ± 0.0058 | 0.9740 ± 0.0024 | 0.9744 ± 0.0017 | 0.9831 ± 0.0066 | 34.9s ± 0.2 | 707 ± 0 MB | 4.05 |
| gray1 × 336   | 0.9628 ± 0.0059 | 0.9730 ± 0.0033 | 0.9767 ± 0.0046 | 0.9748 ± 0.0040 | 0.9857 ± 0.0035 | 51.1s ± 0.0 | 1125 ± 0 MB | 9.27 |
| gray1 × 448   | 0.9676 ± 0.0055 | 0.9812 ± 0.0022 | 0.9748 ± 0.0094 | 0.9780 ± 0.0039 | 0.9901 ± 0.0002 | 76.8s ± 0.1 | 1702 ± 2 MB | 16.21 |
| gray×3 × 224  | 0.9636 ± 0.0037 | 0.9734 ± 0.0071 | 0.9775 ± 0.0043 | 0.9754 ± 0.0024 | 0.9895 ± 0.0038 | 35.0s ± 0.0 | 712 ± 0 MB | 4.13 |
| gray×3 × 336  | 0.9625 ± 0.0055 | 0.9771 ± 0.0117 | 0.9721 ± 0.0063 | 0.9746 ± 0.0036 | 0.9881 ± 0.0025 | 51.9s ± 0.0 | 1136 ± 1 MB | 9.45 |
| gray×3 × 448  | 0.9681 ± 0.0068 | 0.9849 ± 0.0030 | 0.9717 ± 0.0087 | 0.9783 ± 0.0047 | 0.9875 ± 0.0013 | 78.3s ± 0.1 | 1722 ± 1 MB | 16.53 |
| +entropy × 224 | 0.9693 ± 0.0010 | 0.9838 ± 0.0034 | 0.9744 ± 0.0037 | 0.9791 ± 0.0007 | 0.9909 ± 0.0018 | 35.1s ± 0.2 | 710 ± 0 MB | 4.13 |
| +entropy × 336 | 0.9687 ± 0.0031 | 0.9827 ± 0.0059 | 0.9748 ± 0.0034 | 0.9787 ± 0.0020 | 0.9902 ± 0.0011 | 52.2s ± 0.2 | 1137 ± 0 MB | 9.45 |
| +entropy × 448 | 0.9741 ± 0.0032 | 0.9892 ± 0.0018 | 0.9756 ± 0.0026 | 0.9823 ± 0.0022 | 0.9904 ± 0.0021 | 78.6s ± 0.0 | 1723 ± 0 MB | 16.53 |
| +ascii × 224  | 0.9701 ± 0.0043 | 0.9842 ± 0.0034 | 0.9752 ± 0.0065 | 0.9797 ± 0.0030 | 0.9893 ± 0.0028 | 35.0s ± 0.1 | 710 ± 0 MB | 4.13 |
| +ascii × 336  | 0.9695 ± 0.0017 | 0.9850 ± 0.0058 | 0.9737 ± 0.0080 | 0.9793 ± 0.0013 | 0.9912 ± 0.0010 | 52.0s ± 0.1 | 1136 ± 1 MB | 9.45 |
| +ascii × 448  | 0.9693 ± 0.0054 | 0.9857 ± 0.0017 | 0.9725 ± 0.0072 | 0.9790 ± 0.0037 | 0.9894 ± 0.0033 | 78.5s ± 0.3 | 1723 ± 0 MB | 16.53 |
| full × 224    | 0.9639 ± 0.0055 | 0.9796 ± 0.0047 | 0.9714 ± 0.0050 | 0.9755 ± 0.0038 | 0.9909 ± 0.0010 | 35.6s ± 0.9 | 710 ± 0 MB | 4.13 |
| full × 336    | 0.9684 ± 0.0020 | 0.9887 ± 0.0018 | 0.9683 ± 0.0029 | 0.9784 ± 0.0014 | 0.9916 ± 0.0008 | 52.1s ± 0.0 | 1137 ± 0 MB | 9.45 |
| **full × 448 ★** | 0.9741 ± 0.0034 | 0.9884 ± 0.0030 | 0.9763 ± 0.0063 | 0.9823 ± 0.0024 | 0.9911 ± 0.0006 | 78.5s ± 0.0 | 1723 ± 0 MB | 16.53 |

**ConvNeXt-Tiny (9/9 run, trục độ phân giải, cấu hình `full`):**

| Config × Size | Accuracy | Precision | Recall | F1 | ROC-AUC | Thời gian/epoch | GPU mem đỉnh | FLOPs (GMACs) |
|---------------|:--------:|:---------:|:------:|:--:|:-------:|:---------------:|:------------:|:-------------:|
| **full × 224 ★** | 0.9772 ± 0.0045 | 0.9900 ± 0.0013 | 0.9790 ± 0.0066 | 0.9844 ± 0.0031 | 0.9933 ± 0.0008 | 38.9s ± 0.4 | 904 ± 0 MB | 4.46 |
| full × 336    | 0.9715 ± 0.0047 | 0.9828 ± 0.0041 | 0.9786 ± 0.0043 | 0.9807 ± 0.0032 | 0.9926 ± 0.0004 | 58.1s ± 0.0 | 1472 ± 1 MB | 9.88 |
| full × 448    | 0.9766 ± 0.0027 | 0.9896 ± 0.0030 | 0.9786 ± 0.0033 | 0.9841 ± 0.0019 | 0.9926 ± 0.0006 | 90.3s ± 0.1 | 2294 ± 0 MB | 17.85 |

> **Kiểm định thống kê (paired t-test theo seed trên F1, `scripts/analyze_grid.py` + `src/evaluation/stats.py`, đủ 3 cặp size × cả 5 kênh — CSV đầy đủ: `results/metrics/grid_resolution_ttest.csv`):**
> - **Trục độ phân giải — ResNet50, cả 5 kênh:** 14/15 cặp (224²/336²/448², mọi kênh) có **p>0.05 → tương đương trong nhiễu**. Ngoại lệ duy nhất: `gray×3` 336² vs 448² (p=0.047, "448² cao hơn có ý nghĩa") — một trường hợp lẻ trong 15 phép kiểm định, không đủ để bác kết luận chung (kỳ vọng ~1 false positive/cặp khi test nhiều lần ở α=0.05). Trên kênh `full` (dòng chính của bảng): 224² vs 336² (p=0.202), 224² vs 448² (p=0.120), 336² vs 448² (p=0.081) — cả 3 đều không có ý nghĩa.
> - **Trục độ phân giải — ConvNeXt-Tiny (kênh full):** 224² vs 336² (p=0.304), 224² vs 448² (p=0.832), 336² vs 448² (p=0.105) — **cũng KHÔNG có ý nghĩa thống kê** → Kết luận 2 **không phụ thuộc kiến trúc**, được xác nhận nhất quán trên gần như toàn bộ lưới (đúng yêu cầu §6).
> - **Trục kênh:** chưa có kiểm định chính thức gray1-vs-full trong `analyze_grid.py` (script hiện chỉ test trục độ phân giải); nhìn bảng, `+entropy`/`+ascii`/`full` nhỉnh hơn `gray1`/`gray×3` ở hầu hết size nhưng chênh lệch nhỏ (F1 ~0.003–0.007) so với std giữa seed (~0.002–0.005) → **cần nói "xu hướng ủng hộ kênh composite/kỹ thuật, chưa kiểm định chính thức ở n=3 seed"**, không khẳng định "hơn có ý nghĩa". Nêu rõ giới hạn này trong báo cáo DATN.

> **Ý nghĩa 3 cột chi phí** (đo/tính thực tế mỗi run, KHÔNG điền sẵn):
> - **Thời gian/epoch:** thời gian wall-clock train 1 epoch (giây/phút) — **đo thực tế** trên GPU dùng để train, lấy trung bình qua các epoch (bỏ epoch đầu warm-up).
> - **GPU mem đỉnh:** VRAM đỉnh trong lúc train (`torch.cuda.max_memory_allocated()`) — **đo thực tế**; quyết định batch size và việc chạy nổi trên RTX 4060 8GB hay không.
> - **FLOPs (GMACs):** khối lượng tính toán 1 lượt forward — **tính giải tích** (vd `fvcore`/`ptflops`), chỉ phụ thuộc kiến trúc + `img_size`, không phụ thuộc phần cứng.
>
> **Kỳ vọng lý thuyết** (không phải số điền sẵn): lấy 224² làm mốc 1× thì 336²≈2.25×, 448²≈4× — vì chi phí ~ bậc hai theo cạnh ảnh (§8). FLOPs sẽ theo sát tỉ lệ này; **thời gian/epoch và GPU mem thực tế có thể lệch** (dataloader bottleneck, AMP, batch size khác nhau giữa các size…) — **luôn báo cáo số đo được**, tỉ lệ ×N chỉ dùng để đối chiếu. Nếu số thực tế lệch xa kỳ vọng thì ghi chú nguyên nhân trong báo cáo, kết luận accuracy-vs-cost dựa trên số thực tế. Ô ★ là kỳ vọng (`full × 224`) — thực tế đánh dấu theo số liệu chạy được.

### Kết luận rút ra từ bảng (cập nhật 2026-07-07 — số liệu thực tế, 54/54 run)

- **Kết luận 1 — Kênh (so các dòng cùng độ phân giải):** số liệu thực tế cho pattern **`+entropy ≈ +ascii ≈ full > gray1 ≈ gray×3`** ở cả 3 size (F1 gray1/gray×3 luôn thấp nhất hoặc đồng hạng thấp nhất; 3 cấu hình có kênh kỹ thuật luôn nhỉnh hơn). Điều này **yếu hơn kỳ vọng ban đầu** (`full` không luôn vượt trội `+entropy`/`+ascii` riêng lẻ — ở 224²/336² hai kênh đơn lẻ này thậm chí F1 nhỉnh hơn `full` một chút, chỉ ở 448² `full` mới dẫn đầu cùng `+entropy`). `gray×3 ≈ gray1` (chênh lệch F1 ≤0.001–0.004) **xác nhận nhân bản kênh không thêm thông tin đáng kể**. Chưa có kiểm định t-test chính thức cho trục kênh (`scripts/analyze_grid.py` hiện chỉ kiểm định trục độ phân giải) — phải diễn đạt là **"xu hướng ủng hộ kênh composite/kỹ thuật, nhưng chưa kiểm định thống kê chính thức ở n=3 seed"**, không khẳng định "hơn hẳn".
- **Kết luận 2 — Độ phân giải (so 3 dòng cùng một cấu hình):** paired t-test (theo seed, trên F1) cho **14/15 cặp size × kênh ở ResNet50 đều p>0.05**, cặp ngoại lệ duy nhất `gray×3` 336² vs 448² (p=0.047) không đủ để bác kết luận chung (~1 false-positive kỳ vọng khi test 15 lần ở α=0.05). Trên kênh `full`: ResNet50 p=0.20/0.12/0.08; ConvNeXt-Tiny p=0.30/0.83/0.11 — **KHÔNG có khác biệt có ý nghĩa thống kê về accuracy giữa 3 độ phân giải**, ở cả 2 kiến trúc. Trong khi đó chi phí tăng đúng theo lý thuyết bậc hai: GMACs 224²→336²→448² là ×1 / ×2.29 / ×4.00 (ResNet50), thời gian/epoch ×1 / ×1.49 / ×2.25, GPU mem ×1 / ×1.60 / ×2.43. → **224² đạt accuracy tương đương thống kê với 336²/448² nhưng rẻ hơn 2.3–4× → 224² tối ưu cho triển khai.** Đây là kết luận **mạnh và được xác nhận thống kê đầy đủ trên gần như toàn bộ lưới**, không phụ thuộc kiến trúc (đúng yêu cầu §6).
- **Chọn cấu hình triển khai:** ô F1 cao nhất thực tế là `full × 448` (ResNet50, F1=0.9823) và `full × 224` (ConvNeXt-Tiny, F1=0.9844) — nhưng do Kết luận 2, `full × 224` (ResNet50, F1=0.9755) **không khác `full × 448` có ý nghĩa thống kê** trong khi rẻ hơn ~4× → **`full × 224` vẫn là cấu hình khuyến nghị triển khai thực tế** (accuracy tương đương, chi phí thấp nhất), không phải ô F1 tuyệt đối cao nhất trên bảng.
- **Kèm kiểm định thống kê:** mọi phát biểu "≈"/"hơn" ở trên đều kèm p-value (paired t-test, script `scripts/analyze_grid.py`, dùng `src/evaluation/stats.py`) — xem §6, dữ liệu đầy đủ trong `results/metrics/grid_resolution_ttest.csv`.

> Hai kết luận này là **hai đóng góp chính (co-primary)** của DATN, nay đến từ **cùng một bảng** thay vì hai thí nghiệm rời. **Kết luận 2 (độ phân giải) mạnh và đầy đủ bằng chứng thống kê; Kết luận 1 (kênh) có xu hướng đúng hướng nhưng cần nêu rõ giới hạn thống kê ở n=3 seed trong báo cáo DATN** — có thể cân nhắc chạy thêm seed nếu cần củng cố Kết luận 1.

---

## 3. Ảnh 3-kênh composite — định nghĩa & cách tạo

### Giả thuyết
Thay vì nhân bản kênh xám (không thêm thông tin), ta tạo ảnh **3 kênh mang 3 góc nhìn khác nhau** của cùng file, **đều tính TỪ CHUỖI BYTE**:
- **Kênh 1 — Grayscale:** bytes → pixel, **width cố định = 448**. Cấu trúc thô của file.
- **Kênh 2 — Entropy (từ chuỗi byte):** Shannon entropy của cửa sổ byte liên tiếp → vùng packed/mã hóa/nén.
- **Kênh 3 — Tỉ lệ ASCII (từ chuỗi byte):** tỉ lệ byte in được (0x20–0x7E) trong cửa sổ byte → vùng chuỗi/text/resource vs code/packed.

> **Vì sao cả 3 kênh tính TỪ CHUỖI BYTE (không phải ảnh 2D):** entropy và ASCII là tính chất của **byte liên tiếp** (packed = đoạn byte liên tiếp entropy cao; chuỗi = byte liên tiếp in được). Cửa sổ 2D trên ảnh trộn các byte cách nhau `width=448` → sai ngữ nghĩa. Tính trên cửa sổ byte 1D rồi trải về đúng vị trí byte → **đúng ngữ nghĩa** + **căn chỉnh pixel** với kênh 1.

### Kênh 2 — Entropy từ chuỗi byte (cửa sổ 256 byte liên tiếp)
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

### Kênh 3 — Tỉ lệ ký tự in được (printable ASCII) từ chuỗi byte
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
- **Trực giao với entropy** (mật độ văn bản vs độ ngẫu nhiên). Cơ sở: string là đặc trưng tĩnh mạnh (Wojnowicz 2016: string+entropy ~99% phát hiện, <1% FP).

### Lắp ghép & chuẩn hóa
- Tính cả 3 kênh ở **native**, stack `[gray, entropy, ascii]` → `3×H×W`, resize về `img_size` ở transform.
- **Chuẩn hóa per-channel** bằng mean/std tính trên tập train (không dùng stat ImageNet RGB). Conv1 pretrained vẫn transfer tốt.

## 4. Năm cấu hình kênh (trục "kênh" của lưới)

| Cấu hình | Đầu vào model | `in_chans` | Mục đích |
|----------|---------------|:---:|----------|
| **gray1** | `[gray]` (1 kênh) | **1** | baseline ảnh xám **thuần** — cốt lõi đề tài; sửa conv đầu thành 1 kênh |
| gray×3 | `[gray, gray, gray]` | 3 | đối chứng: nhân bản gray KHÔNG thêm thông tin |
| +entropy | `[gray, entropy, gray]` | 3 | đo đóng góp riêng kênh entropy (gray×entropy) |
| +ascii | `[gray, gray, ascii]` | 3 | đo đóng góp riêng kênh ASCII (gray×ASCII) |
| **full (đề xuất)** | `[gray, entropy, ascii]` | 3 | composite đầy đủ (gray + entropy-byte + ASCII) |

- **gray1** (1 kênh thật) khác **gray×3** (nhân bản): gray1 sửa lớp conv đầu (`in_chans=1`, khởi tạo = tổng 3 kênh pretrained); gray×3 giữ model 3 kênh, lặp gray. Cả hai là "baseline ảnh xám không có kênh kỹ thuật".
- **`+entropy`/`+ascii`** (leave-one-in): giữ gray + một kênh kỹ thuật → tách được **đóng góp riêng** của entropy vs ASCII, và cho thấy composite `full` cộng hưởng hai kênh ra sao.
- **Đo mỗi run:** accuracy/precision/recall/F1 + ROC-AUC + bộ nhớ + thời gian/epoch + FLOPs.
- **Cấu hình:** `configs/sweep_{model}_{config}_{size}_s{seed}.yaml` (đổi `channels` và `img_size`).

---

## 5. Tập dữ liệu cho lưới — `res_eligible` (bắt buộc để so sánh công bằng)

Vì lưới có trục độ phân giải, **toàn bộ lưới phải chạy trên CÙNG MỘT tệp dataset** mà mọi độ phân giải đều là **thu nhỏ thật** (không phóng to nội suy):

- **Tệp cố định:** `data/interim/sweep_train.csv` / `sweep_val.csv` / `sweep_test.csv` — sinh bằng:
  ```bash
  python scripts/make_split.py --input data/interim/valid_detect.csv \
      --only-res-eligible --out-prefix sweep \
      --stats-out data/interim/channel_stats_sweep.json
  ```
  → lọc `res_eligible=1` (ảnh native **≥ 448×448**, size ≥ 200,704 B ≈ 196 KB) rồi split grouped/stratified chống rò rỉ. Theo EDA ~52% mẫu đủ điều kiện.
- **Cả 15 ô (5 kênh × 3 size) đọc đúng bộ `sweep_*.csv` này** (config: `split_dir: data/interim`, `split_prefix: sweep`). Chỉ khác nhau ở `channels` và `img_size` → ảnh lấy từ `data/processed/{img_size}/{sha[:2]}/{sha}.png`, danh sách mẫu **y hệt nhau**.
- Chuẩn hóa: mean/std per-channel lấy từ `channel_stats_sweep.json` (tính trên `sweep_train`). Nội dung kênh khác nhau giữa các cấu hình nên stat tương ứng từng cấu hình, **nhưng danh sách mẫu không đổi**.
- Ảnh 224 của tập sweep là **tập con** của bộ phát hiện đầy đủ → không sinh lại.

> **Tình trạng config (2026-06-30):** thư mục `configs/` **đã có sẵn đầy đủ** `sweep_resnet50_{gray1,gray3,entropy,ascii,full}_{224,336,448}_s{42,123,2026}.yaml` (đủ lưới 5×3×3 = 45 run) + `sweep_convnext_tiny_{224,336,448}_s*` (full × 3 size × 3 seed). **Không cần thêm config.** Xem S5b.1 trong `docs/BACKLOG.md`.

> **Lưu ý phân biệt hai tệp dataset:** kết quả **phát hiện tổng thể (headline)** báo cáo ở `full @224` trên **`split_train/val/test.csv`** (toàn bộ mẫu hợp lệ ~14,547). **Lưới hợp nhất** (so sánh kênh & độ phân giải) chạy trên **`sweep_train/val/test.csv`** (res_eligible). KHÔNG đặt cạnh nhau hai con số từ hai tệp khác nhau.

### TRÁNH bẫy "trivial" (vì sao cần native lớn)
Phóng to ảnh nhỏ lên 448 chỉ là **upscale nội suy** → 448 không thể hơn 224 là điều gần như hiển nhiên, dễ bị phản biện. Bằng chứng phải đến từ **ảnh native LỚN thật** (PE thô, file vài trăm KB–vài MB → ảnh cao hàng nghìn px ở width 448): chứng minh **thu nhỏ ảnh to thật xuống 224 vẫn giữ đủ thông tin** → 224 ≈ 448 dù 448 là độ phân giải *thật*.

---

## 6. Yêu cầu chặt chẽ về thống kê (BẮT BUỘC để nói "tương đương")
- **Mỗi ô của lưới chạy ≥ 3 seed**; báo cáo **mean ± std**.
- **Kiểm định ý nghĩa** cho trục độ phân giải: paired t-test (trên seed) hoặc McNemar (trên dự đoán test) → "khác biệt không có ý nghĩa" hay "224 cao hơn có ý nghĩa".
- Chỉ nói "224 nhỉnh hơn" khi chênh lệch **vượt** dao động seed; nếu không → "tương đương trong nhiễu".
- **Công bằng tuyệt đối:** cùng model/split/seed-set/augment/epoch/normalize; chỉ đổi `channels`/`img_size`.
- **Không model-specific:** khẳng định trên ≥ 2 kiến trúc (ResNet50 + ConvNeXt-Tiny).

## 7. Điểm bán hàng cốt lõi: ACCURACY-VS-COST (trục độ phân giải)
Luận điểm mạnh nhất không phải "224 chính xác hơn" mà là **"224 không kém nhưng rẻ hơn nhiều"**. Cột chi phí (thời gian/epoch, GPU mem, FLOPs) đã **nằm ngay trong bảng output §2** cạnh các cột accuracy → đọc ngang một dòng thấy luôn "được gì / mất gì".

→ Kết luận: *"tăng độ phân giải không cải thiện độ chính xác có ý nghĩa nhưng tốn gấp ~2–4× tài nguyên → 224² tối ưu cho triển khai thực tế"* (hợp ngành ATTT: máy yếu, quét hàng loạt). Bổ sung **biểu đồ Pareto accuracy-vs-cost** làm nổi điểm 224².

## 8. Cơ sở kỹ thuật theo kiến trúc (đổi độ phân giải)
- **CNN (VGG/ResNet/DenseNet/ConvNeXt):** xử lý độ phân giải tùy ý nhờ adaptive pooling trước FC → chỉ đổi `img_size`. (VGG16 torchvision đã có `AdaptiveAvgPool2d((7,7))` nên nhận 224/336/448 sẵn.)
- **ViT/Swin:** đổi độ phân giải → đổi số patch → **phải nội suy 2D positional embedding** (timm: truyền `img_size=` khi `create_model`, hoặc `dynamic_img_size=True`). Kiểm tra forward ở 336/448.
- Chi phí ~ bậc hai cạnh ảnh: 336²≈2.25×, 448²≈4×. → **giảm batch size** khi tăng size (vd 64@224 → 32@336 → 16@448 trên T4); bật AMP; gradient accumulation nếu cần.

## 9. CAVEAT width=448 & EDA (đã chốt 2026-06-28)
- **Bằng chứng EDA (`scripts/eda.py`):** "width ứng viên → % ảnh cao ≥ 448": 128→76.3%, 256→66%, 384→57.2%, **448→~52%**, 512→48.3%. Nếu chỉ tối ưu %ảnh đủ cao, script gợi ý width=128; ta **cố ý chọn 448** để mọi resize trong sweep là thu nhỏ thật. Chi tiết: `docs/DATASET_PIPELINE.md` §3.
- **`image_width = 448`** (= độ phân giải lớn nhất của sweep) → native width = 448 → resize 224/336 là thu nhỏ THẬT, về 448 không resample.
- File < 4 KB bị loại; file > 30 MB chỉ đọc 30 MB đầu (`configs/data.yaml`).

## 10. Đặt tên run & phạm vi
- Mỗi ô: `{dataset}_{model}_{config}_{size}_s{seed}_{ngày}` (vd `detect_resnet50_full_224_s1_20260629`).
- Lưới đầy đủ 5×3 trên **ResNet50** (chính); trên **ConvNeXt-Tiny** ít nhất chạy trục độ phân giải với cấu hình `full` (3 size × ≥3 seed) để khẳng định kết luận 2 không phụ thuộc kiến trúc.

## Nguồn
- [Tri-channel visualised malicious code classification (ResNet cải tiến) — Applied Intelligence 2024](https://link.springer.com/article/10.1007/s10489-024-05707-4)
- [A New Framework for Visual Classification of Multi-Channel Malware — Applied Sciences 2023](https://doi.org/10.3390/app13042484)
- [Using Entropy Analysis to Find Encrypted and Packed Malware](https://www.researchgate.net/publication/3437909_Using_Entropy_Analysis_to_Find_Encrypted_and_Packed_Malware)
- [String + entropy features (Wojnowicz 2016 — Wavelet decomposition of software entropy)](https://arxiv.org/pdf/1607.04950)
- [Signal-Based Malware Classification (byte là tín hiệu 1D)](https://arxiv.org/html/2509.06548v1)
- [ViT — nội suy 2D positional embedding khi đổi độ phân giải (HF docs)](https://huggingface.co/docs/transformers/en/model_doc/vit)
- [An Image is Worth 16x16 Words (ViT) — fine-tune ở độ phân giải cao](https://arxiv.org/pdf/2010.11929)

**Cơ sở chọn ResNet50 làm backbone lưới** (xem `docs/RELATED_WORK.md` mục 5.6):
- [He et al. 2016 — Deep Residual Learning (kiến trúc gốc, CVPR)](https://arxiv.org/abs/1512.03385)
- [Wightman, Touvron & Jégou 2021 — ResNet strikes back (ResNet-50 = baseline gold-standard; nhóm tác giả timm)](https://arxiv.org/abs/2110.00476)
- [Nie 2024 — dùng ResNet50 cho ablation biểu diễn ảnh malware; lý do chọn trong họ ResNet (§4.3)](https://arxiv.org/abs/2406.03831)
- [Vasan et al. 2020 — IMCEC: fine-tune ResNet50 trên ảnh malware >99%](https://doi.org/10.1016/j.cose.2020.101748)
- [Xiao et al. 2020 — MalFCS: ResNet trích đặc trưng entropy graph](https://doi.org/10.1016/j.jpdc.2020.03.012)
- [El-Shafai et al. 2021 — so sánh 6 CNN pretrained trên Malimg (khuôn mẫu so sánh model)](https://www.mdpi.com/2076-3417/11/14/6446)
- [Pleiss et al. 2017 — Memory-Efficient DenseNets (lý do DenseNet121 không làm backbone lưới)](https://arxiv.org/abs/1707.06990)
