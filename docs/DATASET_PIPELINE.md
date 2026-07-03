# DATASET\_PIPELINE.md — Thu thập & xử lý dữ liệu (từ đầu đến cuối)

Tài liệu lý thuyết \+ quy trình cho chương "Dữ liệu & Phương pháp" của báo cáo DATN. Đề tài: **Phát hiện mã độc bằng học sâu dựa trên biểu diễn ảnh** (benign vs malware, trên **PE thô tự thu thập**). Cập nhật: 2026-06-29. Chi tiết lệnh thu thập: `docs/DATA_COLLECTION.md`. Thí nghiệm: `docs/EXPERIMENTS.md`.

---

## 0\. Tóm tắt một trang

PE thô (.exe/.dll/.bin)  — malware: figshare \+ MalwareBazaar \+ Ultimate-RAT

                           benign : figshare \+ Win10 (System32/SysWOW64/WinSxS) \+ Program Files \+ tool/app đa nguồn

   ▼ \[Gán nhãn\] dedup SHA-256 · VirusTotal verify · gán benign(0)/malware(1) · gộp RAT

   ▼ labels.csv (đầy đủ) → detect\_subset.csv (cân bằng 1.5:1)

   ▼ \[Ảnh\] đọc bytes → ảnh xám width=448 (k1) \+ entropy-byte (k2) \+ tỉ lệ ASCII (k3) → 3×H×W

   ▼ \[Split\] grouped/stratified chống rò rỉ → resize 224/336/448 → train

**Số liệu thực tế (2026-06-28):** 27,340 PE duy nhất (theo SHA-256) \= **21,511 malware** \+ **5,829 benign**. Tập phát hiện cân bằng 1.5:1 ≈ **8,743 malware \+ 5,829 benign** (`detect_subset.csv`).

---

## 1\. Vì sao chọn các nguồn này mà KHÔNG dùng BIG2015 hay Malimg

### 1.1 Bài toán quyết định việc chọn dữ liệu

Đề tài là **phát hiện mã độc** — phân loại **benign vs malware** (nhị phân). Muốn vậy, dataset **bắt buộc phải có cả hai lớp** và phải là **PE thô đầy đủ** để mô phỏng đúng tình huống thực tế (đưa một file lạ vào, quyết định độc hay sạch). Hai dataset ảnh kinh điển không đáp ứng được yêu cầu cốt lõi này.

### 1.2 Vì sao KHÔNG dùng Malimg

- **Không phải bytes thô mà là ảnh đã render sẵn.** Malimg cung cấp \~9,339 **ảnh xám đã tạo** từ 25 họ; ta không còn chuỗi byte gốc. Hệ quả: không thể tự kiểm soát quy ước bytes→ảnh (đặc biệt là **width**, kênh entropy/ASCII tính từ chuỗi byte), tức là phải "kế thừa" lựa chọn của người tạo dataset → mâu thuẫn với hai luận điểm chính của đồ án (composite 3 kênh & độ phân giải).  
- **Không có lớp benign.** Malimg chỉ gồm các họ malware → **không làm được bài toán phát hiện nhị phân**, chỉ phân loại họ.  
- **Đã bão hòa.** Accuracy trên Malimg đã \~99.5–99.8% (xem `docs/SOTA_2026.md`) → không còn dư địa đóng góp; dễ trở thành "đua benchmark".

### 1.3 Vì sao KHÔNG dùng BIG2015

- **Đã bị gỡ PE header (defanged).** Để file không thể thực thi, Microsoft **loại bỏ PE header** trong các file `.bytes`. Nghĩa là phần đầu file — nơi chứa nhiều tín hiệu phân biệt (cấu trúc header, bảng import, section) — **đã mất**. Biểu diễn ảnh từ dữ liệu defanged **khác** với ảnh từ PE thô đầy đủ, làm sai lệch giả thuyết "texture của file thật".  
- **Không có lớp benign.** BIG2015 chỉ gồm 9 họ malware (\~10,868 mẫu train) → **không phục vụ phát hiện nhị phân**.  
- **Định dạng không đồng nhất với dữ liệu của ta.** Nếu trộn BIG2015 (defanged) với PE thô (có header) thì model có thể học "kiểu định dạng" thay vì tính độc hại → nhiễu thí nghiệm.  
- **Nặng** (\~200GB cả `.bytes`\+`.asm`) trong khi không giải quyết được bài toán chính.

### 1.4 Vì sao chọn figshare \+ MalwareBazaar \+ RAT \+ benign tự thu

| Nguồn | Vai trò | Lý do chọn |
| :---- | :---- | :---- |
| **figshare 6635642** (8,970 malware PE, 5 họ \+ benign kèm) | malware \+ một phần benign | PE **thô đầy đủ header**, có nhãn họ sẵn, dễ kiểm chứng; là "xương sống" malware ổn định |
| **MalwareBazaar** (abuse.ch, API theo `signature`) | malware đa dạng, mới | Mẫu **thực tế, cập nhật**, nhiều họ hành vi khác nhau (stealer/botnet/banking/RAT) → tăng tính đại diện và độ khó thực tế |
| **Ultimate-RAT-Collection** (\~230+ họ RAT builder) | malware nhóm RAT | Bổ sung số lượng và đa dạng họ; nhãn \= tên thư mục; xử lý trong **VM cô lập** |
| **Benign đa nguồn**: figshare benign \+ Win10 System32/SysWOW64/WinSxS \+ Program Files (VM & host) \+ Sysinternals/NirCmd/Notepad++/PuTTY... | lớp benign | Benign là **lớp khan hiếm** → phải gom **nhiều nguồn/nhiều trình biên dịch** để chống thiên lệch |

Tất cả là **PE thô, đầy đủ header, đồng nhất định dạng** → đúng tinh thần "phát hiện trên file thật" và cho phép tự kiểm soát toàn bộ pipeline bytes→ảnh.

### 1.5 Bẫy thiên lệch nguồn (source bias) — và cách chống

Rủi ro lớn nhất khi tự thu dữ liệu phát hiện: nếu **benign chỉ là file Windows sạch** còn **malware đến từ kho khác**, model có thể học đặc trưng "**nguồn dữ liệu / trình biên dịch**" thay vì tính độc hại — accuracy cao giả tạo, sụp đổ ngoài thực tế. Biện pháp:

- **Đa dạng hóa benign**: nhiều hệ thống, nhiều nhà phát hành, nhiều compiler (System32, Program Files, app open-source, tool Microsoft…).  
- **Split chống rò rỉ** (grouped theo họ/biến thể, dedup SHA-256) để biến thể không vắt qua train/test.  
- **Kiểm tra bias nguồn** trong EDA và báo cáo P/R/F1/ROC-AUC thay vì chỉ accuracy.  
- Vì bài toán phát hiện-ảnh **không có benchmark ảnh chuẩn**, độ tin cậy đến từ **phương pháp chặt**, không từ "gương" SOTA (xem `docs/SOTA_2026.md`).

---

## 2\. Quy trình thu thập (tóm tắt)

Toàn bộ thao tác với malware thực hiện trong **VM cô lập** (NAT khi tải, Host-Only sau đó; snapshot trước mỗi bước lớn). Chỉ **đọc bytes**, KHÔNG thực thi. Lệnh chi tiết: `docs/DATA_COLLECTION.md`.

1. **Thu thập malware:** `collect_figshare.py` · `collect_malwarebazaar.py` (API theo họ) · `collect_rat.py` (clone \+ giải nén 7z).  
2. **Thu thập benign:** gom từ Win10 VM (System32/SysWOW64/WinSxS) \+ máy host (Program Files, Sysinternals, app open-source); lọc theo **MZ magic** để chỉ giữ PE.  
3. **Checksum & dedup:** `check_duplicates.py` → `checksums.csv`, `duplicates.csv`, `label_conflicts.csv` (đã xử lý 7 .NET DLL trùng giữa RAT và benign).  
4. **Xác minh VirusTotal:** `verify_virustotal.py` → loại `clean_but_labeled_malware` khỏi malware và `detected_as_malware` khỏi benign.  
5. **Gán nhãn:** `labeling.py` → dedup SHA-256 toàn cục, gán `label` (0=benign/1=malware), gộp RAT thành 1 nhóm → `labels.csv` (đầy đủ).  
6. **Tập phát hiện 1.5:1:** `make_detection_subset.py` (cap RAT & Winwebsec để cân bằng) → `detect_subset.csv`, **không phá** tập đầy đủ.

Ngưỡng chấp nhận: tỉ lệ malware:benign ≤ 4:1 (thực tế \~3.3:1 trước cân bằng), benign ≥ 3 source-tag.

---

## 3\. Lý thuyết: vì sao width \= 448 khi tạo ảnh

### 3.1 Cách bytes → ảnh và vai trò của width

Mỗi byte (0–255) là một pixel xám. Chuỗi 1 chiều được "cuộn" thành ảnh 2 chiều với **chiều rộng cố định W**, chiều cao `H = ceil(len(bytes)/W)` (pad 0 hàng cuối nếu lẻ). Width quyết định cách cuộn:

- **Hàng xóm ngang** của 1 pixel \= byte liền kề; **hàng xóm dọc** \= byte cách đúng W vị trí.  
- **Width cố định cho mọi mẫu** → cùng một offset byte rơi vào cùng cột → **texture đồng nhất, so sánh được** giữa các file (header ở trên, các section xếp theo cột nhất quán). Đây là lý do ta cố định W thay vì dùng bảng width-theo-kích-thước kiểu Nataraj (mỗi file một width khác nhau → texture lệch scale).

### 3.2 Vì sao chọn đúng 448 (không phải 256/512…)

Quyết định sau dựa trên 3 lý do:

1. **Khớp với thí nghiệm độ phân giải.** Đồ án so sánh 224 / 336 / 448\. Chọn **width \= giá trị lớn nhất của sweep (448)** để: ảnh **native sinh ra ở 448** → resize về 336/224 là **thu nhỏ THẬT** (giảm thông tin có thật). Nếu chọn width nhỏ hơn (vd 256\) rồi phóng lên 448, đó là **nội suy \= thông tin giả**, làm thí nghiệm vô nghĩa.  
2. **Tương thích pretrained ImageNet.** 448 \= 2×224 và 336 \= 1.5×224 → các mốc downsample "đẹp", ăn khớp với backbone pretrained ở 224\.  
3. **Cân bằng chi tiết vs chi phí.** Phân bố kích thước file rất rộng (min \~662 B, max \~284 MB). Width 448 đủ rộng để giữ chi tiết texture mà không tạo ảnh quá "mảnh và cao" bất thường; chi phí 448² vẫn chạy được trên GPU dự án (RTX 4060 / Colab).

### 3.3 Lọc outlier kích thước (đi kèm quyết định width)

- **Bỏ file \< 4 KB** (`min_bytes=4096`): ảnh quá nhỏ, gần như vô nghĩa (\~44 file).  
- **Đọc tối đa 30 MB/file** (`max_bytes≈31.4 MB`): chặn file khổng lồ gây nổ bộ nhớ; giữ phần đầu file — nơi tập trung header/code (\~185 file bị cắt).  
- **Điều kiện tham gia sweep độ phân giải** (`res_sweep_min_bytes=200704 = 448×448`): chỉ mẫu có ảnh native ≥ 448×448 mới dùng cho thí nghiệm, để 448 là downsample thật chứ không phóng to. Cờ `res_eligible` trong `valid_*.csv`.

---

## 4\. Lý thuyết: vì sao 3 kênh gray \+ entropy-byte \+ tỉ lệ ASCII

### 4.1 Vì sao 3 kênh "có ý nghĩa" thay vì 1 kênh hoặc nhân bản

Backbone pretrained ImageNet nhận 3 kênh. Hai lựa chọn tệ: (a) dùng 1 kênh xám (phải sửa conv1, và bỏ phí 2 kênh); (b) **nhân bản** kênh xám thành 3 (gray×3) — **không thêm thông tin**, chỉ tốn tài nguyên. Thay vào đó, ta đặt vào mỗi kênh **một "góc nhìn" khác nhau của cùng file**, đều **căn chỉnh không gian** (cùng H×W, cùng tọa độ pixel). Vì 3 kênh thực sự khác nhau, việc dùng `in_chans=3` \+ pretrained là **chính đáng**, và ablation sẽ chứng minh chúng *thêm thông tin thật*.

### 4.2 Kênh 1 — Grayscale (cấu trúc thô)

- **Là gì:** byte → pixel, width=448. Bản đồ trực tiếp bố cục file.  
- **Mang thông tin gì:** ranh giới và "vân" của các vùng — PE header, bảng import, vùng code (.text), dữ liệu (.data), tài nguyên (.rsrc). Mỗi vùng có phân bố byte riêng → texture riêng.  
- **Vì sao chọn:** đây là biểu diễn nền tảng (Nataraj 2011); giữ nguyên layout byte-level, là "khung xương" để hai kênh kia bổ sung.

### 4.3 Kênh 2 — Entropy từ chuỗi byte (độ ngẫu nhiên)

**Là gì.** Entropy Shannon đo *độ khó đoán* của dữ liệu. Với một cửa sổ pixel, gọi `p_i` là tần suất của mức xám `i` (0–255), entropy là:

> **H = − Σ p_i · log₂(p_i)**  (đơn vị: bit/byte; cực đại = 8 khi 256 mức xuất hiện đều như nhau)

Ta tính **entropy từ chuỗi byte**: chuỗi byte gốc, chia thành **cửa sổ 256 byte liên tiếp**, tính H cho mỗi khối rồi gán cho mọi byte trong khối → bản đồ **cùng H×W** với kênh 1 (cuộn lại theo width=448), chuẩn hóa 0–255.

**Vì sao cửa sổ 256 byte.** Đủ dài để ước lượng phân bố byte ổn định (nhận diện vùng packed/nén, entropy > 7 bit), vẫn đủ cục bộ để tách vùng; đúng cách entropy được dùng để dò packing trong file thật — trên **đoạn byte liên tiếp**, không phải lân cận 2D.

**Đọc giá trị thế nào (ý nghĩa vật lý).**

| Entropy | Vùng điển hình trong PE | Diễn giải |
|---------|------------------------|-----------|
| ~8 (rất cao, sáng) | payload **đã nén/mã hóa/packed** | byte gần như ngẫu nhiên → "khó nén" |
| trung bình | code máy `.text`, dữ liệu hỗn hợp | có cấu trúc nhưng đa dạng |
| thấp / ~0 (tối) | padding 0, bảng lặp, chuỗi đều | rất đều, dễ đoán |

**Vì sao hữu ích cho phát hiện mã độc.** Đóng gói (packing) và mã hóa payload là **kỹ thuật né tránh phổ biến của malware**; chúng đẩy entropy của vùng tương ứng lên gần cực đại. Ảnh xám (kênh 1) *có* chứa thông tin này một cách gián tiếp, nhưng entropy **làm nó tường minh thành một đại lượng** để CNN dễ khai thác. Lưu ý quan trọng (để báo cáo trung thực): **benign cũng có thể có entropy cao** (trình cài đặt nén, tài nguyên đã nén) → entropy **một mình không kết luận** được, nên nó đóng vai trò *một trong ba góc nhìn* để model kết hợp, không phải luật cứng.

**Vì sao chọn entropy từ chuỗi byte (thay vì entropy 2D trên ảnh):**
- **Đúng ngữ nghĩa packing:** packing/mã hóa là tính chất của **đoạn byte liên tiếp** trong file → entropy phải đo trên cửa sổ byte liền kề, đúng cách phân tích packing thực tế.
- **Cửa sổ 2D làm sai ngữ nghĩa:** trên ảnh đã cuộn, một cửa sổ 9×9 trộn các byte **cách nhau `width`=448 vị trí** trong file → không còn là "đoạn byte liền kề", entropy mất ý nghĩa gốc.
- **Căn chỉnh + rẻ:** tính trên chuỗi 1D rồi cuộn theo cùng width → cùng H×W, **căn chỉnh pixel** với kênh 1 & 3; vectorize bằng một lần `bincount`.
- **Có tiền lệ:** byte-entropy theo cửa sổ trượt là chuẩn để dò vùng packed/encrypted (Lyda & Hamrock 2007; byte-entropy histogram — Saxe & Berman 2015).

### 4.4 Kênh 3 — Tỉ lệ ký tự in được (printable ASCII)

**Là gì.** Với mỗi cửa sổ byte liên tiếp (mặc định 256), đếm tỉ lệ byte **in được** — nằm trong khoảng ASCII `0x20–0x7E` (dấu cách, chữ, số, ký hiệu) — trên tổng số byte của cửa sổ:

> **ratio = (số byte in được) / (kích thước cửa sổ)** ∈ [0, 1]

Gán tỉ lệ cho mọi byte trong cửa sổ → bản đồ cùng H×W, map **×255 (tuyệt đối)**: 0 = không có text, 255 = toàn text. Không min-max từng ảnh → giá trị **nhất quán giữa các mẫu** (cùng mức sáng = cùng ý nghĩa).

**Bắt thông tin gì trong PE.** Phần lớn thông tin "đọc được" của file ở dạng text ASCII: URL C2, tên hàm API, đường dẫn, khóa registry, thông báo, tên file. Vùng **chuỗi/text/resource** có mật độ ASCII cao (sáng); vùng **code nhị phân hoặc packed/mã hóa** có mật độ thấp (tối — byte trải khắp 0–255, ít rơi vào 0x20–0x7E). Bản đồ này vẽ ra "đâu là text, đâu là non-text" — bổ sung cho cấu trúc thô (kênh 1) và độ ngẫu nhiên (kênh 2).

**Vì sao chọn tỉ lệ ASCII (thay cho nén / phổ tần / toán tử texture 2D):**
- **Trực giao với entropy nhất:** entropy đo *độ ngẫu nhiên*, ASCII-ratio đo *tính văn bản* — hai chiều khác hẳn (nén & phổ tần đều tương quan nhiều với entropy). 3 kênh càng ít trùng lặp càng "đáng giá".
- **Từ chuỗi byte, căn chỉnh hoàn hảo:** cùng cơ chế cửa sổ byte như kênh 2 → cùng H×W, cùng tọa độ pixel.
- **Rẻ, nhất quán, dễ giải thích:** chỉ so ngưỡng byte + trung bình cửa sổ (vectorize thuần numpy); giá trị tuyệt đối 0–1.
- **Có cơ sở:** string là một trong những đặc trưng tĩnh mạnh nhất; Wojnowicz (2016) dùng **string + entropy** đạt ~99% phát hiện, <1% false positive.

### 4.5 Ghép kênh, chuẩn hóa, và bằng chứng

Hình dưới: 3 kênh sinh từ bytes của một file PE thật (ảnh width=448), cả ba **căn chỉnh không gian** rồi chồng thành ảnh màu giả (R=gray, G=entropy, B=ascii):



- Tính cả 3 kênh ở **native** rồi stack `[gray, entropy, ascii]` → `3×H×W`; resize về `img_size` ở bước transform.
- **Chuẩn hóa per-channel** bằng mean/std tính trên tập train (mỗi kênh một thống kê) — **không** dùng stat ImageNet RGB vì các kênh không phải màu.
- **Ablation (luận điểm A):** so `gray / +entropy / +ascii / full / gray×3` (cùng split/seed) → kỳ vọng `full > gray` (entropy & ASCII thêm thông tin) và `gray×3 ≈ gray` (nhân bản vô ích).

## 5\. Đầu ra của giai đoạn dữ liệu

- `labels.csv` (đầy đủ, cho phân loại họ) \+ `detect_subset.csv` (1.5:1, cho phát hiện) \+ `valid_*.csv` (đã lọc min/max, có cờ `res_eligible`).  
- Ảnh 3 kênh: bản **native** (archive) \+ bản **resize 224/336/448** (để train).  
- Split grouped/stratified chống rò rỉ \+ mean/std per-channel của train.

---

## Nguồn tham khảo

- [Microsoft Malware Classification Challenge (BIG 2015\) — đã gỡ PE header, chỉ malware, 9 họ](https://www.researchgate.net/figure/Data-description-of-Microsoft-Malware-Classification-Challenge-BIG-2015_tbl2_358664952)  
- [Robustness & Explainability in CNN Malware Detection (mô tả BIG2015 bỏ header, không có benign) — arXiv 2025](https://arxiv.org/pdf/2503.01391)  
- [Nataraj et al., Malware Images: Visualization and Automatic Classification (2011)](https://dl.acm.org/doi/10.1145/2016904.2016908)  
- [Using Entropy Analysis to Find Encrypted and Packed Malware](https://www.researchgate.net/publication/3437909_Using_Entropy_Analysis_to_Find_Encrypted_and_Packed_Malware)  
- [String + entropy features — Wavelet decomposition of software entropy (Wojnowicz 2016)](https://arxiv.org/pdf/1607.04950)  
- [Signal-Based Malware Classification (byte là tín hiệu 1D)](https://arxiv.org/html/2509.06548v1)  
- [figshare 6635642 — Malware/Benign PE dataset](https://figshare.com/articles/dataset/_/6635642)  
- [MalwareBazaar (abuse.ch)](https://bazaar.abuse.ch/)

