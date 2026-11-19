# Kiểm định ngoài mẫu VaR 95% (danh mục mặc định)

Tạo lúc 20/11/2026 00:46 (giờ Việt Nam) từ kho `data\portfolio.db`.

VaR lịch sử 1 ngày, cửa sổ trượt 250 phiên; VaR của mỗi ngày chỉ dùng dữ liệu trước ngày đó. Danh mục giữ tỷ trọng hiện tại trong suốt giai đoạn.

| Chỉ tiêu | Giá trị |
| --- | --- |
| Số ngày kiểm định | 496 |
| Từ ngày – đến ngày | 2024-11-21 – 2026-11-19 |
| Số lần lỗ vượt VaR | 28 |
| Tỷ lệ vượt thực tế / kỳ vọng | 5,65% / 5% |
| Kupiec (1995): LR / p-value / kết luận | 0,418 / 0,518 / Đạt |
| Christoffersen (1998): LR / p-value / kết luận | 1,159 / 0,282 / Đạt |

Mức ý nghĩa 5%: p-value ≥ 0,05 thì không bác bỏ giả thuyết mô hình đúng.
