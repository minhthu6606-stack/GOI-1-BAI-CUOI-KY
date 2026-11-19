# Thử các tình huống lỗi

Chạy lúc 20/11/2026 00:45 (giờ Việt Nam) bằng `python scripts/test_error_scenarios.py`.

| Tình huống | Cách thử | Kết quả mong đợi | Kết quả thực tế | Đánh giá |
| --- | --- | --- | --- | --- |
| Thiếu API key | Để trống SSI_API_KEY/SSI_API_SECRET | Báo lỗi, không gọi mạng | Thiếu SSI_API_KEY hoặc SSI_API_SECRET trong file .env (xem .env.example) | Đạt |
| API key sai | Dùng key giả | SSI từ chối xác thực | Xác thực thất bại: HTTP 401 - {"code":401105,"msg":"Invalid API key or secret."} | Đạt |
| Mất kết nối | Trỏ tới máy chủ không tồn tại | Báo không kết nối được, không treo | Không kết nối được máy chủ SSI khi xác thực: HTTPSConnectionPool(host='may-chu-khong-ton-t... (sau 0.0 giây) | Đạt |
| Mã không tồn tại | Hỏi giá 10 ngày của mã ZZZ9 (không tồn tại) | Trả rỗng hoặc báo lỗi, không dừng | SSI trả 0 bản ghi, giữ lại 0 -> ứng dụng ghi 'Không có dữ liệu' | Đạt |
| Giới hạn tần suất | Gửi liên tiếp 4 yêu cầu tổng hợp thị trường, đo khoảng cách | Mỗi yêu cầu cách nhau ≥ 1,1 giây | 4 yêu cầu, khoảng cách nhỏ nhất 1.09 giây | Đạt |
| Danh mục nhập sai | Số lượng âm và mã sai định dạng | Báo lỗi, không tính toán | Mã không hợp lệ: AB! | Đạt |
| Dữ liệu bẩn | 5 bản ghi: 1 trùng ngày, 1 thiếu giá, 1 giá bằng 0 | Giữ 2, loại 3 và thống kê lý do | Nhận 5, giữ 2; loại trùng 1, thiếu 1, giá ≤ 0 1 | Đạt |
| Nghỉ nhiều phiên rồi mở lại | Mô phỏng: cập nhật thứ Hai 09/11, nghỉ 8 phiên (ngày thi), mở lại thứ Sáu 20/11 | Một lần tải bù đủ các phiên còn thiếu; 0 phiên thiếu, 0 dòng trùng | Phiên cuối trước khi nghỉ 2026-11-09; lần mở lại tải 1 yêu cầu, cách tải 'incremental', thêm 9 phiên mới (đến 2026-11-20); phiên thiếu 0, dòng trùng 0 | Đạt |
| Dữ liệu đến muộn | Mô phỏng: tải lúc 10:00 ngày 19/11 (giá tạm 50.500), tải lại sau 15:00 (giá đóng cửa 51.000) | Trước 15:00 không coi phiên 19/11 là đã chốt; lần tải sau thay giá tạm, không tải lại toàn bộ | Lúc 10:00 phiên đã chốt gần nhất là 2026-11-18; sau 15:00 ứng dụng tự cập nhật lại; giá lưu cho 19/11 = 51.000, cách tải 'incremental' | Đạt |
