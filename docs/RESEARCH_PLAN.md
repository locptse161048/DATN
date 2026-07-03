# RESEARCH_PLAN — Kế hoạch tìm bài báo làm cơ sở cho các quyết định trong đồ án

> Mục tiêu: mỗi quyết định kỹ thuật trong CLAUDE.md phải có ≥1 paper làm cơ sở trích dẫn trong báo cáo DATN.
> Kết quả tổng hợp ghi vào `docs/RELATED_WORK.md` (citation + link + tóm tắt + kết quả + liên hệ quyết định + vì sao phù hợp).
> Trạng thái: ⬜ chưa làm · 🔄 đang làm · ✅ xong

## Thứ tự research

### 1. ✅ Nền tảng: biểu diễn PE bytes → ảnh
Quyết định cần cơ sở: đọc bytes PE thô → ảnh grayscale; giữ header; width cố định.
- Nataraj et al. 2011 (VizSec) — paper gốc malware-as-image, GIST + k-NN.
- Các survey về image-based malware detection (2022–2026).
- Quy ước width: cố định theo file size vs cố định tuyệt đối; ảnh native vs resize.

### 2. ✅ Luận điểm A: ảnh đa kênh composite (gray + entropy + ASCII)
Quyết định cần cơ sở: 3 kênh đều từ chuỗi byte; entropy cửa sổ 256 byte; tỉ lệ printable ASCII; khác nhân bản kênh; normalize per-channel.
- Paper dùng entropy map làm kênh ảnh (structural entropy, entropy visualization).
- Paper multi-channel/RGB malware image (Hilbert curve, bigram, markov...).
- Paper dùng đặc trưng printable strings/ASCII trong static analysis.
- Cơ sở cho ablation kênh (so với gray×3).

### 3. ✅ Luận điểm B: độ phân giải vs chi phí (224/336/448)
Quyết định cần cơ sở: 224² đủ tốt, rẻ hơn 336²/448²; ảnh hưởng resize/downsample lên texture malware.
- Paper khảo sát ảnh hưởng input size lên accuracy trong malware imaging.
- Paper về information loss khi resize ảnh malware.
- Chuẩn thống kê: nhiều seed, mean±std, kiểm định (so sánh model đúng cách).

### 4. ✅ Phương pháp luận thí nghiệm
Quyết định cần cơ sở: grouped split chống rò rỉ; chống bias nguồn benign; dedup SHA-256; VirusTotal + AVClass2; tỉ lệ lớp 1.5:1.
- TESSERACT (USENIX 2019) — spatial/temporal bias trong đánh giá malware ML.
- Paper về dataset bias / experimental pitfalls trong malware ML (Arp et al. 2022...).
- AVClass / AVClass2 — chuẩn hóa nhãn họ.
- Cơ sở chọn tỉ lệ mất cân bằng lớp.

### 5. ✅ Model & XAI
Quyết định cần cơ sở: transfer learning ImageNet → ảnh malware; chọn VGG16/ResNet50/DenseNet121/ConvNeXt-Tiny; Grad-CAM/HiResCAM.
- Paper transfer learning CNN trên ảnh malware (fine-tune pretrained).
- Paper so sánh nhiều kiến trúc CNN cho malware classification.
- ConvNeXt (Liu et al. 2022) + ứng dụng vào malware.
- Grad-CAM/HiResCAM gốc + ứng dụng XAI cho ảnh malware.

### 6. ✅ Tổng hợp & kiểm tra (xong lần 1 — 2026-07-03; còn mục "thiếu" cuối RELATED_WORK.md)
- Gộp tất cả vào `docs/RELATED_WORK.md` theo cấu trúc: Citation → Link → Tóm tắt → Kết quả chính → Quyết định liên quan → Vì sao phù hợp đề tài.
- Verify link (DOI/arXiv) còn truy cập được.
- Đánh dấu paper NÀO trích cho mục NÀO trong báo cáo DATN.

## Format entry chuẩn trong RELATED_WORK.md

```
### [số]. Tên paper (Tác giả, Năm, Venue)
- **Citation:** ...
- **Link:** DOI / arXiv
- **Tóm tắt:** phương pháp làm gì
- **Kết quả chính:** số liệu, dataset
- **Quyết định liên quan:** (mục nào trong CLAUDE.md)
- **Vì sao phù hợp:** liên hệ trực tiếp với đề tài
```
