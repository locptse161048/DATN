# RELATED_WORK — Cơ sở tài liệu cho các quyết định kỹ thuật

> Tổng hợp bài báo/nghiên cứu làm cơ sở trích dẫn cho từng quyết định trong CLAUDE.md.
> Kế hoạch & thứ tự research: `docs/RESEARCH_PLAN.md`. Cập nhật: 2026-07-03.
> Mỗi entry: Citation → Link → Tóm tắt → Kết quả chính → Quyết định liên quan → Vì sao phù hợp.

## Mục lục
1. [Nền tảng: bytes → ảnh](#1-nền-tảng-bytes--ảnh)
2. [Luận điểm A: ảnh đa kênh composite](#2-luận-điểm-a-ảnh-đa-kênh-composite)
3. [Luận điểm B: độ phân giải vs chi phí](#3-luận-điểm-b-độ-phân-giải-vs-chi-phí)
4. [Phương pháp luận thí nghiệm](#4-phương-pháp-luận-thí-nghiệm)
5. [Model & XAI](#5-model--xai)
6. [Bảng tra: quyết định → paper](#6-bảng-tra-quyết-định--paper)

---

## 1. Nền tảng: bytes → ảnh

### 1.1. Malware Images: Visualization and Automatic Classification (Nataraj et al., 2011, VizSec)
- **Citation:** L. Nataraj, S. Karthikeyan, G. Jacob, B. S. Manjunath, "Malware images: visualization and automatic classification," *Proc. 8th Int. Symp. on Visualization for Cyber Security (VizSec '11)*, ACM, 2011.
- **Link:** https://dl.acm.org/doi/10.1145/2016904.2016908 · PDF: https://vizsec.org/files/2011/Nataraj.pdf
- **Tóm tắt:** Paper gốc của toàn bộ hướng "malware-as-image": đọc binary như chuỗi byte 8-bit → ảnh grayscale (mỗi byte = 1 pixel), **width cố định theo bảng tra kích thước file, height thay đổi theo độ dài**. Phân loại bằng đặc trưng texture GIST + k-NN.
- **Kết quả chính:** 98% accuracy trên 9,458 mẫu / 25 họ (sau này thành dataset Malimg); quan sát then chốt: mẫu cùng họ có layout/texture ảnh rất giống nhau, không cần disassembly hay chạy động.
- **Trích dẫn nguyên văn** (abstract): *"For many malware families, the images belonging to the same family appear very similar in layout and texture."* — đây chính là giả thuyết texture của đồ án.
- **Quyết định liên quan:** ý tưởng cốt lõi (mục 1 CLAUDE.md); quy ước bytes → ảnh kênh 1 (mục 4).
- **Vì sao phù hợp:** đây là citation bắt buộc — giả thuyết nghiên cứu của đồ án ("texture phân biệt được giữa benign/malware và giữa các họ") chính là quan sát của Nataraj mở rộng sang bài toán detection. Quy ước width-cố-định/height-thay-đổi của dự án kế thừa trực tiếp từ đây (dự án đơn giản hóa: 1 width duy nhất = 448 thay vì bảng tra, để texture đồng nhất giữa mọi mẫu — điểm khác biệt cần nêu rõ trong báo cáo).

### 1.2. Security through the Eyes of AI: How Visualization is Shaping Malware Detection (2025, survey)
- **Citation:** A. Aghakhani et al. (nhóm Univ. Padova, Cochin UST, Univ. Milan, Univ. Pavia), "Security through the Eyes of AI: How Visualization is Shaping Malware Detection," arXiv:2505.07574, 2025 (bản journal: Computer Science Review, 2026).
- **Link:** https://arxiv.org/abs/2505.07574 · https://www.sciencedirect.com/science/article/pii/S1574013726000237
- **Tóm tắt:** Survey toàn diện nhất hiện nay về visualization-based malware detection (2018–2025), phân loại theo pipeline: thu thập dataset → sinh ảnh → trích đặc trưng → phân loại → đánh giá → robustness.
- **Kết quả chính:** hệ thống hóa các phương pháp sinh ảnh (grayscale, RGB, Hilbert, entropy...), chỉ ra gap: thiếu chuẩn hóa cách sinh ảnh, thiếu benchmark detection (đa số làm family classification trên Malimg/BIG2015), thiếu đánh giá robustness.
- **Quyết định liên quan:** mục 3 CLAUDE.md — ghi chú "bài toán phát hiện dựa trên ảnh không có benchmark ảnh chuẩn".
- **Vì sao phù hợp:** dùng làm khung viết chương Related Work của báo cáo; đồng thời là bằng chứng cho luận điểm "không có benchmark chuẩn nên độ tin cậy dựa vào phương pháp chặt" — đúng lập trường của đồ án. Các gap survey chỉ ra (detection trên PE thô, chống bias) chính là đóng góp của đồ án.

### 1.3. EMBER: An Open Dataset for Training Static PE Malware ML Models (Anderson & Roth, 2018)
- **Citation:** H. S. Anderson, P. Roth, "EMBER: An Open Dataset for Training Static PE Malware Machine Learning Models," arXiv:1804.04637, 2018.
- **Link:** https://arxiv.org/abs/1804.04637
- **Tóm tắt:** Dataset chuẩn cho static PE malware detection dạng **feature vector** (không phải ảnh): 1.1M PE với đặc trưng header, import, byte histogram, byte-entropy histogram, **đặc trưng string in được** (số lượng, độ dài trung bình, histogram ký tự, entropy của strings).
- **Kết quả chính:** LightGBM baseline ROC-AUC > 0.999; trở thành benchmark de-facto cho static detection.
- **Quyết định liên quan:** mục 3 CLAUDE.md — ghi chú "EMBER/BODMAS là đặc trưng, không phải ảnh"; kênh 3 (ASCII ratio).
- **Vì sao phù hợp:** hai vai trò: (1) dẫn chứng rằng benchmark detection hiện có là feature-based nên đồ án phải tự xây tập detection từ PE thô; (2) EMBER đưa đặc trưng printable-string vào bộ feature chuẩn → xác nhận tỉ lệ ký tự in được là tín hiệu phân loại có giá trị, củng cố lựa chọn kênh 3.

### 1.4. Malware Classification Based on Image Segmentation (Nie, 2024)
- **Citation:** W. Nie, "Malware Classification Based on Image Segmentation," arXiv:2406.03831, 2024.
- **Link:** https://arxiv.org/abs/2406.03831
- **Tóm tắt:** Ngoài đóng góp chính (cắt ảnh theo section PE thành multi-channel), paper dành riêng một phần thảo luận **width alignment như một hyperparameter**: cách chọn width làm thay đổi texture và cấu trúc ảnh, ảnh hưởng trực tiếp đến hiệu năng model; đặc biệt vùng `.rsrc` chứa resource (ảnh nhúng...) rất nhạy với width — cùng một file, đổi width có thể tạo texture khác hẳn.
- **Kết quả chính:** thực nghiệm cho thấy hiệu năng model thay đổi theo cách căn width; kết luận width alignment là siêu tham số mới của bài toán malware visualization, cần được chọn và cố định có chủ đích. Số liệu (ResNet50, BIG2015, logloss test — thấp \= tốt): width cố định 1024 \= **0.0265** \< bảng Nataraj \= 0.0316 \< sqrt(file size) \= 0.0330.
- **Trích dẫn nguyên văn** (§4.2, đã đối chiếu toàn văn):
  - *"The choice of image width not only affects the degree of detail loss but also alters the texture and structural features of the image."*
  - *"Notably, when the .rsrc section contains resources like images, the alignment of the image width can have a particularly pronounced effect on the grayscale image, potentially causing significant differences even among images with originally similar textures. Therefore, the alignment method for image width emerges as a new hyperparameter in the problem of malware visualization and classification."*
  - *"Employing a fixed width alignment strategy helps mitigate the impact of factors such as distortion, texture changes, and structural feature alterations that may occur during image scaling."* (§4.4, bình luận kết quả S1–S3)
- **Quyết định liên quan:** "width CỐ ĐỊNH = 448, chốt sau EDA" (mục 3, 4 CLAUDE.md).
- **Vì sao phù hợp:** đây là bằng chứng rằng **width không phải chi tiết cài đặt tùy tiện mà là hyperparameter phải chốt bằng thực nghiệm/EDA** — đúng quy trình đồ án đã làm (EDA 2026-06-28 → chốt 448). Trích khi biện luận vì sao dự án khảo sát phân bố kích thước file trước khi chọn width thay vì lấy đại một giá trị từ paper khác.

### 1.5. Image-based malware representation with EfficientNet (Chaganti et al., 2022, JISA)
- **Citation:** R. Chaganti, V. Ravi, T. D. Pham, "Image-based malware representation approach with EfficientNet convolutional neural networks for effective malware classification," *J. Information Security and Applications*, 69, 103306, 2022.
- **Link:** https://doi.org/10.1016/j.jisa.2022.103306
- **Tóm tắt:** So sánh các cách biểu diễn ảnh byte-level, trong đó có thí nghiệm giữa **width cố định vs width theo kích thước file** (kiểu bảng tra Nataraj); đánh giá nhiều CNN để cân đối tài nguyên tính toán.
- **Kết quả chính:** **width cố định (512) cho kết quả phân loại tốt hơn** width phụ thuộc kích thước file trên Microsoft BIG2015; lý do: width cố định làm texture giữa các mẫu **đồng nhất và so sánh được** — cùng một pattern byte luôn tạo cùng một hình dạng 2D bất kể file to nhỏ.
- **Trích dẫn nguyên văn** (abstract Chaganti et al. 2022): *"Additionally, the CNN pretrained models are evaluated against the different types of malware image representation methods, which are distinguished based on selection of the image width size. Our evaluation of the proposed model EfficientNetB1 shows that it has achieved an accuracy of 99% to classify the Microsoft Malware Classification Challenge (MMCC) malware classes using the malware image representation with fixed image width and also require fewer network parameters compared to other pretrained models to achieve the performance accuracy."* — xác nhận trực tiếp: trục so sánh của paper chính là **cách chọn width**, và kết quả tốt nhất đạt được với **fixed width**.
- **Trích dẫn xác nhận độc lập** (Nie 2024, §4.2, nguyên văn): *"Chaganti et al. demonstrated that using a fixed width (512 bytes) for malware grayscale images is beneficial for classification tasks, at least in the context of the Microsoft Malware Dataset."* — và Nie ghi nhận Chaganti *không* phân tích lý do; phần cơ chế do Nie bổ sung (xem 1.4).
- **Quyết định liên quan:** "width cố định → texture đồng nhất giữa các mẫu" (mục 4 CLAUDE.md).
- **Vì sao phù hợp:** là bằng chứng thực nghiệm trực tiếp nhất cho lựa chọn **một width cố định duy nhất cho toàn dataset** thay vì bảng tra theo file size của Nataraj 1.1 (vốn làm mỗi mẫu một width → cùng pattern byte tạo texture khác nhau, CNN khó học). Giá trị 512 của họ cùng bậc với 448 của đồ án → 448 nằm trong vùng đã được kiểm chứng của văn liệu.

### Hộp tổng hợp: chuỗi lập luận cho width = 448
Không có paper nào "chứng minh 448 tối ưu" — và cũng không có con số nào trong văn liệu được chứng minh tối ưu phổ quát (mỗi paper dùng 256/512/1024... theo dataset của họ). Lập luận cho 448 ghép từ 4 mảnh có cơ sở:

1. **Phải dùng width cố định** (không theo file size): Chaganti 2022 (1.5) — fixed width thắng size-dependent width; Nataraj 1.1 dùng bảng tra chỉ vì hạn chế GIST thời 2011.
2. **Width là hyperparameter phải chốt bằng khảo sát dữ liệu**: Nie 2024 (1.4) — width đổi là texture đổi, nên chọn qua EDA trên chính dataset (đồ án: EDA 2026-06-28, phân bố kích thước file + tỉ lệ mẫu đạt height ≥ 448).
3. **Width phải ≥ độ phân giải train lớn nhất (448²) để mọi biến thể 224/336/448 đều là downsample thật**: Peters & Farhat 2023 (3.1) — resize là phép biến đổi mất mát; downsample từ ảnh native lớn giữ texture toàn cục, ngược lại nếu width < img_size thì phải **upsample = nội suy bịa pixel không mang thông tin mới**, làm sweep độ phân giải (luận điểm B) mất giá trị so sánh. Đây là lý do quyết định: width = max(img_size) = 448.
4. **448 nằm trong dải quy ước của văn liệu và chia hết cho 64**: dải width phổ biến 256–1024 (Nataraj 1.1: 64–1024; Chaganti: 512; các nghiên cứu khác: 256/1024); 448 = 64×7 = 2×224, khớp lưới stride của các backbone CNN (downsample tổng 32×: 448/32 = 14 nguyên).

**Điểm cần ghi vào threats to validity:** PE FileAlignment mặc định là 512 byte — width 512 sẽ căn ranh giới section thẳng hàng theo dòng, còn 448 thì không (tạo "trôi chéo" nhẹ ở ranh giới section, chính là hiệu ứng Nie 2024 mô tả với `.rsrc`). Đồ án chấp nhận trade-off này vì ưu tiên tính chất downsample-thuần của thiết kế sweep (mảnh 3); có thể nêu ablation width 448 vs 512 làm hướng mở rộng.

---

## 2. Luận điểm A: ảnh đa kênh composite

### 2.1. Using Entropy Analysis to Find Encrypted and Packed Malware (Lyda & Hamrock, 2007, IEEE S&P Magazine)
- **Citation:** R. Lyda, J. Hamrock, "Using Entropy Analysis to Find Encrypted and Packed Malware," *IEEE Security & Privacy*, 5(2), 40–45, 2007.
- **Link:** https://doi.org/10.1109/MSP.2007.48 · https://www.researchgate.net/publication/3437909
- **Tóm tắt:** Paper kinh điển đặt nền móng cho entropy học trong phân tích malware: tính Shannon entropy trên các khối byte của file thực thi để phát hiện vùng packed/encrypted (entropy cao ≈ 8 bit/byte) vs code/data thường (entropy thấp hơn).
- **Kết quả chính:** thống kê ngưỡng entropy phân biệt native/packed/encrypted trên hàng nghìn mẫu; packed & encrypted malware chiếm tỉ lệ lớn malware thực tế.
- **Quyết định liên quan:** kênh 2 (entropy cửa sổ byte liền kề) — mục 4 CLAUDE.md.
- **Vì sao phù hợp:** là cơ sở lý thuyết trực tiếp cho kênh entropy: đồ án tính Shannon entropy trên **cửa sổ byte liên tiếp** (256 byte) đúng theo ngữ nghĩa của Lyda & Hamrock (phát hiện vùng packed/mã hóa), thay vì cửa sổ 2D trên ảnh vốn trộn các byte cách nhau `width` không liên quan. Trích khi biện luận "vì sao entropy phải tính từ chuỗi byte".

### 2.2. Classification of Malware by Using Structural Entropy on CNN (Gibert et al., 2018, AAAI/IAAI)
- **Citation:** D. Gibert, C. Mateu, J. Planes, R. Vicens, "Classification of Malware by Using Structural Entropy on Convolutional Neural Networks," *Proc. AAAI-18 (IAAI track)*, 2018.
- **Link:** https://dl.acm.org/doi/abs/10.5555/3504035.3504987
- **Tóm tắt:** Biểu diễn file như **chuỗi entropy** (structural entropy): chia file thành các chunk byte liên tiếp, tính entropy mỗi chunk → chuỗi 1D → CNN 1D phân loại họ.
- **Kết quả chính:** trên Microsoft BIG2015, structural entropy + CNN đạt kết quả cạnh tranh với đặc trưng thủ công phức tạp; chứng minh chuỗi entropy đủ giàu thông tin để phân loại họ.
- **Quyết định liên quan:** kênh 2 — cửa sổ **liên tiếp** trên chuỗi byte, mặc định 256 byte.
- **Vì sao phù hợp:** xác nhận đúng thiết kế của kênh 2: entropy tính theo **chunk byte liên tiếp** (không phải láng giềng 2D) là biểu diễn có giá trị phân loại đã được kiểm chứng. Đồ án đi xa hơn: trải entropy về đúng vị trí byte để căn chỉnh không gian với kênh grayscale — điểm mới cần nhấn mạnh.

### 2.3. MalFCS: Malware classification framework via entropy graphs + deep CNN (Xiao et al., 2020, JPDC)
- **Citation:** G. Xiao, J. Li, Y. Chen, K. Li, "MalFCS: An effective malware classification framework with automated feature extraction based on deep convolutional neural networks," *J. Parallel and Distributed Computing*, 141, 49–58, 2020.
- **Link:** https://doi.org/10.1016/j.jpdc.2020.03.012
- **Tóm tắt:** Trực quan hóa malware thành **entropy graph** (ảnh từ structural entropy) thay vì grayscale thô → CNN sâu (ResNet) trích đặc trưng → SVM phân loại.
- **Kết quả chính:** accuracy 0.997 (Malimg) và ~1.0 (BIG2015) — SOTA thời điểm đó; lập luận: "một biểu diễn low-order duy nhất (grayscale) có thể bỏ sót đặc trưng ẩn của họ malware".
- **Quyết định liên quan:** luận điểm A — kênh entropy bổ sung thông tin so với grayscale đơn kênh.
- **Vì sao phù hợp:** bằng chứng mạnh rằng biểu diễn entropy **một mình** đã đạt kết quả rất cao → kỳ vọng hợp lý rằng ghép entropy làm kênh bổ sung cho grayscale sẽ tăng thông tin (điều ablation của đồ án kiểm chứng). MalFCS thay thế grayscale bằng entropy; đồ án **kết hợp cả hai + ASCII** trong một tensor căn chỉnh không gian — khác biệt để định vị đóng góp.

### 2.4. HIT4Mal: Hybrid Image Transformation for Malware Classification (Vu et al., 2020, ETT)
- **Citation:** D.-L. Vu, T.-K. Nguyen, T. V. Nguyen, T. N. Nguyen, F. Massacci, P. H. Phung, "HIT4Mal: Hybrid image transformation for malware classification," *Trans. on Emerging Telecommunications Technologies*, 31(11), e3789, 2020.
- **Link:** https://doi.org/10.1002/ett.3789
- **Tóm tắt:** Paper gần nhất với luận điểm A: mã hóa binary thành **ảnh màu nhiều kênh** kết hợp đặc trưng thống kê (**entropy**) và cú pháp (**character class — phân lớp byte theo loại ký tự**, trong đó có printable ASCII), sắp xếp pixel bằng Hilbert curve.
- **Kết quả chính:** 93.01% accuracy trên 16,000 mẫu (8k malware + 8k benign — bài toán **detection**, không chỉ family); mã hóa hybrid entropy+character class thắng các mã hóa đơn.
- **Trích dẫn nguyên văn** (abstract): *"…these developed images contain statistical (e.g., entropy) and syntactic artifacts (e.g., strings), and their pixels are filled up using space-filling curves."* — đúng cặp đặc trưng thống kê (entropy) + cú pháp (strings/ASCII) mà đồ án dùng làm kênh 2 và 3.
- **Quyết định liên quan:** toàn bộ thiết kế 3 kênh composite (gray + entropy + ASCII) — mục 3, 4 CLAUDE.md.
- **Vì sao phù hợp:** đây là tiền lệ trực tiếp nhất: chứng minh **kết hợp entropy + phân lớp ký tự trong ảnh màu tốt hơn ảnh đơn kênh**, và trên đúng bài toán detection benign-vs-malware như đồ án. Khác biệt của đồ án: giữ layout tuyến tính row-major thay vì Hilbert (giữ tương ứng trực tiếp pixel↔offset, thuận cho Grad-CAM), dùng ASCII-ratio liên tục thay vì class rời rạc, và có ablation từng kênh + so với gray×3 một cách hệ thống.

### 2.5. Evaluation of printable character-based malicious PE file-detection method (Otsubo et al., 2022, ICT Express)
- **Citation:** M. Mimura et al., "Evaluation of printable character-based malicious PE file-detection method," *ICT Express*, 8(2), 2022.
- **Link:** https://www.sciencedirect.com/science/article/pii/S2542660522000245
- **Tóm tắt:** Detection PE độc hại **chỉ từ ký tự in được** (printable characters) trong file: trích chuỗi printable → mô hình ngôn ngữ (Doc2vec) → classifier; đánh giá trên FFRI dataset 400k benign + 400k malware theo chuỗi thời gian 2019–2021.
- **Kết quả chính:** F1 = 0.981 với Doc2vec + MLP; token printable đặc thù có sức phân loại cao và giữ hiệu quả với malware mới.
- **Quyết định liên quan:** kênh 3 (tỉ lệ printable ASCII 0x20–0x7E theo cửa sổ) — mục 4 CLAUDE.md.
- **Vì sao phù hợp:** bằng chứng độc lập, quy mô lớn rằng **riêng thông tin ký tự in được đã đủ phát hiện malware với F1 rất cao** → mật độ/phân bố printable là tín hiệu mạnh, xứng đáng một kênh riêng. Đồ án dùng dạng tỉ lệ theo cửa sổ (giữ tính không gian, chỉ ra *vùng nào* nhiều text) thay vì NLP trên chuỗi — bổ trợ chứ không trùng lặp.

### 2.6. Wavelet decomposition of software entropy reveals symptoms of malicious code (Wojnowicz et al., 2016)
- **Citation:** M. Wojnowicz, G. Chisholm, M. Wolff, X. Zhao, "Wavelet decomposition of software entropy reveals symptoms of malicious code," *J. Innovation in Digital Ecosystems*, 3(2), 2016. arXiv:1607.04950.
- **Link:** https://arxiv.org/abs/1607.04950
- **Tóm tắt:** Tính chuỗi entropy trên các khối byte liên tiếp của file PE rồi phân tích wavelet đa tỉ lệ để đo "mức độ gập ghềnh entropy" (entropic suspiciousness); kết hợp với đặc trưng string trong hệ detection quy mô lớn.
- **Kết quả chính:** riêng đặc trưng entropy-wavelet đã tăng odds phát hiện; đây là nguồn của con số "string + entropy đạt ~99% detection, <1% FP" đã dẫn trong `docs/EXPERIMENTS.md` và `docs/DATASET_PIPELINE.md` §4.4 *(con số này cần kiểm tra lại đúng trang trong PDF trước khi đưa vào báo cáo)*.
- **Quyết định liên quan:** cặp kênh 2 + kênh 3 (entropy + ASCII) như hai tín hiệu bổ sung nhau.
- **Vì sao phù hợp:** là bằng chứng ở quy mô công nghiệp (Cylance) rằng entropy theo khối byte liên tiếp + string là cặp đặc trưng tĩnh mạnh — đúng cặp mà đồ án không gian hóa thành 2 kênh ảnh. Đã được các doc của dự án dẫn từ trước nhưng nay mới có entry chính thức.

---

## 3. Luận điểm B: độ phân giải vs chi phí

### 3.1. High-resolution Image-based Malware Classification using Multiple Instance Learning (Peters & Farhat, 2023)
- **Citation:** T. Peters, H. Farhat, "High-resolution Image-based Malware Classification using Multiple Instance Learning," arXiv:2311.12760, 2023.
- **Link:** https://arxiv.org/abs/2311.12760 · Code: https://github.com/timppeters/MIL-Malware-Images
- **Tóm tắt:** Phân tích thực nghiệm cho thấy **resize ảnh malware về kích thước nhỏ gây mất thông tin then chốt** và có thể bị khai thác (binary enlargement attack); đề xuất giữ ảnh độ phân giải cao, chia patch + multiple instance learning với attention.
- **Kết quả chính:** trên BIG2015, MIL đạt 96.6% trên mẫu bị phóng to đối kháng, so với baseline resize chỉ 22.8%.
- **Trích dẫn nguyên văn** (abstract, đã đối chiếu): *"Current methods of visualisation-based malware classification largely rely on lossy transformations of inputs such as resizing to handle the large, variable-sized images. Through empirical analysis and experimentation, it is shown that these approaches cause crucial information loss that can be exploited."*
- **Quyết định liên quan:** luận điểm B (mục 3 CLAUDE.md) — câu hỏi 224 vs 336 vs 448; quyết định lưu bản native làm archive.
- **Vì sao phù hợp:** là "đối trọng" khoa học của H1: paper này lập luận resolution cao/không resize là cần thiết, còn đồ án kiểm chứng **trong điều kiện thường (không adversarial), 224² đã đủ**. Trích dẫn để (a) công nhận trade-off tồn tại, (b) khoanh vùng phạm vi kết luận H1 (không phủ nhận adversarial case), (c) biện minh việc lưu ảnh native.

### 3.2. Impact of Image Size on Accuracy and Generalization of CNNs (Rukundo, 2019/2021)
- **Citation:** O. Rukundo, "Effects of Image Size on Deep Learning," / "Impact of Image Size on Accuracy and Generalization of Convolutional Neural Networks," 2019–2021.
- **Link:** https://www.researchgate.net/publication/332241609
- **Tóm tắt:** Khảo sát hệ thống ảnh hưởng của input size lên accuracy và khả năng khái quát của CNN (ngoài domain malware): size lớn hơn không phải lúc nào cũng tốt hơn; tồn tại điểm bão hòa nơi thêm pixel chỉ thêm chi phí.
- **Kết quả chính:** quan hệ accuracy–size phi tuyến, phụ thuộc task; chi phí tính toán tăng ~bình phương theo cạnh ảnh.
- **Quyết định liên quan:** luận điểm B — kỳ vọng "224 xấp xỉ 336/448 nhưng rẻ hơn nhiều lần".
- **Vì sao phù hợp:** cho khung lý thuyết tổng quát của H1 từ computer vision; đồ án là instance của câu hỏi này trong domain ảnh malware, nơi texture lặp (không phải chi tiết nhỏ) là tín hiệu chính — lý do kỳ vọng điểm bão hòa đến sớm (≤224).

### 3.3. Hierarchical malware detection using CNN-based hybrid models (2026, Scientific Reports) + các thực nghiệm size trong domain
- **Citation:** "Hierarchical malware detection, family identification, and variant attribution using CNN-based hybrid models on grayscale executable images," *Scientific Reports*, 2026; và "An Empirical Analysis of Image-Based Learning Techniques for Malware Classification" (Prajapati & Stamp, arXiv:2103.13827).
- **Link:** https://www.nature.com/articles/s41598-026-40655-8 · https://arxiv.org/abs/2103.13827
- **Tóm tắt:** Các thực nghiệm trong domain malware với nhiều kích thước ảnh (32–1024): resize về 224 vẫn giữ được texture features cốt lõi; giảm kích thước ảnh giảm thời gian train tới ~8× mà accuracy gần như không đổi trong nhiều cấu hình.
- **Kết quả chính:** texture toàn cục (điều CNN dùng để phân loại họ) sống sót qua downsample; chi tiết cục bộ mất trước.
- **Quyết định liên quan:** luận điểm B; chọn 224 làm size chính cho toàn bộ thí nghiệm detection.
- **Vì sao phù hợp:** bằng chứng trong-domain rằng H1 khả thi. Lưu ý các paper này thường thực nghiệm 1 seed, không kiểm định thống kê — đồ án làm chặt hơn (≥3 seed, mean±std, kiểm định, bảng accuracy-vs-cost) chính là đóng góp phương pháp.

### 3.4. Accounting for Variance in Machine Learning Benchmarks (Bouthillier et al., 2021, MLSys)
- **Citation:** X. Bouthillier et al., "Accounting for Variance in Machine Learning Benchmarks," *Proc. MLSys 3*, 2021. arXiv:2103.03098.
- **Link:** https://arxiv.org/abs/2103.03098
- **Tóm tắt:** Chỉ ra variance do seed (khởi tạo trọng số, sampling, augmentation) trong benchmark ML **thường lớn hơn khác biệt giữa các thuật toán**; kết luận từ 1 run đơn lẻ có thể đảo ngược thứ hạng model; khuyến nghị nhiều run + kiểm định thống kê.
- **Kết quả chính:** phân rã nguồn variance thực nghiệm trên nhiều benchmark; đề xuất quy trình so sánh đúng (multi-seed, paired test).
- **Trích dẫn nguyên văn** (abstract, đã đối chiếu): *"Strong empirical evidence that one machine-learning algorithm A outperforms another one B ideally calls for multiple trials optimizing the learning pipeline over sources of variation such as data sampling, data augmentation, parameter initialization, and hyperparameters choices."* và *"…variance due to data sampling, parameter initialization and hyperparameter choice impact markedly the results."*
- **Quyết định liên quan:** yêu cầu "≥3 seed + mean±std + kiểm định thống kê" của luận điểm B (mục 3 CLAUDE.md).
- **Vì sao phù hợp:** là cơ sở phương pháp luận trực tiếp cho thiết kế thống kê của H1: khác biệt 224-vs-448 dự kiến nhỏ, nên nếu không multi-seed + kiểm định thì kết luận "xấp xỉ nhau" hay "nhỉnh hơn" đều vô nghĩa. Trích trong phần Experimental Setup.

### 3.5. Cơ sở chọn bộ seed {42, 123, 2026}
- **Citation:**
  - D. Picard, "Torch.manual_seed(3407) is all you need: On the influence of random seeds in deep learning architectures for computer vision," arXiv:2109.08203, 2021.
  - J. Pineau et al., "Improving Reproducibility in Machine Learning Research (A Report from the NeurIPS 2019 Reproducibility Program)," *JMLR* 22, 2021. arXiv:2003.12206.
  - (kết hợp với Bouthillier et al. 2021 — mục 3.4)
- **Link:** https://arxiv.org/abs/2109.08203 · https://jmlr.org/papers/v22/20-303.html
- **Tóm tắt:** Picard quét tới 10⁴ seed trên CIFAR-10/ImageNet: phân bố accuracy theo seed có outlier tốt/tệ rõ rệt → báo cáo kết quả từ một seed "đẹp" là cherry-picking (chính tiêu đề paper là câu mỉa mai trò "seed may mắn"). Pineau et al. (chương trình Reproducibility của NeurIPS) đặt chuẩn: mô tả đầy đủ cấu hình ngẫu nhiên (seed), báo cáo kết quả trên nhiều run kèm thước đo phân tán (mean±std), công bố code/config để tái lập.
- **Kết quả chính:** chuẩn cộng đồng cho seed gồm 4 tính chất: (1) **chọn trước** (pre-specified, không chọn sau khi thấy kết quả); (2) **tùy ý** (arbitrary — giá trị cụ thể không mang ý nghĩa); (3) **cố định & công bố** (ghi trong config, tái lập được); (4) **nhiều seed** + báo cáo mean±std thay vì kết quả đơn lẻ.
- **Quyết định liên quan:** bộ seed {42, 123, 2026} trong `EXPERIMENTS.md` §6, `reports/experimentA.md` §1; nguyên tắc reproducibility (CLAUDE.md mục 6).
- **Vì sao phù hợp:** trả lời trực tiếp câu hỏi "vì sao 42/123/2026?": **giá trị cụ thể không cần cơ sở — quy trình mới cần cơ sở.** 42 là quy ước văn hóa của cộng đồng (Hitchhiker's Guide), 123 là dãy đơn giản phổ biến, 2026 là năm thực hiện đồ án — cả ba đều tùy ý một cách minh bạch, chọn trước khi chạy, cố định trong config YAML, và không seed nào được chọn vì "cho kết quả đẹp". Bằng chứng nội bộ rằng dự án không cherry-pick: trong `experimentA.md`, seed 42 không phải seed tốt nhất (gray1: 42→F1 96.80 < 123→97.44) nhưng vẫn được giữ nguyên và báo cáo đầy đủ. Kết luận rút từ mean±std trên cả 3 seed + kiểm định (theo 3.4), không từ seed đơn lẻ nào.

---

## 4. Phương pháp luận thí nghiệm

### 4.1. TESSERACT: Eliminating Experimental Bias in Malware Classification across Space and Time (Pendlebury et al., 2019, USENIX Security)
- **Citation:** F. Pendlebury, F. Pierazzi, R. Jordaney, J. Kinder, L. Cavallaro, "TESSERACT: Eliminating Experimental Bias in Malware Classification across Space and Time," *28th USENIX Security Symposium*, 2019. (Extended: arXiv:2402.01359)
- **Link:** https://www.usenix.org/conference/usenixsecurity19/presentation/pendlebury · https://arxiv.org/abs/2402.01359
- **Tóm tắt:** Chứng minh F1 ~0.99 của nhiều hệ malware ML là ảo do 2 bias: **spatial bias** (phân bố lớp train/test không giống thực tế) và **temporal bias** (split ngẫu nhiên cho phép "học từ tương lai"); đề xuất ràng buộc thiết kế thí nghiệm loại bỏ cả hai.
- **Kết quả chính:** cùng model, đánh giá đúng cách làm F1 rơi mạnh; đưa ra metric AUT đo robustness theo thời gian.
- **Trích dẫn nguyên văn** (abstract bản mở rộng arXiv:2402.01359, đã đối chiếu): *"This paper argues that commonly reported results are inflated due to two pervasive sources of experimental bias in the detection task: spatial bias caused by data distributions that are not representative of a real-world deployment; and temporal bias caused by incorrect time splits of data, leading to unrealistic configurations."*
- **Quyết định liên quan:** split grouped/temporal chống rò rỉ; cân nhắc tỉ lệ lớp — mục 4, 6 CLAUDE.md.
- **Vì sao phù hợp:** citation nền cho toàn bộ chương thiết kế thí nghiệm: biện minh vì sao đồ án không dùng random split mà dùng grouped split (biến thể/họ không vắt qua train/test), và vì sao báo cáo P/R/F1/ROC-AUC thay vì chỉ accuracy trên tập cân bằng nhân tạo.

### 4.2. Dos and Don'ts of Machine Learning in Computer Security (Arp et al., 2022, USENIX Security — Distinguished Paper)
- **Citation:** D. Arp, E. Quiring, F. Pendlebury, A. Warnecke, F. Pierazzi, C. Wressnegger, L. Cavallaro, K. Rieck, "Dos and Don'ts of Machine Learning in Computer Security," *31st USENIX Security Symposium*, 2022.
- **Link:** https://www.usenix.org/conference/usenixsecurity22/presentation/arp · https://dodo-mlsec.org/
- **Tóm tắt:** Hệ thống hóa 10 pitfall của ML trong security: **sampling bias** (nguồn dữ liệu khác nhau giữa lớp), label inaccuracy, data snooping, spurious correlation (model học "nguồn" thay vì "tính độc hại"), metric không phù hợp, base-rate fallacy...; khảo sát cho thấy đa số paper security dính ≥1 pitfall.
- **Kết quả chính:** case study chứng minh model có accuracy cao nhưng học artifact của dataset; checklist khuyến nghị cho từng pitfall.
- **Quyết định liên quan:** "benign phải đa dạng nguồn để chống thiên lệch nguồn" (mục 2 CLAUDE.md); dedup SHA-256; kiểm tra bias nguồn (mục 7).
- **Vì sao phù hợp:** đúng nguy cơ lớn nhất của đồ án: benign từ Win10/figshare vs malware từ MalwareBazaar/RAT — nếu không đa dạng hóa và kiểm tra, model học "nguồn dữ liệu". Paper này cho tên gọi, khung phân tích và cách kiểm tra (ví dụ: train trên nguồn này test nguồn kia). Trích trong phần thiết kế dataset + threats to validity.

### 4.3. AVClass2: Massive Malware Tag Extraction from AV Labels (Sebastián & Caballero, 2020, ACSAC)
- **Citation:** S. Sebastián, J. Caballero, "AVClass2: Massive Malware Tag Extraction from AV Labels," *Proc. ACSAC 2020*. arXiv:2006.10615.
- **Link:** https://doi.org/10.1145/3427228.3427261 · https://arxiv.org/abs/2006.10615 · Code: https://github.com/malicialab/avclass
- **Tóm tắt:** Công cụ chuẩn hóa nhãn họ malware từ nhãn AV hỗn loạn (VirusTotal): trích tag họ/hành vi/thuộc tính file sạch từ nhãn của hàng chục AV engine, giải quyết alias và token rác.
- **Kết quả chính:** đánh giá trên hàng triệu mẫu; trở thành công cụ cộng đồng mặc định cho gán nhãn họ quy mô lớn (AVClass và AVClass2 nay gộp chung codebase).
- **Quyết định liên quan:** pipeline gán nhãn "VirusTotal verify · AVClass2 chuẩn hóa họ" (mục 4 CLAUDE.md); bảng tra family→behavior (nhánh phụ).
- **Vì sao phù hợp:** biện minh trực tiếp cho lựa chọn công cụ: nhãn `signature` của MalwareBazaar và nhãn AV thô không nhất quán giữa engine; AVClass2 là chuẩn được cộng đồng chấp nhận để quy về một tên họ duy nhất — điều kiện tiên quyết cho grouped split theo họ và cho nhánh phân loại họ.

### 4.4. On the impact of dataset size and class imbalance in evaluating ML-based Windows malware detection (Dambra et al., 2022)
- **Citation:** S. Dambra et al., "On the impact of dataset size and class imbalance in evaluating machine-learning-based windows malware detection techniques," arXiv:2206.06256, 2022.
- **Link:** https://arxiv.org/abs/2206.06256
- **Tóm tắt:** Nghiên cứu thực nghiệm ảnh hưởng của kích thước dataset và tỉ lệ malware:benign lên kết quả đánh giá detector Windows; so sánh tỉ lệ từ cân bằng đến giống in-the-wild.
- **Kết quả chính:** tỉ lệ lớp trong test ảnh hưởng mạnh precision/FPR; tập cân bằng nhân tạo + metric accuracy không phản ánh triển khai thực. *(Lưu ý: con số ngưỡng "1:8" lưu truyền trong văn liệu thứ cấp — khi trích trong báo cáo phải kiểm tra lại đúng trang trong bản PDF.)*
- **Trích dẫn nguyên văn** (abstract, đã đối chiếu): *"Researchers also tend to use balanced datasets and accuracy as a metric for testing. The former is not a true representation of reality, where benign samples significantly outnumber malware, and the latter … is known to be problematic for imbalanced problems."* và *"…high accuracy scores don't necessarily translate to high real-world performance."*
- **Quyết định liên quan:** tập detection 1.5:1 (`detect_subset.csv`); báo cáo đầy đủ P/R/F1/ROC-AUC — mục 2, 3 CLAUDE.md.
- **Vì sao phù hợp:** cho phép biện luận trung thực về tỉ lệ 1.5:1: đây là lựa chọn thực dụng do benign khan hiếm (cap malware xuống thay vì bỏ benign), không phải mô phỏng in-the-wild; theo paper này, cần nêu rõ hạn chế rằng precision đo được sẽ lạc quan hơn triển khai thực — ghi vào threats to validity, và ưu tiên ROC-AUC (ít nhạy tỉ lệ lớp).

### 4.5. BODMAS: An Open Dataset for Learning-based Temporal Analysis of PE Malware (Yang et al., 2021, DLS)
- **Citation:** L. Yang, A. Ciptadi, I. Laziuk, A. Ahmadzadeh, G. Wang, "BODMAS: An Open Dataset for Learning based Temporal Analysis of PE Malware," *IEEE S&P Workshops (DLS)*, 2021.
- **Link:** https://gangw.cs.illinois.edu/DLS21_BODMAS.pdf
- **Tóm tắt:** Dataset 57,293 malware (PE thô) + 77,142 benign (feature) thu trong 1 năm, có timestamp và nhãn họ (581 họ) đã curate — thiết kế cho nghiên cứu temporal/concept drift.
- **Kết quả chính:** minh họa concept drift trên detector thực; cung cấp quy trình gán nhãn họ đáng tin cậy.
- **Quyết định liên quan:** mục 3 CLAUDE.md (EMBER/BODMAS là feature-based); thiết kế labels.csv với nhãn họ + nguồn.
- **Vì sao phù hợp:** cùng với EMBER, chứng minh khoảng trống mà đồ án lấp: dataset detection công khai không phân phối **bytes benign** (bản quyền) → buộc tự thu benign; quy trình metadata (SHA-256, timestamp, family, source) của labels.csv mô phỏng thực hành tốt của BODMAS.

### 4.6. MalConv: Malware Detection by Eating a Whole EXE (Raff et al., 2018, AAAI Workshop)
- **Citation:** E. Raff, J. Barker, J. Sylvester, R. Brandon, B. Catanzaro, C. Nicholas, "Malware Detection by Eating a Whole EXE," *AAAI-18 Workshop on AI for Cyber Security*. arXiv:1710.09435.
- **Link:** https://arxiv.org/abs/1710.09435 · PDF: https://cdn.aaai.org/ocs/ws/ws0432/16422-75958-1-PB.pdf
- **Tóm tắt:** Mạng neural đầu tiên học trực tiếp từ **chuỗi byte thô của toàn bộ file PE** (không đặc trưng thủ công, không disassembly); vì ràng buộc bộ nhớ, đầu vào bị **cắt/pad về 2MB đầu file** (~2 triệu byte).
- **Kết quả chính:** chứng minh học từ byte thô khả thi ở quy mô lớn; chuẩn hóa thực hành "đọc N byte đầu file" khi file quá lớn — vùng đầu file chứa header/code là nơi giàu tín hiệu nhất.
- **Quyết định liên quan:** "đọc tối đa 30 MB/file, giữ phần đầu file — nơi tập trung header/code" (`docs/DATASET_PIPELINE.md` §3.3, CLAUDE.md mục 3).
- **Vì sao phù hợp:** là tiền lệ trực tiếp cho quyết định cắt file: MalConv cắt ở 2MB mà vẫn đạt hiệu năng tốt → ngưỡng 30MB của đồ án (chỉ ảnh hưởng ~185 file) là bảo thủ hơn nhiều, dễ bảo vệ. Đồng thời củng cố triết lý chung "byte thô đủ giàu tín hiệu, không cần disassembly" của toàn đề tài.

### 4.7. Measuring and Modeling the Label Dynamics of Online Anti-Malware Engines (Zhu et al., 2020, USENIX Security)
- **Citation:** S. Zhu, J. Shi, L. Yang, B. Qin, Z. Zhang, L. Song, G. Wang, "Measuring and Modeling the Label Dynamics of Online Anti-Malware Engines," *29th USENIX Security Symposium*, 2020.
- **Link:** https://www.usenix.org/conference/usenixsecurity20/presentation/zhu
- **Tóm tắt:** Theo dõi nhãn VirusTotal của 14,000+ file trên 65 engine trong suốt một năm: nhãn dao động theo thời gian ("hazard flips"), một số engine tương quan mạnh (không độc lập), engine "uy tín" chọn tay không phải lúc nào cũng tốt.
- **Kết quả chính:** xác nhận lợi ích của **ngưỡng số engine (threshold-based aggregation)** trong việc ổn định nhãn, đồng thời cảnh báo hệ quả của ngưỡng chọn kém; khuyến nghị chờ nhãn "chín" (mẫu mới cần thời gian để các engine cập nhật).
- **Quyết định liên quan:** quy tắc VirusTotal trong `docs/DATA_COLLECTION.md` §6: ≥5 engine → `confirmed_malware`; benign >2 engine detect → loại.
- **Vì sao phù hợp:** cho cơ sở học thuật rằng **cách tiếp cận ngưỡng-nhiều-engine là đúng phương pháp** (thay vì tin một engine); ngưỡng cụ thể 5 của đồ án nằm trong dải thông dụng của văn liệu (2–15). Trích khi mô tả pipeline gán nhãn + ghi threats to validity về nhãn dao động (mẫu RAT cũ đã ổn định nhãn — một điểm cộng).

### 4.8. Cơ sở tin cậy file hệ thống Windows từ máy ảo sạch làm benign
- **Citation:**
  - S. Dambra, Y. Han, S. Aonzo, P. Kotzias, A. Vitale, J. Caballero, D. Balzarotti, L. Bilge, "Decoding the Secrets of Machine Learning in Malware Classification: A Deep Dive into Datasets, Feature Extraction, and Model Performance," *ACM CCS 2023*. arXiv:2307.14657.
  - NIST, "National Software Reference Library (NSRL)" — Reference Data Set (RDS).
  - D. Kim, B. J. Kwon, T. Dumitraş, "Certified Malware: Measuring Breaches of Trust in the Windows Code-Signing PKI," *ACM CCS 2017*. (đối trọng)
  - O. Kargarnovin et al., "Mal2GCN: A Robust Malware Detection Approach…," arXiv:2108.12473. (đối trọng về bias)
- **Link:** https://arxiv.org/abs/2307.14657 · https://www.nist.gov/itl/ssd/software-quality-group/national-software-reference-library-nsrl · https://userlab.utk.edu/files/papers/kim/2017/kim2017certified.pdf · https://arxiv.org/abs/2108.12473
- **Tóm tắt & vì sao đây là thực hành chuẩn:**
  1. **Thực hành phổ biến trong văn liệu:** vì bytes benign không được phân phối công khai (bản quyền — EMBER/BODMAS chỉ phát feature), nhiều nghiên cứu xây tập benign từ **cài đặt Windows sạch/mặc định**. Dambra et al. (CCS 2023) tự xây benign bằng máy sạch Windows 10 + cài package Chocolatey rồi thu mọi file thực thi; các nghiên cứu khác thu executables từ cấu hình mặc định Windows XP→10 với giả định "software do Microsoft cung cấp trong bản cài mặc định là benign".
  2. **Chuỗi tin cậy kỹ thuật:** VM cài từ ISO chính thức → file trong System32/SysWOW64/WinSxS do Microsoft phát hành, có **chữ ký số Authenticode**; VM snapshot sạch, không cài phần mềm lạ → không có đường lây nhiễm.
  3. **Chuẩn forensic:** NIST **NSRL RDS** — cơ sở dữ liệu hash file "known" của phần mềm thương mại (gồm file hệ điều hành) — được pháp y máy tính dùng làm bộ lọc "known files" hàng chục năm; file hệ thống Windows chuẩn thuộc đúng nhóm này. *(Caveat của chính NIST: RDS đánh dấu "known", không phải "known good" tuyệt đối.)*
  4. **Lớp xác minh của đồ án (không tin mù):** mọi benign đều qua VirusTotal (`DATA_COLLECTION.md` §6 — >2 engine detect → loại), tức không dựa duy nhất vào nguồn gốc.
- **Đối trọng phải ghi nhận (threats to validity):**
  - **Kim et al. 2017:** tồn tại malware ký số hợp lệ — chữ ký/nguồn gốc Microsoft không phải bảo chứng tuyệt đối → lớp VirusTotal ở (4) là cần thiết.
  - **Mal2GCN (nguyên văn):** benign chỉ từ Windows sạch làm model *"overfitted on specific features that only exist in system executables… looking for simple Windows-related features such as existence of 'Microsoft' strings to label a file as benign"* → đây chính là lý do đồ án **đa dạng hóa 11 nguồn benign** (figshare, Program Files host, Sysinternals, NirSoft, Notepad++, PuTTY…) chứ không chỉ System32, khớp khung sampling bias của Arp 2022 (mục 4.2).
- **Quyết định liên quan:** nguồn benign Win10 VM (System32/SysWOW64/WinSxS) trong `DATA_COLLECTION.md` §4.2; nguyên tắc "benign đa dạng nguồn" (CLAUDE.md mục 2).
- **Vì sao phù hợp:** trả lời trực diện câu hỏi phản biện "lấy gì đảm bảo benign của bạn sạch?" — bằng 4 lớp: thực hành chuẩn văn liệu + chuỗi tin cậy cài đặt + chuẩn forensic NSRL + xác minh VirusTotal, kèm 2 đối trọng đã được giảm thiểu bằng thiết kế (đa nguồn + kiểm tra bias nguồn S6.2).

---

## 5. Model & XAI

### 5.1. Bộ ba kiến trúc gốc: VGG16 / ResNet50 / DenseNet121
- **Citation:**
  - K. Simonyan, A. Zisserman, "Very Deep Convolutional Networks for Large-Scale Image Recognition," *ICLR 2015*. arXiv:1409.1556.
  - K. He, X. Zhang, S. Ren, J. Sun, "Deep Residual Learning for Image Recognition," *CVPR 2016*. arXiv:1512.03385.
  - G. Huang, Z. Liu, L. van der Maaten, K. Q. Weinberger, "Densely Connected Convolutional Networks," *CVPR 2017*. arXiv:1608.06993.
- **Link:** https://arxiv.org/abs/1409.1556 · https://arxiv.org/abs/1512.03385 · https://arxiv.org/abs/1608.06993
- **Tóm tắt:** Ba mốc kiến trúc CNN: VGG (stack conv 3×3 sâu), ResNet (skip connection giải quyết degradation), DenseNet (dense connectivity, tái sử dụng feature, ít tham số hơn).
- **Kết quả chính:** lần lượt là SOTA ImageNet các năm 2014–2017; là backbone phổ biến nhất trong văn liệu malware-image (xem 5.2, 5.3).
- **Quyết định liên quan:** lựa chọn model (mục 3 CLAUDE.md).
- **Vì sao phù hợp:** citation gốc bắt buộc khi dùng kiến trúc; bộ ba đại diện 3 thế hệ thiết kế CNN khác nhau → so sánh có ý nghĩa kiến trúc chứ không chỉ "nhiều model".

### 5.2. IMCEC: Image-Based Malware Classification using Ensemble of CNN Architectures (Vasan et al., 2020, Computers & Security)
- **Citation:** D. Vasan, M. Alazab, S. Wassan, B. Safaei, Q. Zheng, "Image-Based malware classification using ensemble of CNN architectures (IMCEC)," *Computers & Security*, 92, 101748, 2020.
- **Link:** https://doi.org/10.1016/j.cose.2020.101748
- **Tóm tắt:** Fine-tune VGG16 + ResNet50 pretrained ImageNet trên ảnh malware, ensemble đặc trưng qua SVM; đánh giá cả mẫu packed/unpacked.
- **Kết quả chính:** >99% accuracy (unpacked), >98% (packed) trên Malimg; suy luận ~1.18s/mẫu; chứng minh transfer learning ImageNet→malware hiệu quả dù khác domain hoàn toàn.
- **Quyết định liên quan:** transfer learning pretrained ImageNet với `in_chans=3`; chọn VGG16/ResNet50 (mục 3 CLAUDE.md).
- **Vì sao phù hợp:** tiền lệ mạnh nhất cho chiến lược model của đồ án: đặc trưng texture ImageNet chuyển giao tốt sang texture ảnh byte, đặc biệt khi dataset không khổng lồ (~14.5k mẫu detection). Cũng cho thấy VGG16/ResNet50 là baseline chuẩn văn liệu → kết quả đồ án so sánh được với các nghiên cứu khác.

### 5.3. Visualized Malware Multi-Classification Framework Using Fine-Tuned CNN-Based Transfer Learning Models (El-Shafai et al., 2021, Applied Sciences)
- **Citation:** W. El-Shafai, I. Almomani, A. AlKhayer, "Visualized Malware Multi-Classification Framework Using Fine-Tuned CNN-Based Transfer Learning Models," *Applied Sciences*, 11(14), 6446, 2021.
- **Link:** https://www.mdpi.com/2076-3417/11/14/6446
- **Tóm tắt:** So sánh có hệ thống 6 model pretrained (trong đó có VGG16, ResNet50, DenseNet201...) fine-tune trên ảnh malware Malimg.
- **Kết quả chính:** VGG16 fine-tuned đạt 99.97% trên Malimg; họ CNN pretrained đều >99%, khác biệt giữa kiến trúc nhỏ nhưng nhất quán.
- **Quyết định liên quan:** so sánh ≥4 model là tiêu chí thành công (mục 7 CLAUDE.md).
- **Vì sao phù hợp:** khuôn mẫu (template) cho thí nghiệm so sánh model của đồ án; đồng thời là minh chứng vì sao cần multi-seed + kiểm định (5.3 và các paper cùng loại chỉ chạy 1 run — khác biệt 0.1–0.5% giữa model không thể kết luận nếu thiếu thống kê, xem 3.4).

### 5.4. A ConvNet for the 2020s — ConvNeXt (Liu et al., 2022, CVPR)
- **Citation:** Z. Liu, H. Mao, C.-Y. Wu, C. Feichtenhofer, T. Darrell, S. Xie, "A ConvNet for the 2020s," *CVPR 2022*. arXiv:2201.03545.
- **Link:** https://arxiv.org/abs/2201.03545
- **Tóm tắt:** Hiện đại hóa ResNet theo các bài học thiết kế của Vision Transformer (patchify stem, depthwise conv 7×7, LayerNorm, GELU...) — thuần convolution nhưng đạt/ vượt Swin Transformer.
- **Kết quả chính:** ConvNeXt-Tiny ~82.1% top-1 ImageNet với 28M tham số; giữ tính chất "đổi input size là chạy" của CNN (không cần nội suy positional embedding như ViT).
- **Quyết định liên quan:** chọn ConvNeXt-Tiny (timm) làm đại diện CNN hiện đại; thuận lợi cho sweep 224/336/448 (mục 3 CLAUDE.md).
- **Vì sao phù hợp:** hai lý do: (1) phủ trục thời gian kiến trúc 2014→2022 trong so sánh model; (2) tính linh hoạt input size của CNN là lý do kỹ thuật khiến sweep độ phân giải (luận điểm B) rẻ và sạch — ViT/Swin phải nội suy pos-embedding, thêm biến nhiễu. Các nghiên cứu 2024–2025 (hybrid ConvNeXt-Swin trên Malimg/MaleVis) xác nhận ConvNeXt-Tiny hoạt động tốt trên ảnh malware.

### 5.5. Grad-CAM (Selvaraju et al., 2017, ICCV) & HiResCAM (Draelos & Carin, 2020)
- **Citation:**
  - R. R. Selvaraju, M. Cogswell, A. Das, R. Vedantam, D. Parikh, D. Batra, "Grad-CAM: Visual Explanations from Deep Networks via Gradient-Based Localization," *ICCV 2017*.
  - R. L. Draelos, L. Carin, "Use HiResCAM instead of Grad-CAM for faithful explanations of convolutional neural networks," arXiv:2011.08891, 2020.
- **Link:** https://arxiv.org/abs/1610.02391 · https://arxiv.org/abs/2011.08891
- **Tóm tắt:** Grad-CAM: heatmap vùng ảnh quan trọng cho dự đoán từ gradient của lớp conv cuối, không cần sửa kiến trúc. HiResCAM: chỉ ra bước average-gradient của Grad-CAM có thể highlight vùng model **không** dùng; sửa bằng element-wise product, đảm bảo faithful (chính xác với kiến trúc 1 lớp FC cuối).
- **Kết quả chính:** Grad-CAM là chuẩn de-facto XAI cho CNN; HiResCAM chứng minh toán học tính faithful hơn trên ảnh y tế độ phân giải cao.
- **Quyết định liên quan:** hướng nâng cao XAI "Grad-CAM/HiResCAM trên model tốt nhất" (mục 3 CLAUDE.md).
- **Vì sao phù hợp:** với ảnh malware, heatmap trỏ về **offset byte cụ thể** trong file PE (nhờ layout row-major của đồ án) → có thể đối chiếu vùng nóng với section header/packed region/string table, biến XAI thành phân tích forensic. HiResCAM đáng dùng vì ảnh byte có cấu trúc vị trí chặt — highlight sai vùng là sai ngữ nghĩa nghiêm trọng. Các nghiên cứu 2025 (vd. "Through the Static: Demystifying Malware Visualization via Explainability", arXiv:2503.02441; SHAP/LIME/Grad-CAM trên ảnh malware, PMC12118971) xác nhận hướng này đang là chuẩn mới.

### 5.6. Vì sao ResNet50 (không phải DenseNet121) làm backbone tham chiếu cho lưới ablation (Thí nghiệm A)
- **Citation:**
  - R. Wightman, H. Touvron, H. Jégou, "ResNet strikes back: An improved training procedure in timm," *NeurIPS 2021 Workshop (ImageNet PPF)*. arXiv:2110.00476.
  - G. Pleiss, D. Chen, G. Huang, T. Li, L. van der Maaten, K. Q. Weinberger, "Memory-Efficient Implementation of DenseNets," arXiv:1707.06990, 2017.
- **Link:** https://arxiv.org/abs/2110.00476 · https://arxiv.org/abs/1707.06990
- **Tóm tắt:** Wightman et al. (nhóm tác giả timm — đúng thư viện đồ án dùng) mở đầu bằng nhận định: ResNet do He et al. thiết kế **"vẫn là kiến trúc gold-standard trong rất nhiều công bố khoa học, thường đóng vai trò kiến trúc mặc định trong các nghiên cứu, hoặc làm baseline khi kiến trúc mới được đề xuất"** — và chọn đúng vanilla ResNet-50 làm đối tượng chuẩn hóa training recipe (đạt 80.4% top-1 ImageNet ở 224²). Pleiss et al. ghi nhận điểm yếu thực dụng của DenseNet: cài đặt naive có bộ nhớ feature map tăng **bình phương theo độ sâu** do phép concatenation, cần kỹ thuật shared-memory riêng để giảm về tuyến tính.
- **Kết quả chính:** ResNet-50 là mẫu số chung của các nghiên cứu ablation/benchmark (MLPerf dùng ResNet-50 làm bài chuẩn; các framework detection/segmentation mặc định backbone ResNet-50). Trong chính văn liệu malware-image: **Nie 2024 (1.4) chạy ablation width bằng ResNet50**, IMCEC (5.2) fine-tune ResNet50, MalFCS (2.3) trích đặc trưng bằng ResNet — kết quả ablation trên ResNet50 so sánh trực tiếp được với các nghiên cứu này.
- **Trích dẫn nguyên văn** (Wightman et al., abstract, đã đối chiếu): *"The influential Residual Networks designed by He et al. remain the gold-standard architecture in numerous scientific publications. They typically serve as the default architecture in studies, or as baselines when new architectures are proposed."*
- **Quyết định liên quan:** chọn model chạy lưới hợp nhất 5×3 (Thí nghiệm A) — `docs/EXPERIMENTS.md`.
- **Vì sao phù hợp:** lưới 5 kênh × 3 size × ≥3 seed = 45 run/model, nên chỉ chạy đủ lưới trên 1–2 backbone tham chiếu. ResNet50 thắng DenseNet121 ở vai trò này vì 3 lý do: (1) **tính so sánh cộng đồng** — ResNet50 là baseline mặc định của văn liệu (Wightman) và của chính các paper malware-image gần nhất (Nie 2024 dùng ResNet50 cho đúng dạng thí nghiệm ablation biểu diễn ảnh); DenseNet121 xuất hiện thưa hơn hẳn trong vai trò ablation backbone. (2) **Chi phí bộ nhớ** — lưới có ô 448²; DenseNet concatenation ngốn activation memory (Pleiss), bất lợi trên RTX 4060 8GB, trong khi ResNet50 ở 448² vẫn chạy được batch hợp lý + AMP. (3) **Tách bạch vai trò thí nghiệm** — DenseNet121 vẫn nằm trong so sánh ≥4 model ở cấu hình headline (mục 7 CLAUDE.md); nó chỉ không làm backbone của lưới ablation. Lưu ý trung thực: kết luận kênh/resolution từ ResNet50 cần một lưới thu gọn trên model thứ hai (vd ConvNeXt-Tiny) để chứng minh không phụ thuộc kiến trúc.

---

## 6. Bảng tra: quyết định → paper

| Quyết định trong CLAUDE.md | Paper cơ sở |
|---|---|
| Bytes → ảnh grayscale, width cố định, height thay đổi | 1.1 Nataraj 2011 |
| Width cố định (không theo file size) → texture đồng nhất | 1.5 Chaganti 2022 |
| Width là hyperparameter, chốt qua EDA | 1.4 Nie 2024 |
| Width = 448 = max(img_size) → chỉ downsample, không upsample | Hộp tổng hợp mục 1 · 3.1 Peters & Farhat |
| Không có benchmark ảnh detection chuẩn → phương pháp chặt | 1.2 Survey 2025 · 1.3 EMBER · 4.5 BODMAS |
| Kênh 2: entropy Shannon cửa sổ byte **liên tiếp** (256B) | 2.1 Lyda & Hamrock 2007 · 2.2 Gibert 2018 · 2.3 MalFCS 2020 |
| Kênh 3: tỉ lệ printable ASCII theo cửa sổ | 2.5 ICT Express 2022 · 1.3 EMBER · 2.4 HIT4Mal |
| Composite 3 kênh > đơn kênh (luận điểm A) + ablation | 2.4 HIT4Mal 2020 · 2.3 MalFCS 2020 |
| 224² đủ tốt, rẻ hơn (luận điểm B / H1) | 3.2 Rukundo · 3.3 thực nghiệm in-domain |
| Trade-off resize mất thông tin (đối trọng H1, lưu native) | 3.1 Peters & Farhat 2023 |
| ≥3 seed + mean±std + kiểm định thống kê | 3.4 Bouthillier 2021 |
| Bộ seed {42,123,2026}: chọn trước, tùy ý, cố định, công bố | 3.5 Picard 2021 · Pineau 2021 |
| Grouped/temporal split chống rò rỉ | 4.1 TESSERACT 2019 |
| Benign đa nguồn, chống bias nguồn, dedup | 4.2 Arp 2022 |
| VirusTotal + AVClass2 chuẩn hóa họ | 4.3 AVClass2 2020 |
| Ngưỡng số engine VirusTotal (≥5 malware, >2 loại benign) | 4.7 Zhu 2020 |
| Cắt file lớn, giữ 30 MB đầu (header/code) | 4.6 MalConv 2018 |
| Tin cậy file Windows từ VM sạch làm benign | 4.8 Dambra CCS 2023 · NSRL · Kim 2017 (đối trọng) |
| Cặp entropy + string là đặc trưng tĩnh mạnh | 2.6 Wojnowicz 2016 |
| Tỉ lệ 1.5:1 + hạn chế của nó + ưu tiên ROC-AUC | 4.4 Dambra 2022 |
| VGG16/ResNet50/DenseNet121 + transfer learning ImageNet | 5.1 gốc · 5.2 IMCEC · 5.3 El-Shafai 2021 |
| ConvNeXt-Tiny + CNN thuận sweep resolution | 5.4 Liu 2022 |
| ResNet50 làm backbone tham chiếu cho lưới ablation | 5.6 Wightman 2021 · Pleiss 2017 · 1.4 Nie 2024 |
| XAI Grad-CAM/HiResCAM | 5.5 Selvaraju 2017 · Draelos 2020 |

## 7. Gap còn lại — quyết định CHƯA có cơ sở trích dẫn (rà soát toàn bộ .md, 2026-07-05)

| # | Quyết định (vị trí) | Trạng thái & việc cần làm |
|---|---|---|
| G1 | **Cửa sổ entropy/ASCII = 256 byte** (`DATASET_PIPELINE.md` §4.3: "kích thước mặc định, chỉnh được qua config") | Chưa có paper chốt 256. Văn liệu dùng đủ cỡ: EMBER dùng window 2048, một số nghiên cứu 1024/stride 256, Gibert 2018 dùng chunk nhỏ. **Cách vá rẻ nhất:** ablation nhỏ window ∈ {128, 256, 512, 1024} trên 1 seed, hoặc viết rõ "lựa chọn thực dụng: 256 byte ≈ 0.57 hàng ảnh width 448 → độ phân giải không gian của kênh xấp xỉ 1 hàng pixel". |
| G2 | **Kiểm định trong `reports/experimentA.md` dùng t-test ĐỘC LẬP**, trong khi `EXPERIMENTS.md` §6 quy định **paired t-test hoặc McNemar** | **Mâu thuẫn nội bộ.** Với cùng bộ seed {42,123,2026} chạy chung split, so sánh đúng là paired (theo cặp seed) — Bouthillier (3.4) và Dietterich 1998 ("Approximate Statistical Tests for Comparing Supervised Classification Learning Algorithms", Neural Computation 10(7)) là cơ sở. Nên tính lại paired t-test/Wilcoxon cho bảng §3 của experimentA (số liệu đã có sẵn theo seed trong phụ lục). |
| G3 | **AdamW + CosineAnnealing + early stopping** (experimentA §1) | Dễ vá: cite Loshchilov & Hutter — AdamW (*Decoupled Weight Decay Regularization*, ICLR 2019, arXiv:1711.05101) và SGDR/cosine (*SGDR: Stochastic Gradient Descent with Warm Restarts*, ICLR 2017, arXiv:1608.03983). |
| G4 | **Class weights tự động cho lệch lớp** (experimentA §1) | Thực hành chuẩn (cost-sensitive learning); có thể cite King & Zeng 2001 hoặc đơn giản là docs sklearn/PyTorch. Ưu tiên thấp. |
| G5 | **Ngưỡng bỏ file < 4 KB** (`DATASET_PIPELINE.md` §3.3) | Không có paper cho con số này; biện minh bằng chính EDA (44 file, ảnh < 10 hàng ở width 448 — không đủ texture). Ghi là quyết định thực nghiệm, không cần citation. |
| G6 | **Benign lấy từ máy host + VM Win10 có thể lệch phiên bản/không đa dạng nhà phát hành** (`DATA_COLLECTION.md` §4) | Đã có khung Arp 2022 (4.2, sampling bias); việc cần làm là **thí nghiệm kiểm tra**: train trên benign nguồn A test nguồn B (đã ghi trong BACKLOG S1.4 nhưng chưa thấy kết quả trong reports). |
| G7 | **Suy hành vi từ họ qua bảng tra family→behavior** (CLAUDE.md mục 2) | Chưa có citation. AVClass2 (4.3) chính là công cụ trích tag *behavior* từ nhãn AV — dùng luôn làm cơ sở; bổ sung khi làm nhánh phụ. |

## 8. Danh sách PDF nên tải về (nguồn chính thức — an toàn)

Tất cả link dưới đây là **domain chính thức của nhà xuất bản/hội nghị** (arxiv.org, usenix.org, aaai.org, vizsec.org) — chỉ chứa PDF văn bản, tải trực tiếp từ các domain này là an toàn. **Tránh** các bản mirror trên site lạ (pdf-drive, sci-hub mirror không rõ nguồn...).

| Paper | Link PDF chính thức |
|---|---|
| Nataraj 2011 | https://vizsec.org/files/2011/Nataraj.pdf |
| Nie 2024 (đã tải ✔) | https://arxiv.org/pdf/2406.03831 |
| Peters & Farhat 2023 | https://arxiv.org/pdf/2311.12760 |
| Bouthillier 2021 | https://arxiv.org/pdf/2103.03098 |
| TESSERACT (extended) | https://arxiv.org/pdf/2402.01359 |
| Arp 2022 (Dos and Don'ts) | https://www.usenix.org/system/files/sec22-arp.pdf |
| Zhu 2020 (VirusTotal) | https://www.usenix.org/system/files/sec20-zhu.pdf |
| AVClass2 | https://arxiv.org/pdf/2006.10615 |
| EMBER | https://arxiv.org/pdf/1804.04637 |
| Dambra 2022 (imbalance) | https://arxiv.org/pdf/2206.06256 |
| MalConv | https://arxiv.org/pdf/1710.09435 |
| Wojnowicz 2016 | https://arxiv.org/pdf/1607.04950 |
| Wightman 2021 (ResNet strikes back) | https://arxiv.org/pdf/2110.00476 |
| Pleiss 2017 (DenseNet memory) | https://arxiv.org/pdf/1707.06990 |
| ConvNeXt | https://arxiv.org/pdf/2201.03545 |
| Grad-CAM | https://arxiv.org/pdf/1610.02391 |
| HiResCAM | https://arxiv.org/pdf/2011.08891 |
| Survey visualization 2025 | https://arxiv.org/pdf/2505.07574 |
| BODMAS | https://gangw.cs.illinois.edu/DLS21_BODMAS.pdf |

Các paper sau **không có PDF mở** (paywall Elsevier/Wiley): Chaganti 2022 (JISA), HIT4Mal (ETT), MalFCS (JPDC), Lyda & Hamrock (IEEE S&P Mag), Gibert 2018 (AAAI — có bản trên trang tác giả). Truy cập qua thư viện trường hoặc bản preprint trên trang cá nhân tác giả/ResearchGate (kiểm tra đúng tên bài trước khi tải).

## Ghi chú khi viết báo cáo
- Các con số accuracy 99%+ trên Malimg/BIG2015 (2.3, 5.2, 5.3) cần trích kèm caveat: dataset family-classification, không có benign, có nguy cơ bias theo TESSERACT/Arp — không so trực tiếp với kết quả detection của đồ án.
- Link đã kiểm tra qua search 2026-07-03; DOI/arXiv là link ổn định, ưu tiên dùng trong báo cáo.
- Còn thiếu (research bổ sung nếu cần): paper riêng về augmentation cho ảnh malware; robustness FGSM (nếu làm nhánh tùy chọn); citation cho ngưỡng 4 KB/30 MB (hiện là quyết định thực dụng từ EDA, có thể biện minh bằng phân bố kích thước file trong labels.csv thay vì paper).
