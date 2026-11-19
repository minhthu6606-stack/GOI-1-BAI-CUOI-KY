# Kết quả kiểm chứng

Các file trong thư mục này được tạo tự động từ kho dữ liệu thật, dùng làm bằng chứng cho Mục 7 của báo cáo:

| File | Tạo bằng lệnh | Nội dung |
| --- | --- | --- |
| `chat_luong_du_lieu.md` | `python scripts/verification_report.py` | Mỗi mã: số phiên, phiên thiếu, dòng bị gắn cờ, giá đã điều chỉnh, đối chiếu lợi suất với % thay đổi SSI |
| `nhat_ky_thu_thap.md` | `python scripts/verification_report.py` | Mỗi lần cập nhật: lúc nào, phiên nào, số chuỗi thành công/lỗi; danh sách phiên đã thu thập |
| `kiem_dinh_var.md` | `python scripts/verification_report.py` | Kiểm định ngoài mẫu VaR 95% (Kupiec 1995, Christoffersen 1998) của danh mục mặc định |
| `thu_loi.md` | `python scripts/test_error_scenarios.py` | 9 tình huống: thiếu key, sai key, mất kết nối, mã không tồn tại, giới hạn tần suất, danh mục sai, dữ liệu bẩn, nghỉ nhiều phiên rồi mở lại, dữ liệu đến muộn |
