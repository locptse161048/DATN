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
- **Quyết định liên quan:** toàn bộ thiết kế 3 kênh composite (gray + entropy + ASCII) — mục 3, 4 CLAUDE.md.
- **Vì sao phù hợp:** đây là tiền lệ trực tiếp nhất: chứng minh **kết hợp entropy + phân lớp ký tự trong ảnh màu tốt hơn ảnh đơn kênh**, và trên đúng bài toán detection benign-vs-malware như đồ án. Khác biệt của đồ án: giữ layout tuyến tính row-major thay vì Hilbert (giữ tương ứng trực tiếp pixel↔offset, thuận cho Grad-CAM), dùng ASCII-ratio liên tục thay vì class rời rạc, và có ablation từng kênh + so với gray×3 một cách hệ thống.

### 2.5. Evaluation of printable character-based malicious PE file-detection method (Otsubo et al., 2022, ICT Express)
- **Citation:** M. Mimura et al., "Evaluation of printable character-based malicious PE file-detection method," *ICT Express*, 8(2), 2022.
- **Link:** https://www.sciencedirect.com/science/article/pii/S2542660522000245
- **Tóm tắt:** Detection PE độc hại **chỉ từ ký tự in được** (printable characters) trong file: trích chuỗi printable → mô hình ngôn ngữ (Doc2vec) → classifier; đánh giá trên FFRI dataset 400k benign + 400k malware theo chuỗi thời gian 2019–2021.
- **Kết quả chính:** F1 = 0.981 với Doc2vec + MLP; token printable đặc thù có sức phân loại cao và giữ hiệu quả với malware mới.
- **Quyết định liên quan:** kênh 3 (tỉ lệ printable ASCII 0x20–0x7E theo cửa sổ) — mục 4 CLAUDE.md.
- **Vì sao phù hợp:** bằng chứng độc lập, quy mô lớn rằng **riêng thông tin ký tự in được đã đủ phát hiện malware với F1 rất cao** → mật độ/phân bố printable là tín hiệu mạnh, xứng đáng một kênh riêng. Đồ án dùng dạng tỉ lệ theo cửa sổ (giữ tính không gian, chỉ ra *vùng nào* nhiều text) thay vì NLP trên chuỗi — bổ trợ chứ không trùng lặp.

---

## 3. Luận điểm B: độ phân giải vs chi phí

### 3.1. High-resolution Image-based Malware Classification using Multiple Instance Learning (Peters & Farhat, 2023)
- **Citation:** T. Peters, H. Farhat, "High-resolution Image-based Malware Classification using Multiple Instance Learning," arXiv:2311.12760, 2023.
- **Link:** https://arxiv.org/abs/2311.12760 · Code: https://github.com/timppeters/MIL-Malware-Images
- **Tóm tắt:** Phân tích thực nghiệm cho thấy **resize ảnh malware về kích thước nhỏ gây mất thông tin then chốt** và có thể bị khai thác (binary enlargement attack); đề xuất giữ ảnh độ phân giải cao, chia patch + multiple instance learning với attention.
- **Kết quả chính:** trên BIG2015, MIL đạt 96.6% trên mẫu bị phóng to đối kháng, so với baseline resize chỉ 22.8%.
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
- **Quyết định liên quan:** yêu cầu "≥3 seed + mean±std + kiểm định thống kê" của luận điểm B (mục 3 CLAUDE.md).
- **Vì sao phù hợp:** là cơ sở phương pháp luận trực tiếp cho thiết kế thống kê của H1: khác biệt 224-vs-448 dự kiến nhỏ, nên nếu không multi-seed + kiểm định thì kết luận "xấp xỉ nhau" hay "nhỉnh hơn" đều vô nghĩa. Trích trong phần Experimental Setup.

---

## 4. Phương pháp luận thí nghiệm

### 4.1. TESSERACT: Eliminating Experimental Bias in Malware Classification across Space and Time (Pendlebury et al., 2019, USENIX Security)
- **Citation:** F. Pendlebury, F. Pierazzi, R. Jordaney, J. Kinder, L. Cavallaro, "TESSERACT: Eliminating Experimental Bias in Malware Classification across Space and Time," *28th USENIX Security Symposium*, 2019. (Extended: arXiv:2402.01359)
- **Link:** https://www.usenix.org/conference/usenixsecurity19/presentation/pendlebury · https://arxiv.org/abs/2402.01359
- **Tóm tắt:** Chứng minh F1 ~0.99 của nhiều hệ malware ML là ảo do 2 bias: **spatial bias** (phân bố lớp train/test không giống thực tế) và **temporal bias** (split ngẫu nhiên cho phép "học từ tương lai"); đề xuất ràng buộc thiết kế thí nghiệm loại bỏ cả hai.
- **Kết quả chính:** cùng model, đánh giá đúng cách làm F1 rơi mạnh; đưa ra metric AUT đo robustness theo thời gian.
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
- **Kết quả chính:** tỉ lệ lớp trong test ảnh hưởng mạnh precision/FPR; vượt qua ngưỡng ~1:8 (malware:benign) thì thêm benign không đổi kết quả đáng kể; tập cân bằng nhân tạo thổi phồng precision so với triển khai thực.
- **Quyết định liên quan:** tập detection 1.5:1 (`detect_subset.csv`); báo cáo đầy đủ P/R/F1/ROC-AUC — mục 2, 3 CLAUDE.md.
- **Vì sao phù hợp:** cho phép biện luận trung thực về tỉ lệ 1.5:1: đây là lựa chọn thực dụng do benign khan hiếm (cap malware xuống thay vì bỏ benign), không phải mô phỏng in-the-wild; theo paper này, cần nêu rõ hạn chế rằng precision đo được sẽ lạc quan hơn triển khai thực — ghi vào threats to validity, và ưu tiên ROC-AUC (ít nhạy tỉ lệ lớp).

### 4.5. BODMAS: An Open Dataset for Learning-based Temporal Analysis of PE Malware (Yang et al., 2021, DLS)
- **Citation:** L. Yang, A. Ciptadi, I. Laziuk, A. Ahmadzadeh, G. Wang, "BODMAS: An Open Dataset for Learning based Temporal Analysis of PE Malware," *IEEE S&P Workshops (DLS)*, 2021.
- **Link:** https://gangw.cs.illinois.edu/DLS21_BODMAS.pdf
- **Tóm tắt:** Dataset 57,293 malware (PE thô) + 77,142 benign (feature) thu trong 1 năm, có timestamp và nhãn họ (581 họ) đã curate — thiết kế cho nghiên cứu temporal/concept drift.
- **Kết quả chính:** minh họa concept drift trên detector thực; cung cấp quy trình gán nhãn họ đáng tin cậy.
- **Quyết định liên quan:** mục 3 CLAUDE.md (EMBER/BODMAS là feature-based); thiết kế labels.csv với nhãn họ + nguồn.
- **Vì sao phù hợp:** cùng với EMBER, chứng minh khoảng trống mà đồ án lấp: dataset detection công khai không phân phối **bytes benign** (bản quyền) → buộc tự thu benign; quy trình metadata (SHA-256, timestamp, family, source) của labels.csv mô phỏng thực hành tốt của BODMAS.

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

---

## 6. Bảng tra: quyết định → paper

| Quyết định trong CLAUDE.md | Paper cơ sở |
|---|---|
| Bytes → ảnh grayscale, width cố định, height thay đổi | 1.1 Nataraj 2011 |
| Không có benchmark ảnh detection chuẩn → phương pháp chặt | 1.2 Survey 2025 · 1.3 EMBER · 4.5 BODMAS |
| Kênh 2: entropy Shannon cửa sổ byte **liên tiếp** (256B) | 2.1 Lyda & Hamrock 2007 · 2.2 Gibert 2018 · 2.3 MalFCS 2020 |
| Kênh 3: tỉ lệ printable ASCII theo cửa sổ | 2.5 ICT Express 2022 · 1.3 EMBER · 2.4 HIT4Mal |
| Composite 3 kênh > đơn kênh (luận điểm A) + ablation | 2.4 HIT4Mal 2020 · 2.3 MalFCS 2020 |
| 224² đủ tốt, rẻ hơn (luận điểm B / H1) | 3.2 Rukundo · 3.3 thực nghiệm in-domain |
| Trade-off resize mất thông tin (đối trọng H1, lưu native) | 3.1 Peters & Farhat 2023 |
| ≥3 seed + mean±std + kiểm định thống kê | 3.4 Bouthillier 2021 |
| Grouped/temporal split chống rò rỉ | 4.1 TESSERACT 2019 |
| Benign đa nguồn, chống bias nguồn, dedup | 4.2 Arp 2022 |
| VirusTotal + AVClass2 chuẩn hóa họ | 4.3 AVClass2 2020 |
| Tỉ lệ 1.5:1 + hạn chế của nó + ưu tiên ROC-AUC | 4.4 Dambra 2022 |
| VGG16/ResNet50/DenseNet121 + transfer learning ImageNet | 5.1 gốc · 5.2 IMCEC · 5.3 El-Shafai 2021 |
| ConvNeXt-Tiny + CNN thuận sweep resolution | 5.4 Liu 2022 |
| XAI Grad-CAM/HiResCAM | 5.5 Selvaraju 2017 · Draelos 2020 |

## Ghi chú khi viết báo cáo
- Các con số accuracy 99%+ trên Malimg/BIG2015 (2.3, 5.2, 5.3) cần trích kèm caveat: dataset family-classification, không có benign, có nguy cơ bias theo TESSERACT/Arp — không so trực tiếp với kết quả detection của đồ án.
- Link đã kiểm tra qua search 2026-07-03; DOI/arXiv là link ổn định, ưu tiên dùng trong báo cáo.
- Còn thiếu (research bổ sung nếu cần): paper riêng về augmentation cho ảnh malware; robustness FGSM (nếu làm nhánh tùy chọn); citation cho ngưỡng 4 KB/30 MB (hiện là quyết định thực dụng từ EDA, có thể biện minh bằng phân bố kích thước file trong labels.csv thay vì paper).
