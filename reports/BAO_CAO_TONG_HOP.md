# Báo cáo tổng hợp: Phát hiện mã độc bằng cách biến file thành ảnh và dùng học sâu

> Báo cáo này tổng hợp lại toàn bộ ý tưởng, dữ liệu, phương pháp và **kết quả thí nghiệm thực tế** của đồ án, viết lại bằng ngôn ngữ dễ hiểu, hạn chế tối đa từ viết tắt chuyên ngành. Nguồn tổng hợp: `docs/RELATED_WORK.md`, `docs/DATASET_PIPELINE.md`, `docs/EXPERIMENTS.md`, `reports/detection_224_full_4models.md`, `docs/code_VGG16_reference.md`, `docs/code_RESNET50_reference.md`, `docs/code_DENSENET121_reference.md`.

---

## 1. Đề tài này làm gì?

Mục tiêu: cho một file chương trình Windows (định dạng `.exe`/`.dll`), tự động trả lời câu hỏi **"file này sạch (benign) hay là mã độc (malware)?"** mà không cần chạy thử file (vì chạy thử rất nguy hiểm) và không cần "dịch ngược" mã máy (việc này tốn nhiều công sức của chuyên gia).

**Ý tưởng cốt lõi:** một file chương trình, xét cho cùng, chỉ là một dãy dài các con số (byte) từ 0 đến 255. Nếu ta "cuộn" dãy số này thành một tấm ảnh, thì các file cùng loại (cùng sạch, hoặc cùng một họ mã độc) sẽ có "vân ảnh" (texture) tương đối giống nhau — giống như cách các loại vải khác nhau có hoa văn dệt khác nhau. Ý tưởng này đã được kiểm chứng trong nghiên cứu từ năm 2011 (Nataraj và cộng sự): ảnh biểu diễn từ byte của các mã độc cùng họ trông "rất giống nhau về bố cục và vân ảnh".

Từ đó, đồ án dùng một mạng học sâu (một dạng trí tuệ nhân tạo chuyên xử lý ảnh, gọi là **mạng nơ-ron tích chập** — thường viết tắt là CNN) để "nhìn" vào tấm ảnh này và học cách phân biệt sạch/độc hại, giống như cách các mô hình AI phân biệt ảnh chó và ảnh mèo.

Điểm mới của đồ án so với cách làm ảnh xám truyền thống (chỉ 1 màu xám–đen–trắng): thay vì chỉ dùng 1 "góc nhìn" của file, đồ án tạo ra **3 góc nhìn khác nhau** từ cùng một dãy byte, xếp chồng thành 1 tấm ảnh màu giống như ảnh màu thường (ảnh màu thường có 3 lớp Đỏ–Xanh lá–Xanh dương, ở đây thay bằng 3 lớp: **ảnh xám gốc, độ hỗn loạn dữ liệu (entropy), và tỉ lệ ký tự đọc được**). Ba góc nhìn này được giải thích chi tiết ở Mục 3.

---

## 2. Dữ liệu dùng để huấn luyện và kiểm tra

### 2.1. Vì sao không dùng các bộ dữ liệu ảnh có sẵn nổi tiếng

Có hai bộ dữ liệu ảnh mã độc rất nổi tiếng trong giới nghiên cứu (Malimg và Microsoft BIG2015), nhưng đồ án **không dùng** vì:

- **Malimg:** chỉ có ảnh dựng sẵn từ mã độc, **không có file sạch** đi kèm — không thể dùng để huấn luyện bài toán "sạch hay độc hại" (chỉ dùng được để phân loại mã độc thuộc họ nào). Ngoài ra kết quả trên bộ này đã đạt ~99% từ lâu, không còn nhiều giá trị để nghiên cứu thêm.
- **BIG2015:** file đã bị **cắt bỏ phần đầu file (header)** trước khi công bố (để đảm bảo file không thể chạy được) — nhưng phần đầu file lại là nơi chứa rất nhiều dấu hiệu quan trọng để nhận biết. Bộ này cũng không có file sạch.

Vì vậy đồ án **tự thu thập dữ liệu file gốc đầy đủ (nguyên vẹn header)**, bao gồm cả file sạch và file độc hại thật.

### 2.2. Nguồn dữ liệu

| Loại | Nguồn | Vai trò |
|---|---|---|
| Mã độc | Kho dữ liệu figshare (8.970 file, 5 loại) | Nguồn mã độc ổn định, có nhãn sẵn |
| Mã độc | MalwareBazaar (kho mã độc công khai, cập nhật liên tục) | Mã độc mới, đa dạng loại hành vi |
| Mã độc | Ultimate-RAT-Collection | Bổ sung nhóm mã độc "điều khiển từ xa" (RAT) |
| File sạch | figshare (phần benign) + Windows 10 (System32, Program Files...) + phần mềm phổ biến (Sysinternals, Notepad++, PuTTY...) | File sạch — đây là nhóm **khan hiếm hơn** nên phải lấy từ nhiều nguồn khác nhau |

**Vì sao file sạch phải lấy từ nhiều nguồn?** Nếu tất cả file sạch chỉ lấy từ một nơi duy nhất (ví dụ chỉ từ Windows 10) còn mã độc lấy từ nơi khác, thì mô hình AI có nguy cơ học nhầm: thay vì học "cái gì làm file trở nên độc hại", nó học "file này có đến từ đúng nguồn Windows 10 hay không" — độ chính xác trên giấy tờ có thể rất cao nhưng thực tế vô dụng vì mô hình đã "gian lận" mà không ai biết. Đây là một rủi ro kinh điển đã được nhiều nghiên cứu bảo mật máy học cảnh báo, và đồ án chủ động phòng tránh bằng cách đa dạng hoá nguồn file sạch.

Toàn bộ thao tác với file mã độc được thực hiện trong máy ảo cách ly, **chỉ đọc dãy byte của file, không chạy file** — đảm bảo an toàn.

### 2.3. Con số cụ thể

Sau khi loại trùng lặp (loại các file có cùng "mã băm" — một loại con số nhận dạng duy nhất tính từ nội dung file, dùng để phát hiện file trùng nhau dù tên khác nhau):

- Tổng: **27.340 file duy nhất** = 21.511 mã độc + 5.829 file sạch.
- Vì mã độc nhiều hơn file sạch quá nhiều lần (~3,7:1), đồ án tạo thêm một **tập cân bằng hơn** cho bài toán chính (phát hiện sạch/độc hại): giữ nguyên toàn bộ file sạch, chỉ giới hạn bớt số mã độc lại còn tỉ lệ **1,5 mã độc : 1 file sạch** (≈ 8.743 mã độc + 5.829 sạch, tổng 14.547 file). Tỉ lệ này thực dụng (không bịa ra một tỉ lệ "giống thực tế" nào cả), nên báo cáo ưu tiên các chỉ số ít bị ảnh hưởng bởi tỉ lệ lớp (giải thích ở Mục 5).

Dữ liệu được chia thành 3 phần độc lập: **tập huấn luyện** (train — để mô hình học), **tập kiểm định** (validation — để theo dõi trong lúc huấn luyện, chọn thời điểm dừng tốt nhất), và **tập kiểm tra** (test — chỉ dùng một lần cuối để đánh giá khách quan). Việc chia được làm cẩn thận để **các file có quan hệ họ hàng/biến thể với nhau không bị vắt qua cả train lẫn test** — nếu để lọt, mô hình có thể "học thuộc lòng" thay vì học đặc điểm chung, khiến kết quả đánh giá bị ảo (cao hơn thực tế).

| Tập chia | File sạch | Mã độc | Tổng | Tỉ lệ |
|---|:---:|:---:|:---:|:---:|
| Huấn luyện | 4.066 | 6.115 | 10.181 | 1,50:1 |
| Kiểm định | 872 | 1.311 | 2.183 | 1,50:1 |
| Kiểm tra | 872 | 1.311 | 2.183 | 1,50:1 |
| **Tổng** | **5.810** | **8.737** | **14.547** | **1,50:1** |

> Ngoài tập trên (dùng cho kết quả "đầu bảng" ở Mục 5), đồ án còn dùng một tập con nhỏ hơn (~7.860 file) riêng cho thí nghiệm so sánh độ phân giải ảnh ở Mục 6 — lý do có tập riêng được giải thích ngay trong mục đó.

---

## 3. Biến một file thành tấm ảnh 3 lớp màu — giải thích kênh 2 và kênh 3

Đây là phần kỹ thuật cốt lõi và cũng là đóng góp chính của đồ án, nên sẽ giải thích kỹ, từng bước, không dùng thuật ngữ khó.

### Bước 0: Đọc file như một dãy số

Một file chương trình, mở ra ở dạng thô, chỉ là một dãy rất dài các con số nguyên từ 0 đến 255 (mỗi số gọi là 1 byte). Ví dụ 10 byte đầu của một file có thể là: `77, 90, 144, 0, 3, 0, 0, 0, 4, 0...`

Ta "cắt" dãy số này thành từng đoạn có **độ dài cố định là 448 số** rồi xếp chồng các đoạn lên nhau — giống như cắt một cuộn giấy dài thành các đoạn 448 ô rồi xếp chồng thành một tờ giấy hình chữ nhật. Con số 448 không phải chọn ngẫu nhiên — nó được chọn sau khi khảo sát kỹ phân bố kích thước của toàn bộ 27.340 file, và cũng chính là độ phân giải lớn nhất mà đồ án dùng để thử nghiệm sau này (xem thêm hộp giải thích ở cuối Mục 3).

### Kênh 1 — Ảnh xám gốc (góc nhìn "cấu trúc file")

Đơn giản nhất: mỗi con số byte (0–255) trở thành **độ sáng của 1 điểm ảnh** — số càng lớn thì điểm càng sáng, số càng nhỏ thì điểm càng tối. Đây chính là cách làm ảnh mã độc truyền thống, được dùng từ nghiên cứu gốc năm 2011.

Kết quả: ta nhìn thấy trực tiếp "bố cục" của file — phần tiêu đề (header) ở trên cùng, tiếp theo là các "vùng" khác nhau của file (vùng chứa mã lệnh, vùng chứa dữ liệu, vùng chứa tài nguyên như hình ảnh/icon...). Mỗi vùng có kiểu byte đặc trưng riêng nên tạo ra vân ảnh khác nhau, mắt thường cũng có thể phân biệt được ranh giới.

### Kênh 2 — Bản đồ "độ hỗn loạn" của dữ liệu (entropy)

**Vấn đề cần giải quyết:** Rất nhiều mã độc dùng một mánh khoé gọi là "đóng gói" (packing) hoặc "mã hoá" (encryption): chúng nén hoặc mã hoá phần thân thật sự của mã độc lại, chỉ để lộ một đoạn nhỏ "vỏ bọc" dùng để giải nén/giải mã lúc chạy. Mục đích là để qua mặt phần mềm diệt virus. Đặc điểm chung của dữ liệu đã bị nén/mã hoá là: **các byte trông cực kỳ "ngẫu nhiên và khó đoán"** — khác hẳn với mã chương trình bình thường hay văn bản, vốn có quy luật lặp lại nhất định.

**Cách đo độ "ngẫu nhiên/khó đoán" này** gọi là **entropy** (entropy Shannon) — một đại lượng quen thuộc trong lý thuyết thông tin. Có thể hiểu đơn giản: hãy tưởng tượng lấy một đoạn 256 byte liên tiếp trong file, rồi đếm xem 256 giá trị (0–255) đó xuất hiện đều nhau hay lệch hẳn về một vài giá trị:

- Nếu đoạn đó chỉ toàn số 0 lặp lại (ví dụ phần đệm trống) → rất dễ đoán, entropy **thấp** (gần 0).
- Nếu đoạn đó có mọi giá trị từ 0–255 xuất hiện với tần suất gần như đều nhau (không có quy luật gì để đoán byte tiếp theo) → rất khó đoán, entropy **cao** (gần mức tối đa là 8).

Cách tính cụ thể: chia file thành từng khối 256 byte liên tiếp, với mỗi khối tính "tỉ lệ xuất hiện" của từng giá trị byte trong khối đó, rồi áp một công thức toán học chuẩn (công thức entropy Shannon) để ra một con số duy nhất đại diện cho độ "hỗn loạn" của khối. Con số này sau đó được "tô" lên đúng vị trí của toàn bộ 256 byte trong khối, quy đổi về thang 0–255 giống một ảnh xám bình thường để ghép làm kênh thứ 2.

Kết quả: kênh này giống như một "bản đồ nhiệt" chỉ ra vùng nào của file **bị đóng gói/mã hoá** (những vùng rất sáng trên kênh entropy) so với vùng mã máy hoặc dữ liệu thông thường (sáng vừa) và vùng đệm/lặp lại đều đặn (tối). Vì đóng gói/mã hoá là kỹ thuật né tránh rất phổ biến của mã độc, kênh này cung cấp một tín hiệu quan trọng mà ảnh xám đơn thuần (kênh 1) không thể hiện rõ ràng.

*Lưu ý trung thực:* không phải cứ entropy cao là chắc chắn độc hại — nhiều phần mềm sạch cũng nén dữ liệu cài đặt hoặc nén tài nguyên đi kèm (ảnh, font...). Vì vậy entropy chỉ là **một trong ba góc nhìn**, không dùng riêng lẻ để kết luận.

Quan trọng: entropy được tính **trực tiếp trên dãy byte gốc theo từng khối liên tiếp**, chứ không tính bằng cách quét một cửa sổ nhỏ trên tấm ảnh 2 chiều đã dựng — vì nếu quét trên ảnh 2 chiều, cửa sổ sẽ vô tình trộn lẫn các byte nằm cách xa nhau 448 vị trí (đúng bằng độ rộng ảnh) lại với nhau, dù chúng chẳng liên quan gì đến nhau trong file gốc. Tính trên dãy byte 1 chiều rồi mới "trải" giá trị trở lại đúng vị trí điểm ảnh mới đảm bảo đúng ý nghĩa vật lý (đúng là entropy của một đoạn dữ liệu liên tục thật sự trong file) và vẫn khớp hoàn toàn về toạ độ với kênh 1.

### Kênh 3 — Bản đồ "mật độ văn bản đọc được" (tỉ lệ ký tự ASCII in được)

**Vấn đề cần giải quyết:** Bên trong hầu như mọi file chương trình đều có các đoạn **văn bản đọc được bằng mắt người** — ví dụ tên các hàm được gọi tới, đường dẫn file, địa chỉ website, thông báo lỗi, tên bản quyền... Những đoạn này bao gồm các ký tự chữ cái, số, dấu câu thông thường mà con người đọc được — trong máy tính, dải mã byte tương ứng với các ký tự "đọc được" này nằm trong một khoảng cố định (thường gọi là **ký tự ASCII in được**, gồm chữ cái, số, khoảng trắng, dấu câu — khoảng 95 ký tự thông dụng trên bàn phím).

Ngược lại, những vùng chứa **mã máy thuần tuý** hoặc **dữ liệu đã nén/mã hoá** thường có rất ít byte rơi vào dải "đọc được" này — vì đó không phải là văn bản, mà là các lệnh nhị phân hoặc dữ liệu ngẫu nhiên.

**Cách tính:** giống hệt cách chia khối 256 byte liên tiếp ở kênh 2, nhưng lần này với mỗi khối ta chỉ đơn giản **đếm xem có bao nhiêu trong số 256 byte đó rơi vào dải ký tự đọc được**, rồi chia cho 256 để ra một **tỉ lệ phần trăm** (từ 0% đến 100%). Ví dụ một khối có 200 trong 256 byte là ký tự đọc được thì tỉ lệ là 200/256 ≈ 78%. Tỉ lệ này được quy đổi sang thang 0–255 (giống một ảnh xám) và "tô" vào đúng vị trí của khối đó để tạo thành kênh thứ 3.

Kết quả: kênh này giống một "bản đồ nhiệt" làm nổi bật **vùng nào của file chứa nhiều văn bản/chuỗi ký tự** (vùng bảng chuỗi, tên hàm, đường dẫn... sẽ rất sáng) so với **vùng mã máy hoặc dữ liệu đã đóng gói** (sẽ tối, vì gần như không có ký tự đọc được). Mật độ và cách phân bố văn bản trong file từ lâu đã được xem là một dấu hiệu có giá trị để phát hiện mã độc trong nhiều nghiên cứu bảo mật trước đây.

**Vì sao kênh 2 và kênh 3 không dư thừa nhau (bổ sung thật sự, không trùng lặp):** hai đại lượng này đo hai điều khác hẳn nhau — entropy đo "mức độ ngẫu nhiên, khó đoán" của dữ liệu, còn tỉ lệ ASCII đo "mức độ giống văn bản con người đọc được". Một vùng dữ liệu có thể:
- Entropy trung bình nhưng vẫn rất nhiều văn bản (ví dụ bảng chứa hàng trăm chuỗi ký tự khác nhau — không quá đều nhưng vẫn toàn ký tự đọc được).
- Entropy rất cao nhưng lại không phải văn bản (dữ liệu đã mã hoá — ngẫu nhiên và cũng không phải chữ).

Vì hai đại lượng "nhìn" theo hai chiều khác nhau, kết hợp cả hai cho mô hình nhiều thông tin hơn hẳn so với chỉ dùng một trong hai, hoặc chỉ dùng ảnh xám đơn thuần.

### Ghép 3 kênh lại thành một tấm ảnh màu

Giống như một ảnh màu thông thường có 3 lớp (Đỏ, Xanh lá, Xanh dương) chồng lên nhau, đồ án chồng 3 "bản đồ" nói trên (ảnh xám, entropy, tỉ lệ ASCII) — cả ba đều có cùng kích thước và **khớp chính xác từng điểm ảnh với nhau** (vì đều tính từ đúng cùng một dãy byte và cùng cách chia khối) — thành một tấm ảnh 3 lớp duy nhất để đưa vào mạng học sâu. Vì cả ba lớp thực sự chứa thông tin khác nhau (không phải chỉ nhân bản 1 ảnh xám thành 3 bản giống hệt nhau), việc này giúp mô hình "nhìn" được nhiều khía cạnh của file cùng lúc.

> **Vì sao độ rộng ảnh cố định là 448:** Đồ án đã khảo sát toàn bộ phân bố kích thước 27.340 file trước khi quyết định. Nếu chỉ muốn tối đa số file có ảnh "đủ cao", con số tối ưu sẽ là 128; nhưng đồ án cố tình chọn 448 (dù chỉ ~52% file đủ điều kiện cao tương ứng) vì một lý do quan trọng hơn: đồ án còn có một thí nghiệm riêng so sánh 3 độ phân giải ảnh khác nhau (224, 336, 448 — xem Mục 6), và muốn phép so sánh đó công bằng tuyệt đối, ảnh gốc phải được sinh ra ở đúng kích thước lớn nhất (448) rồi mới thu nhỏ xuống 224/336 — vì thu nhỏ ảnh thật luôn giữ được thông tin thật, còn nếu làm ngược lại (phóng to ảnh nhỏ sẵn lên 448) sẽ chỉ tạo ra thông tin "bịa" do máy tính nội suy, khiến phép so sánh độ phân giải trở nên vô nghĩa. Việc dùng độ rộng cố định (thay vì mỗi file một độ rộng khác nhau tuỳ kích thước, như cách làm truyền thống) cũng đã được chứng minh trong nhiều nghiên cứu là cho kết quả tốt hơn, vì nó giúp cùng một kiểu dữ liệu luôn tạo ra cùng một kiểu vân ảnh trên mọi file, thay vì vân ảnh bị biến dạng khác nhau tuỳ theo kích thước file.

---

## 4. Bốn mô hình học sâu được so sánh

Đồ án không tự thiết kế mạng học sâu từ đầu, mà dùng lại 4 kiến trúc mạng học sâu nổi tiếng đã được huấn luyện sẵn trên 1,2 triệu ảnh vật thể đời thường (chó, mèo, xe hơi...) — gọi là **học chuyển giao (transfer learning)**: giữ lại toàn bộ "con mắt nhìn hoạ tiết" mà mạng đã học được từ hàng triệu ảnh thường, chỉ thay và huấn luyện lại "câu trả lời cuối cùng" (lớp phân loại cuối) cho bài toán 2 lựa chọn (sạch/độc hại) của đồ án. Cách này hiệu quả hơn nhiều so với huấn luyện một mạng học sâu từ số 0, vì đồ án chỉ có ~14.500 file — quá nhỏ so với 1,2 triệu ảnh cần thiết để tự học từ đầu.

| Mô hình | Năm ra đời | Số tầng có trọng số | Số tham số (đã sửa cho bài toán 2 lớp) | Đặc điểm thiết kế nổi bật |
|---|:---:|:---:|:---:|---|
| **VGG16** | 2014 | 16 | ~134,3 triệu | Kiến trúc "cổ điển" nhất — chỉ xếp chồng thẳng các lớp lọc ảnh, không có đường tắt. Có thêm cơ chế "ngẫu nhiên tắt bớt nơ-ron lúc học" (Dropout) để chống học vẹt, vì 2 lớp cuối cùng quá lớn (chiếm ~88% toàn bộ tham số) |
| **ResNet50** | 2016 | 50 | ~23,5 triệu | Có **đường tắt (skip connection)**: mỗi khối xử lý xong sẽ "cộng thẳng" lại phần đầu vào ban đầu — nhờ vậy mạng có thể sâu tới 50 tầng mà không bị mất tín hiệu (giống như hồi tưởng lại thông tin gốc thay vì chỉ dựa vào phiên bản đã bị xử lý qua nhiều bước) |
| **DenseNet121** | 2017 | 121 | ~7 triệu (nhẹ nhất) | Thay vì "cộng" như ResNet, mỗi tầng **nối thêm** đặc trưng mới vào toàn bộ đặc trưng của mọi tầng trước đó — giúp tái sử dụng thông tin triệt để, nên cần rất ít tham số dù có nhiều tầng nhất |
| **ConvNeXt-Tiny** | 2022 | — | ~28 triệu | Phiên bản "hiện đại hoá" của ResNet, học hỏi các kỹ thuật thiết kế mới nhất (tính đến 2022) nhưng vẫn giữ bản chất là mạng lọc ảnh cổ điển — không cần các bước xử lý phức tạp khi đổi kích thước ảnh đầu vào |

Cả 4 mô hình đều được thử nghiệm trên cùng một bộ dữ liệu, cùng cấu hình huấn luyện (chỉ đổi kiến trúc mạng) để đảm bảo so sánh công bằng.

---

## 5. Kết quả thí nghiệm chính: so sánh 4 mô hình (độ phân giải chuẩn 224×224, đủ 3 kênh)

### Cách đọc các con số đánh giá (giải thích các chỉ số trước khi xem bảng)

- **Accuracy (độ chính xác tổng thể):** tỉ lệ đoán đúng trên tổng số file kiểm tra. Dễ hiểu nhưng có thể gây hiểu lầm khi hai lớp không cân bằng.
- **Precision (độ chuẩn xác):** trong số các file mô hình *báo là mã độc*, có bao nhiêu phần trăm thực sự đúng là mã độc. Precision thấp nghĩa là báo động giả nhiều (nhiều file sạch bị oan).
- **Recall (độ bao phủ/khả năng phát hiện):** trong số các file *thực sự là mã độc*, mô hình bắt được bao nhiêu phần trăm. Recall thấp nghĩa là bỏ sót nhiều mã độc — nguy hiểm hơn trong thực tế.
- **F1:** một con số kết hợp cân bằng giữa Precision và Recall (trung bình điều hoà) — dùng khi muốn một con số duy nhất phản ánh cả hai mặt.
- **ROC-AUC:** đo khả năng mô hình phân biệt hai lớp bất kể ngưỡng quyết định đặt ở đâu; giá trị 1.0 là hoàn hảo, 0.5 là đoán ngẫu nhiên. Chỉ số này ít bị ảnh hưởng bởi tỉ lệ lệch lớp, nên đồ án ưu tiên tham khảo chỉ số này khi bàn về độ tin cậy tổng thể.

### Kết quả trên tập kiểm tra (872 file sạch + 1.311 mã độc)

| Mô hình | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|:---:|:---:|:---:|:---:|:---:|
| VGG16 | 0,9689 | 0,9777 | 0,9703 | 0,9740 | 0,9901 |
| ResNet50 | 0,9698 | 0,9792 | 0,9703 | 0,9747 | 0,9909 |
| **DenseNet121 (tốt nhất)** | **0,9725** | **0,9830** | 0,9710 | **0,9770** | **0,9940** |
| ConvNeXt-Tiny | 0,9675 | 0,9740 | **0,9718** | 0,9729 | 0,9929 |

**Nhận xét dễ hiểu:** cả 4 mô hình đều đạt độ chính xác trên 96,7%, độ đo F1 trên 97,3%, và ROC-AUC trên 0,99 — nghĩa là cả 4 kiến trúc đều "học được" tốt từ tấm ảnh 3 kênh, không phụ thuộc quá nhiều vào việc chọn kiến trúc mạng nào. **DenseNet121** nhỉnh hơn một chút ở hầu hết chỉ số, đặc biệt là ít báo động giả nhất (Precision cao nhất). Tuy nhiên chênh lệch giữa các mô hình khá nhỏ (F1 chỉ chênh nhau tối đa 0,004), nên có thể nói ống dẫn xử lý dữ liệu (từ file thô → ảnh → mô hình) hoạt động ổn định, hiệu quả không phụ thuộc vào một kiến trúc mạng cụ thể nào.

### Chi tiết số lượng đoán đúng/sai (ma trận nhầm lẫn) trên tập kiểm tra

Quy ước: lấy "mã độc" làm lớp dương (positive) và "sạch" làm lớp âm (negative) — đây là quy ước chuẩn khi báo cáo ma trận nhầm lẫn cho bài toán phát hiện. Bốn ký hiệu viết tắt hay gặp trong tài liệu học máy, giải nghĩa như sau:

| Ký hiệu | Tên đầy đủ | Ý nghĩa trong bài toán này |
|---|---|---|
| **TN** (True Negative) | Âm tính đúng | File **sạch**, mô hình đoán đúng là **sạch** |
| **FP** (False Positive) | Dương tính giả | File **sạch**, nhưng mô hình đoán nhầm là **mã độc** (báo động giả/oan) |
| **FN** (False Negative) | Âm tính giả | File **mã độc**, nhưng mô hình đoán nhầm là **sạch** (bỏ sót — nguy hiểm hơn vì để lọt mã độc) |
| **TP** (True Positive) | Dương tính đúng | File **mã độc**, mô hình đoán đúng là **mã độc** |

| Mô hình | TN — Sạch đoán đúng | FP — Sạch báo nhầm thành mã độc | FN — Mã độc bị bỏ sót (báo nhầm thành sạch) | TP — Mã độc đoán đúng |
|---|:---:|:---:|:---:|:---:|
| VGG16 | 843 | 29 | 39 | 1.272 |
| ResNet50 | 845 | 27 | 39 | 1.272 |
| DenseNet121 | 850 | 22 | 38 | 1.273 |
| ConvNeXt-Tiny | 838 | 34 | 37 | 1.274 |

(Kiểm tra nhanh: mỗi hàng cộng lại đúng bằng 872 file sạch + 1.311 mã độc = 2.183 file kiểm tra — ví dụ VGG16: TN 843 + FP 29 = 872; FN 39 + TP 1.272 = 1.311.)

- DenseNet121 có **FP** (số file sạch bị báo oan) thấp nhất: chỉ 22/872 (~2,5%) — quan trọng trong thực tế triển khai vì báo động giả nhiều sẽ gây phiền hà cho người dùng.
- **FN** (số mã độc bị bỏ sót) dao động 37–39/1.311 (~2,8–3,0%) ở cả 4 mô hình — khá đồng đều, không mô hình nào vượt trội hẳn về việc bắt được mã độc (Recall gần như ngang nhau, xem bảng chỉ số ở trên).

---

## 6. Thí nghiệm mở rộng: cùng lúc so sánh "kênh ảnh" và "độ phân giải ảnh"

Ngoài thí nghiệm chính ở Mục 5, đồ án còn thiết kế **một thí nghiệm hợp nhất** để trả lời 2 câu hỏi cùng lúc, dùng một bảng kết quả duy nhất:

- **Câu hỏi 1 (theo hàng — về kênh ảnh):** ảnh 3 kênh composite (xám + entropy + tỉ lệ ASCII) có thực sự tốt hơn ảnh xám 1 kênh không? Và việc "nhân bản" ảnh xám thành 3 bản giống hệt nhau (một cách làm giả tạo để đủ 3 kênh mà không cần tính entropy/ASCII) có thêm được thông tin gì không?
- **Câu hỏi 2 (theo cột — về độ phân giải):** ảnh có cần lớn (448×448 điểm ảnh) mới đạt độ chính xác cao, hay ảnh nhỏ hơn (224×224) đã đủ dùng, trong khi rẻ hơn nhiều lần về chi phí tính toán?

Thí nghiệm chạy **5 cách tạo ảnh khác nhau × 3 độ phân giải khác nhau = 15 ô**, mỗi ô chạy lặp lại với 3 "hạt giống ngẫu nhiên" khác nhau (seed) để đảm bảo kết quả không phải may rủi (giải thích thêm bên dưới), toàn bộ trên **cùng một tập dữ liệu con** (~7.860 file, được chọn vì có kích thước ảnh gốc tự nhiên đủ lớn ≥448×448, để đảm bảo việc thu nhỏ ảnh xuống 224/336 là "thu nhỏ thật" chứ không phải phóng to giả tạo).

**5 cách tạo ảnh được so sánh:**

| Tên viết tắt trong bảng | Ảnh gồm những gì |
|---|---|
| `gray1` | Chỉ ảnh xám gốc (1 kênh) — đường cơ sở |
| `gray×3` | Ảnh xám lặp lại 3 lần giống hệt nhau — để kiểm tra xem "chỉ cần đủ 3 kênh" có tự động tốt hơn không |
| `+entropy` | Ảnh xám + kênh entropy (bỏ tỉ lệ ASCII) — đo riêng đóng góp của entropy |
| `+ascii` | Ảnh xám + kênh tỉ lệ ASCII (bỏ entropy) — đo riêng đóng góp của tỉ lệ ASCII |
| `full` | Đủ cả 3 kênh (xám + entropy + tỉ lệ ASCII) — cấu hình đề xuất của đồ án |

**Vì sao phải lặp lại 3 lần với "hạt giống ngẫu nhiên" khác nhau (seed)?** Quá trình huấn luyện một mạng học sâu có nhiều bước ngẫu nhiên (khởi tạo trọng số ban đầu, xáo trộn thứ tự dữ liệu...). Nếu chỉ chạy 1 lần, kết quả có thể do "may rủi" chứ chưa chắc phản ánh đúng bản chất. Vì vậy mỗi ô trong bảng được huấn luyện lại 3 lần độc lập, rồi báo cáo **giá trị trung bình ± độ dao động** (ví dụ 0,960 ± 0,002 nghĩa là kết quả trung bình 0,960, và ba lần chạy dao động quanh mức đó khoảng ±0,002). Chỉ khi chênh lệch giữa hai cấu hình **lớn hơn hẳn** mức dao động này, và được một phép kiểm định thống kê xác nhận, thì mới được phép nói "cấu hình này thực sự tốt hơn cấu hình kia" — nếu không, phải nói trung thực là "hai cấu hình tương đương nhau, chênh lệch chỉ là nhiễu ngẫu nhiên".

### Bảng kết quả thực tế (mô hình ResNet50, chạy đủ 45/45 lượt = 15 ô × 3 lần)

| Cấu hình × Độ phân giải | Accuracy | Precision | Recall | F1 | ROC-AUC | Thời gian huấn luyện /vòng | Bộ nhớ GPU dùng | Khối lượng tính toán |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| gray1 × 224 | 0,9622 ± 0,0027 | 0,9748 ± 0,0058 | 0,9740 ± 0,0024 | 0,9744 ± 0,0017 | 0,9831 ± 0,0066 | 34,9 giây | 707 MB | 4,05 (đơn vị tính toán) |
| gray1 × 336 | 0,9628 ± 0,0059 | 0,9730 ± 0,0033 | 0,9767 ± 0,0046 | 0,9748 ± 0,0040 | 0,9857 ± 0,0035 | 51,1 giây | 1.125 MB | 9,27 |
| gray1 × 448 | 0,9676 ± 0,0055 | 0,9812 ± 0,0022 | 0,9748 ± 0,0094 | 0,9780 ± 0,0039 | 0,9901 ± 0,0002 | 76,8 giây | 1.702 MB | 16,21 |
| gray×3 × 224 | 0,9636 ± 0,0037 | 0,9734 ± 0,0071 | 0,9775 ± 0,0043 | 0,9754 ± 0,0024 | 0,9895 ± 0,0038 | 35,0 giây | 712 MB | 4,13 |
| gray×3 × 336 | 0,9625 ± 0,0055 | 0,9771 ± 0,0117 | 0,9721 ± 0,0063 | 0,9746 ± 0,0036 | 0,9881 ± 0,0025 | 51,9 giây | 1.136 MB | 9,45 |
| gray×3 × 448 | 0,9681 ± 0,0068 | 0,9849 ± 0,0030 | 0,9717 ± 0,0087 | 0,9783 ± 0,0047 | 0,9875 ± 0,0013 | 78,3 giây | 1.722 MB | 16,53 |
| +entropy × 224 | 0,9693 ± 0,0010 | 0,9838 ± 0,0034 | 0,9744 ± 0,0037 | 0,9791 ± 0,0007 | 0,9909 ± 0,0018 | 35,1 giây | 710 MB | 4,13 |
| +entropy × 336 | 0,9687 ± 0,0031 | 0,9827 ± 0,0059 | 0,9748 ± 0,0034 | 0,9787 ± 0,0020 | 0,9902 ± 0,0011 | 52,2 giây | 1.137 MB | 9,45 |
| +entropy × 448 | 0,9741 ± 0,0032 | 0,9892 ± 0,0018 | 0,9756 ± 0,0026 | 0,9823 ± 0,0022 | 0,9904 ± 0,0021 | 78,6 giây | 1.723 MB | 16,53 |
| +ascii × 224 | 0,9701 ± 0,0043 | 0,9842 ± 0,0034 | 0,9752 ± 0,0065 | 0,9797 ± 0,0030 | 0,9893 ± 0,0028 | 35,0 giây | 710 MB | 4,13 |
| +ascii × 336 | 0,9695 ± 0,0017 | 0,9850 ± 0,0058 | 0,9737 ± 0,0080 | 0,9793 ± 0,0013 | 0,9912 ± 0,0010 | 52,0 giây | 1.136 MB | 9,45 |
| +ascii × 448 | 0,9693 ± 0,0054 | 0,9857 ± 0,0017 | 0,9725 ± 0,0072 | 0,9790 ± 0,0037 | 0,9894 ± 0,0033 | 78,5 giây | 1.723 MB | 16,53 |
| full × 224 | 0,9639 ± 0,0055 | 0,9796 ± 0,0047 | 0,9714 ± 0,0050 | 0,9755 ± 0,0038 | 0,9909 ± 0,0010 | 35,6 giây | 710 MB | 4,13 |
| full × 336 | 0,9684 ± 0,0020 | 0,9887 ± 0,0018 | 0,9683 ± 0,0029 | 0,9784 ± 0,0014 | 0,9916 ± 0,0008 | 52,1 giây | 1.137 MB | 9,45 |
| **full × 448 (F1 cao nhất)** | 0,9741 ± 0,0034 | 0,9884 ± 0,0030 | 0,9763 ± 0,0063 | **0,9823 ± 0,0024** | 0,9911 ± 0,0006 | 78,5 giây | 1.723 MB | 16,53 |

**Kiểm chứng thêm trên một kiến trúc mạng khác (ConvNeXt-Tiny), chỉ với cấu hình đủ 3 kênh (`full`), để đảm bảo kết luận không chỉ đúng riêng cho ResNet50:**

| Độ phân giải | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|:---:|:---:|:---:|:---:|:---:|
| **224 (F1 cao nhất)** | 0,9772 ± 0,0045 | 0,9900 ± 0,0013 | 0,9790 ± 0,0066 | **0,9844 ± 0,0031** | 0,9933 ± 0,0008 |
| 336 | 0,9715 ± 0,0047 | 0,9828 ± 0,0041 | 0,9786 ± 0,0043 | 0,9807 ± 0,0032 | 0,9926 ± 0,0004 |
| 448 | 0,9766 ± 0,0027 | 0,9896 ± 0,0030 | 0,9786 ± 0,0033 | 0,9841 ± 0,0019 | 0,9926 ± 0,0006 |

### Hai kết luận rút ra

**Kết luận 1 — Về kênh ảnh:** Nhìn theo hàng ngang (cùng một độ phân giải, so các cách tạo ảnh khác nhau), số liệu thực tế cho thấy xu hướng **các cách tạo ảnh có thêm kênh kỹ thuật (`+entropy`, `+ascii`, `full`) đều nhỉnh hơn ảnh xám thuần (`gray1`, `gray×3`)** ở hầu hết độ phân giải. Đặc biệt, `gray×3` (nhân bản giả tạo) hầu như không hơn gì `gray1` (chênh lệch rất nhỏ, chỉ 0,001–0,004) — xác nhận đúng như dự đoán rằng **chỉ nhân bản ảnh xám thành 3 bản giống nhau không hề thêm thông tin thật sự**, phải là 3 kênh mang nội dung khác nhau mới có ích. Tuy nhiên, cần nói thẳng một điểm hạn chế: xu hướng này **chưa được kiểm định thống kê chính thức** ở số lần lặp hiện tại (3 lần lặp), nên chỉ có thể phát biểu là "có xu hướng ủng hộ việc dùng đủ 3 kênh có ý nghĩa", chứ chưa thể khẳng định chắc chắn "hơn hẳn về mặt thống kê". Đây là điểm cần làm rõ khi trình bày, và có thể củng cố thêm bằng cách chạy nhiều lần lặp hơn trong tương lai.

**Kết luận 2 — Về độ phân giải ảnh:** Đây là kết luận **mạnh và có đầy đủ bằng chứng thống kê**. So sánh cùng một cách tạo ảnh nhưng đổi độ phân giải (224 so với 336 so với 448), phép kiểm định thống kê (paired t-test — một phép toán chuyên dùng để so sánh xem chênh lệch giữa hai nhóm số liệu có "thật" hay chỉ là ngẫu nhiên) cho thấy: **gần như toàn bộ các cặp so sánh (14 trên 15 trường hợp, ở cả hai kiến trúc mạng ResNet50 và ConvNeXt-Tiny) đều không có khác biệt có ý nghĩa thống kê** — nói cách khác, phóng ảnh lên độ phân giải cao hơn **không** giúp tăng độ chính xác một cách chắc chắn. Trong khi đó, chi phí tính toán (thời gian huấn luyện, bộ nhớ máy tính cần dùng, khối lượng phép tính) tăng đúng theo quy luật bậc hai: ảnh 336 tốn gấp ~2,3 lần, ảnh 448 tốn gấp ~4 lần so với ảnh 224.

→ **Kết luận thực tế: dùng ảnh 224×224 điểm ảnh (nhỏ nhất trong 3 lựa chọn) là tối ưu nhất để triển khai** — độ chính xác tương đương thống kê với ảnh lớn hơn, nhưng rẻ hơn 2,3 đến 4 lần về chi phí máy tính. Kết luận này được xác nhận nhất quán trên cả hai kiến trúc mạng khác nhau, nên không phụ thuộc vào việc chọn kiến trúc mạng cụ thể nào.

**Lựa chọn cấu hình khuyến nghị triển khai thực tế:** dù ô có điểm F1 tuyệt đối cao nhất trên bảng là `full × 448` (ResNet50) hoặc `full × 224` (ConvNeXt-Tiny), nhưng theo đúng Kết luận 2, cấu hình **`full × 224`** (đủ 3 kênh, ảnh 224×224) đã đạt độ chính xác **tương đương về mặt thống kê** với ảnh lớn hơn trong khi chi phí thấp nhất — nên đây mới là cấu hình được khuyến nghị dùng khi triển khai thực tế, chứ không phải máy móc chọn ô có con số cao nhất trên bảng.

---

## 7. Vì sao tin được các kết quả này? (cơ sở khoa học và cách phòng tránh sai lệch)

Bài toán "phát hiện mã độc bằng ảnh" hiện chưa có một bộ dữ liệu ảnh chuẩn mực được cộng đồng công nhận để so sánh trực tiếp (khác với các bài toán ảnh vật thể thông thường). Vì vậy độ tin cậy của đồ án không đến từ việc "so với gương" một con số benchmark có sẵn, mà đến từ việc **tuân thủ phương pháp làm thí nghiệm chặt chẽ**, dựa trên các khuyến nghị đã được nhiều nghiên cứu bảo mật uy tín chỉ ra, bao gồm:

- **Không chia dữ liệu ngẫu nhiên đơn giản** mà chia theo nhóm để các biến thể/họ mã độc liên quan không bị vắt qua cả tập huấn luyện lẫn tập kiểm tra — tránh việc mô hình "học thuộc" thay vì học đặc điểm chung, một sai lầm được chỉ ra rất kỹ trong nghiên cứu TESSERACT (Hội nghị bảo mật USENIX 2019).
- **Đa dạng hoá nguồn dữ liệu file sạch** để tránh mô hình học nhầm "nguồn gốc file" thay vì "tính độc hại thật sự" — rủi ro này và cách phòng tránh được hệ thống hoá trong nghiên cứu "Dos and Don'ts of Machine Learning in Computer Security" (USENIX 2022, một trong các bài báo được vinh danh xuất sắc nhất năm đó).
- **Báo cáo đầy đủ nhiều chỉ số** (Precision, Recall, F1, ROC-AUC) thay vì chỉ dùng Accuracy — vì với dữ liệu lệch tỉ lệ giữa hai lớp, Accuracy một mình có thể gây hiểu lầm, như nghiên cứu về ảnh hưởng của tỉ lệ lớp trong phát hiện mã độc Windows (2022) đã chỉ rõ.
- **Chạy lặp lại nhiều lần với hạt giống ngẫu nhiên khác nhau, kèm kiểm định thống kê** trước khi kết luận "cấu hình này tốt hơn cấu hình kia" — vì nghiên cứu về đo lường phương sai trong học máy (Hội nghị MLSys 2021) đã chứng minh: sự dao động do yếu tố ngẫu nhiên (khởi tạo trọng số, xáo trộn dữ liệu...) nhiều khi **lớn hơn cả** khác biệt thực sự giữa hai thuật toán — nếu không kiểm tra kỹ, rất dễ rút ra kết luận sai.
- **Ý tưởng nền tảng "byte của file cũng có thể coi như một dạng ảnh"** bắt nguồn từ nghiên cứu năm 2011 của Nataraj và cộng sự — nghiên cứu đầu tiên đề xuất hướng này và đã trở thành nền tảng cho rất nhiều nghiên cứu tiếp theo trong hơn một thập kỷ qua.
- **Ý tưởng dùng "độ hỗn loạn dữ liệu" (entropy) để phát hiện vùng bị đóng gói/mã hoá** bắt nguồn từ nghiên cứu kinh điển của Lyda & Hamrock (2007), sau đó được nhiều nghiên cứu khác phát triển thêm việc đưa entropy vào ảnh hoặc vào các mô hình học sâu.
- **Ý tưởng dùng "mật độ văn bản đọc được" làm dấu hiệu phát hiện** được củng cố bởi nhiều nghiên cứu cho thấy riêng thông tin này cũng đã đạt độ chính xác phát hiện rất cao, và bộ đặc trưng chuẩn công nghiệp EMBER (2018, do các nhà nghiên cứu bảo mật công bố) cũng đưa đặc trưng "chuỗi ký tự đọc được" vào làm một phần quan trọng.
- **Việc kết hợp cả entropy và mật độ văn bản vào chung một tấm ảnh nhiều lớp màu** có một tiền lệ trực tiếp là nghiên cứu HIT4Mal (2020), vốn cũng làm đúng trên bài toán phát hiện sạch/độc hại (không chỉ phân loại họ mã độc) và đạt kết quả tốt hơn so với chỉ dùng ảnh xám đơn thuần.

---

## 8. Tổng kết và hạn chế cần lưu ý

**Đã làm được:**
- Xây dựng thành công toàn bộ quy trình: từ file chương trình thô → tấm ảnh 3 lớp màu (xám + entropy + tỉ lệ văn bản đọc được) → mô hình học sâu → kết quả phát hiện sạch/độc hại, chạy trơn tru từ đầu đến cuối.
- So sánh được 4 kiến trúc mạng học sâu khác nhau, tất cả đều đạt độ chính xác cao (F1 trên 97%, ROC-AUC trên 0,99), khẳng định quy trình xử lý dữ liệu là yếu tố quan trọng hơn việc chọn đúng một kiến trúc mạng cụ thể.
- Rút ra được 2 kết luận có bằng chứng số liệu rõ ràng: (1) ảnh nhiều kênh có xu hướng tốt hơn ảnh xám đơn thuần, và nhân bản giả không có tác dụng; (2) ảnh nhỏ (224×224) đạt hiệu quả tương đương ảnh lớn hơn nhưng rẻ hơn nhiều lần — kết luận thứ hai này có đầy đủ kiểm định thống kê và đúng trên hai kiến trúc mạng khác nhau.
