# Kiểm định ngoài mẫu VaR 95% (3 danh mục ví dụ)

Tạo lúc 20/11/2026 23:58 (giờ Việt Nam) từ kho `data\portfolio.db`.

VaR lịch sử 1 ngày, cửa sổ trượt 250 phiên; VaR của mỗi ngày chỉ dùng dữ liệu trước ngày đó. Mỗi danh mục giữ tỷ trọng hiện tại trong suốt giai đoạn (2024-11-21 – 2026-11-20). Tỷ lệ vượt kỳ vọng: 5%.

| Danh mục | Số ngày kiểm định | Số lần vượt | Tỷ lệ vượt | Kupiec (1995): p-value | Christoffersen (1998): p-value |
| --- | --- | --- | --- | --- | --- |
| Người mới bắt đầu | 497 | 26 | 5,23% | 0,814 – Đạt | 0,009 – Không đạt (dồn cục) |
| Dồn vào ngân hàng | 497 | 33 | 6,64% | 0,109 – Đạt | 0,004 – Không đạt (dồn cục) |
| Đa dạng hơn | 497 | 27 | 5,43% | 0,662 – Đạt | 0,002 – Không đạt (dồn cục) |

Mức ý nghĩa 5%: p-value ≥ 0,05 thì không bác bỏ giả thuyết mô hình đúng.
