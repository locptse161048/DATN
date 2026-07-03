# WORKFLOW — Quy trình mỗi phiên làm việc

Mục tiêu: mỗi phiên chỉ nạp tối thiểu context để **tiết kiệm token/limit** mà vẫn đảm bảo chất lượng.

## Nguyên tắc tối ưu context
- **1 phiên = 1 task** trong `docs/BACKLOG.md` (vd `S2.2`). Không gộp nhiều task lớn.
- Chỉ đọc: `CLAUDE.md` + mục *Input* của task đó. **Không** yêu cầu Claude "đọc cả dự án".
- File đã `DONE` thì không mở lại trừ khi task hiện tại phụ thuộc trực tiếp.

## Quy trình 6 bước mỗi phiên
1. **Mở đầu:** "Làm task `Sx.y` trong BACKLOG." Claude đọc CLAUDE.md + task đó.
2. **Xác nhận phạm vi:** Claude tóm tắt Input / Output / DoD trước khi code.
3. **Thực hiện:** viết code vào đúng module trong `src/` hoặc `scripts/`.
4. **Tự kiểm (chất lượng):** chạy thử / unit test, đối chiếu từng gạch đầu dòng DoD.
5. **Cập nhật trạng thái:**
   - Sửa cột trạng thái của task trong `BACKLOG.md` (bảng cuối file).
   - Mở `progress_dashboard.html`, tick các mục DoD đã đạt, đổi trạng thái.
6. **Kết thúc:** ghi 1–2 dòng ghi chú (blocker, link checkpoint) vào ô note của task trên dashboard.

## Vòng đời trạng thái
`TODO → DOING → REVIEW → DONE`
- `REVIEW`: code xong nhưng chưa tick đủ DoD (cần bạn kiểm/chạy GPU).
- `BLOCKED`: ghi rõ lý do ở ô note (vd "chờ thu thập đủ benign").
- Chỉ chuyển `DONE` khi **mọi mục DoD đã tick**.

## Thứ tự khuyến nghị
Làm thông một dataset trước cho chạy hết pipeline:
Chạy thông pipeline **phát hiện nhị phân** trước (đúng tên đề tài):
`S1.1+S1.2 → S1.3 → S1.4 → S2.1 → S2.2 → S2.2b → S2.3 → S2.4 → S3.1 → S4.1 → S5.1 → S5.2 → S5.3 → S6.1 → S6.2`
rồi làm 2 luận điểm chính (`S4.3` → `S5b.1`, `S5b.2`), nhánh phụ phân loại họ (`S5.4`), và các task P2 (`S6.3`, `S6b.1`, `S6b.2`).

## Mẹo tiết kiệm limit
- Tách phiên train (S5.3/S5.4) riêng — chúng tốn thời gian GPU, ít cần đối thoại.
- Gom các task viết code thuần (S2.1, S4.1, S6.1) vào phiên ngắn, rõ DoD.
- Khi cần Claude xem lại nhiều file, ưu tiên dùng subagent tìm kiếm thay vì nạp hết vào phiên chính.
