# Kế hoạch — Phân loại họ mã độc (nhánh PHỤ, S5.4)

> Nhánh phụ của DATN. Bài toán chính vẫn là **phát hiện nhị phân**. Phân loại họ tận dụng **cùng pipeline ảnh 3 kênh** và **cùng dữ liệu `labels.csv`**, chỉ đổi nhãn (họ thay vì benign/malware) và một số xử lý riêng cho mất cân bằng.
> Cập nhật: 2026-06-30.

---

## 1. Mục tiêu & phạm vi
- **Bài toán:** phân loại **họ mã độc** (multi-class), **chỉ trên mẫu malware** (`label=1`).
- **Tái sử dụng tối đa:** ảnh 3 kênh (gray + entropy-byte + ASCII) **đã sinh sẵn** ở `data/processed/224/…`; `train.py`, `make_split.py`, `channels.py` dùng lại, chỉ đổi input nhãn và `num_classes`.
- **Độ phân giải:** dùng **224** (theo kết luận 2 của thí nghiệm A: 224 đủ tốt, rẻ). Không cần sweep độ phân giải cho nhánh phụ.
- **Đầu ra kèm theo:** bảng tra **family → behavior** (suy hành vi từ họ, KHÔNG train model hành vi riêng).

## 2. Tập lớp — CHỐT phương án C (family thật) + cap cân bằng

**Nguyên tắc:** "RAT" là **hành vi**, không phải họ → **KHÔNG** dùng làm 1 lớp. Thay vào đó **tách bucket RAT (621 subfamily) thành các họ RAT thật** và đặt ngang hàng với các họ figshare/Bazaar ở **cùng mức granularity family**.

### 2.1 Chuẩn hóa nhãn (bắt buộc)
- **Heodo → Emotet** (alias abuse.ch) → `Emotet` = 95 + 152 = **247**.
- **njrat (Bazaar 159) → NjRat (RAT-collection 412)** → gộp thành `NjRat` = **571**.
- Nhãn RAT lấy từ **path** (`data/raw/malware/RAT/<subfamily>/…`), không phải cột `family` (đang là "RAT").
- (Nên đối chiếu AVClass2/Malpedia để bắt alias còn lại.)

### 2.2 Ngưỡng ≥150 mẫu/họ → ~20 họ

| Nhóm | Họ (≥150 mẫu) |
|------|---------------|
| figshare/Bazaar (8) | Winwebsec 4400, Zbot 2100, Mediyes 1450, Zeroaccess 690, Locker 330, Emotet 247, Trickbot 175, RedLineStealer 161 |
| RAT-collection (12) | LiberiumRat 975, XWorm 859, NjRat 571, DcRat 384, EagleMonitorRat 365, AsyncRAT 313, VenomRAT 282, Gh0stRat 271, Quasar 258, MrTeeDol 245, Pulsar 238, LimeRat 217 |

→ **~20 họ, tất cả ở mức "family" thật.** Họ <150 (Formbook 113, SnakeKeylogger 82, AgentTesla 62, RemcosRAT 36, và các RAT subfamily <150) → **loại khỏi bài toán họ** (vẫn nằm trong tập phát hiện).

### 2.3 Cap cân bằng (giảm Winwebsec & các họ lớn) — CHỐT
Áp **trần chung `MAX_PER_CLASS` cho MỌI họ** (không chỉ Winwebsec — công bằng về phương pháp), lấy mẫu ngẫu nhiên có seed:

- **Mặc định đề xuất `MAX_PER_CLASS = 1000`** → Winwebsec 4400→1000, Zbot 2100→1000, Mediyes 1450→1000; các họ ≤1000 giữ nguyên.
- Kết hợp sàn 150 + trần 1000 → **mọi lớp trong [150, 1000]**, tỉ lệ mất cân bằng còn **~6.7:1** (thay vì 320:1). Dễ học + macro-F1 công bằng.
- Có thể chỉnh `MAX_PER_CLASS` (800 → ~5:1, chặt hơn nhưng mất data; 1500 → ~10:1). `MIN_PER_CLASS` cũng chỉnh được.
- **Cap ở mức dataset TRƯỚC khi split** (giống `detect_subset` từng cap RAT & Winwebsec) → cả train/val/test đều cân bằng. Ghi rõ trong báo cáo là *chủ động cân bằng*, không phải phân bố tự nhiên.

> Lưu ý: mất cân bằng **không** đến từ việc gán nhãn theo family, mà từ **số mẫu thu được mỗi họ** vốn không đều (long-tail). Cap chỉ làm nhẹ đi, không "khử" hoàn toàn bản chất long-tail của malware.

### 2.4 Benign: KHÔNG thêm
Chỉ malware (multi-class họ) — đúng định nghĩa "phân loại họ". Benign để riêng cho bài toán phát hiện.

## 4. Split chống rò rỉ — KHÁC bài toán phát hiện (đọc kỹ)
> **Cảnh báo quan trọng:** ở bài toán phát hiện, RAT được **grouped theo subfamily** (cả XWorm về một tập) để chống rò rỉ. **KHÔNG dùng lại cách đó ở đây** — vì giờ XWorm *là một lớp*, gộp cả lớp vào train hoặc test → lớp đó **không thể học/không thể đánh giá**. Grouping theo subfamily và phân loại subfamily **mâu thuẫn nhau**.

- **Dùng stratified split theo họ** (mỗi họ chia ~70/15/15) để mọi lớp có mặt ở cả 3 tập. Đã **dedup SHA-256** nên không có mẫu trùng hệt.
- **Rủi ro còn lại — biến thể gần trùng cùng builder** (vd 2 file XWorm khác nhau vài byte config) có thể vắt qua train/test → **F1 họ lạc quan**. Đây là **giới hạn phải nêu rõ**. Giảm thiểu (tùy chọn, nâng cao): cụm near-duplicate bằng **fuzzy hash (ssdeep/TLSH)** rồi grouped theo cụm — cụm nhỏ hơn lớp nên vẫn giữ được lớp ở mọi tập.
- Lớp nhỏ (~150–250 mẫu): test chỉ ~22–37 mẫu → CI rộng → cân nhắc **k-fold stratified** (vd 5-fold) để ước lượng ổn định thay vì 1 lần hold-out.
- `make_split.py` cần thêm cờ **tắt grouping RAT** cho nhánh này (hoặc script split riêng `make_split_family.py`).

## 5. Ảnh & tiền xử lý
- **Không sinh lại ảnh.** Dùng ảnh 3 kênh @224 đã có (`data/processed/224/{sha[:2]}/{sha}.png`) — cùng biểu diễn với bài toán phát hiện.
- Chuẩn hóa per-channel: tính mean/std **trên tập train của bài toán họ** (`channel_stats_family.json`) — vì phân bố lớp khác bài toán phát hiện.

## 6. Xử lý mất cân bằng (trọng tâm)
Kết hợp nhiều biện pháp, cấu hình được:
- **Class weights** (`class_weights: auto` — nghịch tần suất) trong CrossEntropyLoss. *Mặc định.*
- **Weighted sampler** (oversample lớp hiếm) — thử nghiệm so với class weights.
- **(Tùy chọn) cap RAT** khi train (vd ≤2,000) để giảm áp đảo — giống cách `detect_subset` cap RAT; giữ nguyên val/test không cap để đánh giá thực tế.
- **Augmentation** nhẹ cho lớp hiếm (flip/nhiễu byte) — cân nhắc vì texture malware nhạy với biến đổi.
- **Metric chính = macro-F1** (đối xử mọi lớp như nhau), KHÔNG dùng accuracy làm chính (RAT chi phối → accuracy ảo cao).

## 7. Model & huấn luyện
- **Kiến trúc:** dùng lại model tốt nhất của bài toán phát hiện (DenseNet121 F1≈0.977, hoặc ResNet50) + có thể so 2–3 kiến trúc. `train.py` chỉ đổi `num_classes = N` và `task: family`.
- **Config:** `configs/family_{model}_224.yaml` (thêm `label_col: family`, `min_class: 150`, `alias_map`, `class_weights`).
- **≥3 seed** cho model chính để báo cáo mean±std (lớp nhỏ dao động lớn).

## 8. Đánh giá & Output
**Một bảng per-class** + các chỉ số tổng hợp:

| Họ | #test | Precision | Recall | F1 | (support) |
|----|------:|:---------:|:------:|:--:|:---------:|
| Winwebsec | … | … | … | … | … |
| NjRat | … | … | … | … | … |
| … (~20 họ) | | | | | |
| **Macro avg** | | … | … | **…** | |
| **Weighted avg** | | … | … | … | |

- **Chỉ số chính:** macro-F1; kèm weighted-F1, accuracy, **top-3 accuracy** (hữu ích khi họ dễ nhầm).
- **Confusion matrix** (chuẩn hóa theo hàng) → chỉ ra cặp họ hay nhầm (kỳ vọng: các họ RAT gần nhau NjRat↔AsyncRAT↔Quasar; Emotet↔Trickbot — cùng nhóm loader/banking).
- **Phân tích lỗi:** ví dụ ảnh bị phân loại sai; liên hệ với alias/nhóm hành vi.
- (Tùy chọn) **XAI Grad-CAM** trên vài mẫu để xem vùng texture đặc trưng từng họ.

## 9. Bảng tra family → behavior (đầu ra suy diễn, KHÔNG train)
Suy hành vi từ họ (đối chiếu **Malpedia/MITRE ATT&CK** khi viết báo cáo):

| Họ | Nhóm hành vi |
|----|--------------|
| Locker | Ransomware |
| Zbot (Zeus) | Banking trojan |
| Trickbot | Banking trojan / Loader |
| Emotet (Heodo) | Loader / Botnet (gốc banking) |
| Zeroaccess (Sirefef) | Rootkit / Click-fraud botnet |
| Winwebsec | Rogue security / Scareware |
| Mediyes | Trojan clicker (driver ký số) |
| RedLineStealer | Infostealer |
| Formbook | Infostealer |
| SnakeKeylogger | Keylogger / Infostealer |
| Các họ RAT (NjRat, XWorm, DcRat, AsyncRAT, Quasar, VenomRAT, Gh0stRat, LimeRat, LiberiumRat…) | RAT / Backdoor |

→ Nhóm hành vi rút gọn: **Ransomware · Banking/Loader · Infostealer/Keylogger · RAT/Backdoor · Rootkit/Botnet · Rogue/Scareware**. Bảng này cho phép nói "model nhận diện họ X → hành vi Y" mà không cần dữ liệu hành vi động.

## 10. Việc cần làm (chi tiết hóa S5.4)
1. **S5.4a — Chuẩn hóa & tách nhãn họ:** lọc `label=1`; **tách RAT-subfamily từ path**; gộp alias (Heodo→Emotet, njrat→NjRat); áp **ngưỡng ≥150** + **cap MAX_PER_CLASS=1000** (seed cố định) → `data/interim/labels_family.csv` + `family_map.json` (~20 lớp). *(0.5–1 ngày)*
2. **S5.4b — Split họ chống rò rỉ:** `make_split_family.py` (hoặc cờ tắt grouping RAT) — **stratified theo họ, KHÔNG group theo subfamily**; dedup SHA-256; (tùy chọn) cụm near-dup ssdeep/TLSH; + `channel_stats_family.json`. Kiểm tra mỗi lớp có mặt ở 3 tập. *(0.5–1 ngày)*
3. **S5.4c — Train phân loại họ:** `family_{model}_224.yaml`, `num_classes≈20`, class_weights/sampler, ≥3 seed (model tốt nhất từ S5.3). *(1–2 ngày GPU)*
4. **S5.4d — Đánh giá:** bảng per-class + macro/weighted-F1 + top-3 + confusion matrix + phân tích lỗi → `reports/experiment_family.md`. *(0.5 ngày)*
5. **S5.4e — Bảng family→behavior:** hoàn thiện, đối chiếu Malpedia/MITRE. *(0.25 ngày)*

## 11. Rủi ro & lưu ý
- **Long-tail vẫn còn** sau cap (~6.7:1) → ưu tiên **macro-F1** và **top-3**; nêu rõ đây là phân bố đã chủ động cân bằng.
- **Rò rỉ near-duplicate builder** (không group được theo subfamily) → F1 có thể lạc quan; nêu giới hạn, cân nhắc ssdeep/TLSH.
- **Nhãn RAT = tên builder** (chất lượng khác nhau, không qua AVClass) → độ tin cậy nhãn thấp hơn figshare/Bazaar; ghi rõ.
- **Bias nguồn:** figshare/Bazaar vs RAT-collection → model có thể học "nguồn". Kiểm tra như S6.2 cho nhánh họ.

## Nguồn tham khảo
- Malpedia (Fraunhofer FKIE) — mô tả họ & alias: https://malpedia.caad.fkie.fraunhofer.de/
- AVClass2 — chuẩn hóa nhãn họ từ VT: https://github.com/malicialab/avclass
- Tài liệu nội bộ: `docs/DATASET_PIPELINE.md`, `docs/EXPERIMENTS.md`, `scripts/make_split.py`, `scripts/train.py`.
