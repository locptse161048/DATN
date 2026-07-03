# Môi trường & ràng buộc tài nguyên (cập nhật 2026-06-25)

Phân chia công việc theo phần cứng. Mọi quyết định kỹ thuật (cách tải, xử lý, batch size) bám đúng giới hạn này.

## 1. Phân vai môi trường

| Việc | Máy | Lý do |
|------|-----|-------|
| Thu thập + xử lý mã độc, sinh ảnh | **Máy local — trong VM cô lập** (VMware) | An toàn (không chạy malware trên host); i9 14 nhân xử lý nhanh |
| Train việc nhẹ: 224², nhiều seed, ablation | **Local RTX 4060 8GB** | Không quota/giới hạn phiên; đủ VRAM cho 224 |
| Train việc nặng: 448², ViT, chạy song song | **Google Colab (T4 16GB)** | Nhiều VRAM hơn; chạy song song với local |

### Phần cứng local
- CPU **i9-13900H** (14 nhân), RAM **16 GB**, GPU **RTX 4060 Laptop 8 GB**.
- VMware để cô lập mẫu malware khi bóc tách/đọc bytes.

### Colab (free/Pro)
- GPU T4 16GB (hoặc hơn nếu Pro), RAM ~12–25GB, đĩa tạm ~78GB.
- Giới hạn phiên ~12h, có thể ngắt → **checkpoint ra Google Drive mỗi epoch**.

## 2. An toàn khi xử lý mã độc (QUAN TRỌNG)

- figshare / MalwareBazaar / Ultimate-RAT-Collection là **mã độc thật** → bóc tách và đọc bytes **chỉ trong VM cô lập**, **không bao giờ chạy file**, không nối thư mục mẫu vào host trực tiếp.
- Tắt mạng/clipboard chia sẻ của VM khi thao tác mẫu; snapshot VM trước khi giải nén lượng lớn.
- Chỉ **đọc bytes → sinh ảnh PNG** rồi đưa ảnh (vô hại) ra host/Drive để train. Không đưa file thực thi ra ngoài.

## 3. Ngân sách dung lượng

| Thành phần | Dung lượng | Xử lý |
|-----------|-----------|-------|
| figshare (8.970 mal + 1.000 benign PE) | ~2.23 GB | giữ |
| MalwareBazaar (kéo theo nhu cầu) | co giãn (vd vài GB) | giữ phần đã chọn |
| Ultimate-RAT-Collection | vài GB (nhiều phiên bản) | dedup theo hash |
| Benign tự thu (Win10 + phần mềm) | vài GB | đa dạng nguồn |
| Ảnh 3 kênh **native** (archive) | tùy số mẫu (~chục GB) | ổ rời / thư mục archive |
| Ảnh 3 kênh **resize** 224/336/448 | ~vài GB | để train (local + Drive) |

> Nhẹ hơn nhiều so với phương án cũ (không còn 50GB `.bytes` + 150GB `.asm` của BIG2015).

## 4. Quy trình dữ liệu

```
[VM cô lập] thu thập malware (figshare/bazaar/RAT) + benign (figshare/Win10/đa nguồn)
   → dedup SHA-256 → gán nhãn benign/malware → AVClass2 chuẩn hóa họ
   → đọc bytes PE thô → sinh ảnh 3 kênh (native + resize 224/336/448)
[Host/Local 4060] train phát hiện 224² + ablation + nhiều seed
[Colab] train 448² + ViT + nhánh song song  (checkpoint → Drive)
```

- Train đọc thẳng bản **đã resize** đúng `img_size` → không tốn resize mỗi epoch.
- **Không** đọc trực tiếp hàng nghìn file nhỏ từ Drive khi train → giải nén ra `/content` trước.
- Checkpoint ở `My Drive/DATN/checkpoints/` để sống sót qua ngắt phiên Colab.

## 5. Ràng buộc công bằng (luận điểm độ phân giải)

- Bảng **accuracy-vs-cost** của 224/336/448 phải đo trên **CÙNG một GPU** → chạy trọn sweep độ phân giải trên một máy (cùng thiết bị) để cột thời gian/GPU mem so sánh được. Không đo 224 ở 4060 rồi 448 ở Colab cho cùng một bảng cost.

## 6. Gợi ý batch size

- **RTX 4060 8GB (AMP bật):** 224² → ResNet50/ConvNeXt bs 64, VGG16 bs 32; 336² → bs ~24–32; 448² → bs 8–16 + gradient accumulation.
- **Colab T4 16GB:** gấp ~đôi các mức trên.
- `num_workers=2`, `pin_memory=True`; `torch.save` checkpoint mỗi epoch + early stopping.

## 7. Rủi ro & giảm thiểu

| Rủi ro | Giảm thiểu |
|--------|-----------|
| Chạy nhầm mẫu malware trên host | Chỉ thao tác trong VM cô lập, không double-click file |
| Thiên lệch nguồn (benign Win10 vs malware kho khác) | Đa dạng nguồn benign; kiểm tra bias ở S1.4/S6.2 |
| Rò rỉ train/test (biến thể RAT trùng) | Dedup SHA-256 + grouped split |
| Mất tiến độ do Colab ngắt | Checkpoint ra Drive mỗi epoch |
| 4060 OOM ở 448² | Giảm batch + AMP + grad accumulation, hoặc đẩy 448 sang Colab |
