# Lộ trình triển khai — Phát hiện mã độc dựa trên ảnh

Lộ trình theo giai đoạn. Mỗi giai đoạn có deliverable rõ ràng để bám tiến độ DATN.

> Cập nhật 2026-06-25: **pivot sang phát hiện nhị phân (benign vs malware) trên PE thô** (figshare + MalwareBazaar + RAT + benign tự thu). **Bỏ Malimg & BIG2015.** Giữ 2 luận điểm chính (ảnh 3-kênh composite + hiệu quả độ phân giải 224²) và nhánh phụ phân loại họ (AVClass2 + family→behavior).

## Giai đoạn 0 — Khởi tạo (ĐÃ XONG)
- Cấu trúc thư mục, CLAUDE.md, README, requirements, .gitignore, khảo sát SOTA.

## Giai đoạn 1 — Thu thập & gán nhãn dữ liệu
- Thu thập **malware** (figshare 8.970 + MalwareBazaar theo `signature` + RAT) trong **VM cô lập**; **benign** đa nguồn (figshare 1.000 + Win10 + phần mềm khác).
- **Dedup SHA-256**, gán benign/malware, **AVClass2** chuẩn hóa tên họ.
- EDA: phân bố lớp/họ/nguồn, chốt `image_width`, **kiểm tra thiên lệch nguồn**.
- *Ước lượng:* 4–6 ngày (benign là nút thắt — phải đa dạng để chống bias).

## Giai đoạn 2 — Tiền xử lý PE thô → ảnh 3 kênh composite
- Đọc **PE thô đầy đủ** → ảnh xám (k1) + entropy-byte (k2) + tỉ lệ ASCII (k3), đều từ chuỗi byte → stack `3×H×W`.
- Sinh ảnh toàn dataset (streaming), 2 tầng: native (archive) + resize 224/336/448.
- **Split chống rò rỉ** (grouped/temporal) + stat per-channel.
- *Ước lượng:* 3–4 ngày.

## Giai đoạn 3 — Dataset & DataLoader
- Dataset PyTorch, transform (resize, normalize per-channel, augment), cân bằng lớp (benign khan hiếm).
- *Ước lượng:* 1–2 ngày.

## Giai đoạn 4 — Mô hình
- Factory VGG16 / ResNet50 / DenseNet121 pretrained + **ConvNeXt-Tiny** (timm); tùy chọn ViT/Swin, CNN custom. `in_chans=3`, `img_size` cấu hình được.
- *Ước lượng:* 1–2 ngày.

## Giai đoạn 5 — Huấn luyện
- Train loop config-driven; **phát hiện nhị phân** (4 model) là chính; **phân loại họ** (top-N) là phụ.
- *Ước lượng:* 4–6 ngày (GPU).

## Giai đoạn 5b — Hai luận điểm chính (co-primary)
- **A — Ablation kênh:** gray / +entropy / +ascii / full / gray×3 → chứng minh composite thêm thông tin.
- **B — Hiệu quả độ phân giải (H1):** ResNet50 + ConvNeXt-Tiny × {224,336,448} × **≥3 seed**; **mean±std + kiểm định thống kê**; bảng **accuracy-vs-cost** → 224² tối ưu. Chạy trên bộ phát hiện PE thô (native lớn).
- *Ước lượng:* 3–4 ngày (GPU). Chi tiết: `docs/EXPERIMENTS.md`.

## Giai đoạn 6 — Đánh giá & so sánh
- Acc/P/R/F1, **ROC-AUC**, confusion matrix; bảng so sánh model; **kiểm tra thiên lệch nguồn/temporal**; phân tích lỗi.
- *Ước lượng:* 2–3 ngày.

## Giai đoạn 6b — XAI & Robustness (tùy chọn)
- Grad-CAM/HiResCAM trên model tốt nhất; (tùy chọn) FGSM đo độ bền.
- *Ước lượng:* 2–3 ngày.

## Giai đoạn 7 — Báo cáo DATN
- Tổng hợp số liệu/biểu đồ; viết các chương; nêu rõ 2 câu hỏi nghiên cứu (RQ1 composite, RQ2 độ phân giải).
- *Ước lượng:* song song.

## Tổng kết
| GĐ | Nội dung | Ước lượng |
|----|----------|-----------|
| 1 | Thu thập + nhãn + EDA | 4–6 ngày |
| 2 | Tiền xử lý PE→ảnh | 3–4 ngày |
| 3 | Dataset | 1–2 ngày |
| 4 | Model | 1–2 ngày |
| 5 | Train | 4–6 ngày |
| 5b | 2 luận điểm chính | 3–4 ngày |
| 6 | Đánh giá | 2–3 ngày |
| 6b | XAI/Robustness (tùy chọn) | 2–3 ngày |
| 7 | Báo cáo | song song |

> Khuyến nghị: chạy thông pipeline phát hiện nhị phân trước (đúng tên đề tài), rồi mở rộng nhánh phụ phân loại họ.
