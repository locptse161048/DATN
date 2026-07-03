# Malware Detection using Image-based Deep Learning Techniques
*Phát hiện mã độc bằng kỹ thuật học sâu dựa trên biểu diễn ảnh*

Đồ án tốt nghiệp — phát hiện mã độc (benign vs malware) bằng cách chuyển bytes của file PE thành **ảnh 3 kênh composite** (grayscale + entropy-byte + tỉ lệ ASCII, đều từ chuỗi byte) và dùng CNN (PyTorch). Nhánh phụ: phân loại họ.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Tài liệu
- `CLAUDE.md` — tổng quan & quy ước dự án
- `docs/ROADMAP.md` — lộ trình · `docs/BACKLOG.md` — task · `docs/EXPERIMENTS.md` — thí nghiệm
- `docs/ENVIRONMENT.md` — phần cứng & an toàn · `docs/SOTA_2026.md` — khảo sát

## Dataset (PE thô — xử lý trong VM cô lập)
- **Malware:** figshare 6635642 (8.970) + MalwareBazaar (API, theo `signature`) + Ultimate-RAT-Collection
- **Benign:** figshare benign (1.000) + `.dll/.bin` từ Win10 (VMware) + phần mềm đa nguồn

Đặt dữ liệu vào `data/raw/malware/` và `data/raw/benign/`. **Không dùng Malimg/BIG2015.**

## Models
VGG16, ResNet50, DenseNet121 (transfer learning) + **ConvNeXt-Tiny** (timm); tùy chọn ViT/Swin, CNN custom.

## Hai luận điểm chính
1. **Ảnh 3-kênh composite** (gray + entropy-byte + ASCII-ratio) vượt ảnh xám 1 kênh.
2. **Hiệu quả độ phân giải:** 224² đạt accuracy xấp xỉ/nhỉnh hơn 336²/448² nhưng rẻ hơn nhiều.
