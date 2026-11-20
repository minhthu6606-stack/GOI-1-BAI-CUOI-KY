# Kết quả chi tiết 3 danh mục ví dụ

Tạo lúc 20/11/2026 23:58 (giờ Việt Nam) từ kho `data\portfolio.db`.

Mỗi danh mục: bảng nắm giữ, tỷ trọng ngành, thanh khoản và toàn bộ tiêu chí kiểm tra (không khai mức chịu lỗ, tỷ lệ tham gia thanh khoản 20%).

## Người mới bắt đầu

4 mã ở 4 ngành, mỗi mã khoảng 22%, giữ 10% tiền mặt. Kết luận chung: **Cần xem lại** (Rủi ro cao 1, Cảnh báo 3, Tốt 2, Thông tin 7). Tổng tài sản 100.000.000 đ, tiền mặt 11.595.000 đ (11,6%).

| Mã | Số lượng | Giá đóng cửa | Giá trị (đ) | Tỷ trọng |
| --- | --- | --- | --- | --- |
| FPT | 500 | 45.000 | 22.500.000 | 22,5% |
| MBB | 1.200 | 18.250 | 21.900.000 | 21,9% |
| HPG | 1.100 | 20.450 | 22.495.000 | 22,5% |
| MWG | 300 | 71.700 | 21.510.000 | 21,5% |

| Ngành | Tỷ trọng phần cổ phiếu |
| --- | --- |
| Phần mềm | 25,5% |
| Thép và sản phẩm thép | 25,4% |
| Ngân hàng | 24,8% |
| Phân phối hàng chuyên dụng | 24,3% |

| Mã | % KL TB 20 phiên đang nắm | Số ngày có tiền | Mức thanh khoản |
| --- | --- | --- | --- |
| FPT | 0,00% | 3 | Cao |
| MBB | 0,01% | 3 | Cao |
| HPG | 0,01% | 3 | Cao |
| MWG | 0,01% | 3 | Cao |

| Nhóm | Tiêu chí | Giá trị | Mức | Ngưỡng | Cơ sở |
| --- | --- | --- | --- | --- | --- |
| Mức tập trung | Tỷ trọng mã lớn nhất | FPT: 22,5% | Cảnh báo | ≤ 10% tổng tài sản | UCITS 2009/65/EC, Điều 52 (chuẩn tham chiếu của quỹ đại chúng) |
| Mức tập trung | Tổng các mã chiếm trên 5% | 88,4% | Cảnh báo | ≤ 40% tổng tài sản | UCITS 2009/65/EC, Điều 52 (quy tắc 5/10/40) |
| Mức tập trung | Mức đa dạng hóa (Số mã hiệu dụng) | 4,0 mã | Rủi ro cao | ≥ 10 mã: tốt; < 5 mã: tập trung cao | Evans & Archer (1968); tính bằng 1 / HHI |
| Mức tập trung | Ngành chiếm tỷ trọng lớn nhất | Phần mềm: 25,5% | Tốt | ≤ 50% phần cổ phiếu | Quy tắc tự đặt: quá nửa danh mục phụ thuộc một ngành |
| Thanh khoản | Tài sản khó bán nhanh | 0,0% | Tốt | ≤ 15% tổng tài sản | SEC Rule 22e-4 (17 CFR 270.22e-4) |
| Rủi ro thị trường | Độ biến động năm (Volatility) | 20,4% | Thông tin | VN-Index: 19,2% | Độ lệch chuẩn lợi suất ngày × √252 |
| Rủi ro thị trường | Độ nhạy với thị trường (Beta) | 0,74 | Thông tin | Beta = 1: cùng nhịp VN-Index | Sharpe (1964) |
| Rủi ro thị trường | Phần rủi ro đến từ thị trường chung (R²) | 49% | Cảnh báo | ≥ 50%: rủi ro chủ yếu đến từ thị trường | Mô hình chỉ số đơn - Sharpe (1963) |
| Rủi ro thị trường | Mức lỗ trong một phiên xấu (VaR 95%) | 2,0% ≈ 1.992.987 đ | Thông tin | Không có ngưỡng chuẩn (khai mức chịu lỗ để so) | Jorion (2007), mô phỏng lịch sử |
| Rủi ro thị trường | Độ tin cậy của VaR (kiểm định ngoài mẫu) | 26/497 ngày vượt VaR (5,2%) | Thông tin | Đánh giá công cụ đo, không tính vào kết luận chung | Kupiec (1995); Christoffersen (1998) |
| Rủi ro thị trường | Sụt giảm tối đa 1 năm (Max Drawdown) | -24,8% | Thông tin | Không có ngưỡng chuẩn (khai mức chịu lỗ để so) | Từ đỉnh xuống đáy của chuỗi giá trị danh mục |
| Kịch bản xấu | Mọi mã cùng giảm sàn | 1 phiên: 6.115.000 đ | Thông tin | 6,1% (1 phiên) / 17,0% (3 phiên) tổng tài sản | Biên độ giá HOSE 7%, HNX 10%, UPCoM 15% |
| Khối ngoại | Room ngoại còn lại (Foreign room) | MWG: 0,0% | Thông tin | Hết room: nhà đầu tư nước ngoài không mua thêm được | Trường remainForeignRoom, totalForeignRoom của SSI |

## Dồn vào ngân hàng

4 mã cùng ngành ngân hàng, mỗi mã khoảng 22%, giữ 10% tiền mặt. Kết luận chung: **Cần xem lại** (Rủi ro cao 1, Cảnh báo 3, Tốt 2, Thông tin 7). Tổng tài sản 100.000.000 đ, tiền mặt 15.260.000 đ (15,3%).

| Mã | Số lượng | Giá đóng cửa | Giá trị (đ) | Tỷ trọng |
| --- | --- | --- | --- | --- |
| VCB | 400 | 50.200 | 20.080.000 | 20,1% |
| MBB | 1.200 | 18.250 | 21.900.000 | 21,9% |
| ACB | 1.100 | 19.600 | 21.560.000 | 21,6% |
| TCB | 1.000 | 21.200 | 21.200.000 | 21,2% |

| Ngành | Tỷ trọng phần cổ phiếu |
| --- | --- |
| Ngân hàng | 100,0% |

| Mã | % KL TB 20 phiên đang nắm | Số ngày có tiền | Mức thanh khoản |
| --- | --- | --- | --- |
| VCB | 0,01% | 3 | Cao |
| MBB | 0,01% | 3 | Cao |
| ACB | 0,01% | 3 | Cao |
| TCB | 0,01% | 3 | Cao |

| Nhóm | Tiêu chí | Giá trị | Mức | Ngưỡng | Cơ sở |
| --- | --- | --- | --- | --- | --- |
| Mức tập trung | Tỷ trọng mã lớn nhất | MBB: 21,9% | Cảnh báo | ≤ 10% tổng tài sản | UCITS 2009/65/EC, Điều 52 (chuẩn tham chiếu của quỹ đại chúng) |
| Mức tập trung | Tổng các mã chiếm trên 5% | 84,7% | Cảnh báo | ≤ 40% tổng tài sản | UCITS 2009/65/EC, Điều 52 (quy tắc 5/10/40) |
| Mức tập trung | Mức đa dạng hóa (Số mã hiệu dụng) | 4,0 mã | Rủi ro cao | ≥ 10 mã: tốt; < 5 mã: tập trung cao | Evans & Archer (1968); tính bằng 1 / HHI |
| Mức tập trung | Ngành chiếm tỷ trọng lớn nhất | Ngân hàng: 100,0% | Cảnh báo | ≤ 50% phần cổ phiếu | Quy tắc tự đặt: quá nửa danh mục phụ thuộc một ngành |
| Thanh khoản | Tài sản khó bán nhanh | 0,0% | Tốt | ≤ 15% tổng tài sản | SEC Rule 22e-4 (17 CFR 270.22e-4) |
| Rủi ro thị trường | Độ biến động năm (Volatility) | 18,1% | Thông tin | VN-Index: 19,2% | Độ lệch chuẩn lợi suất ngày × √252 |
| Rủi ro thị trường | Độ nhạy với thị trường (Beta) | 0,67 | Thông tin | Beta = 1: cùng nhịp VN-Index | Sharpe (1964) |
| Rủi ro thị trường | Phần rủi ro đến từ thị trường chung (R²) | 50% | Tốt | ≥ 50%: rủi ro chủ yếu đến từ thị trường | Mô hình chỉ số đơn - Sharpe (1963) |
| Rủi ro thị trường | Mức lỗ trong một phiên xấu (VaR 95%) | 1,7% ≈ 1.726.752 đ | Thông tin | Không có ngưỡng chuẩn (khai mức chịu lỗ để so) | Jorion (2007), mô phỏng lịch sử |
| Rủi ro thị trường | Độ tin cậy của VaR (kiểm định ngoài mẫu) | 33/497 ngày vượt VaR (6,6%) | Thông tin | Đánh giá công cụ đo, không tính vào kết luận chung | Kupiec (1995); Christoffersen (1998) |
| Rủi ro thị trường | Sụt giảm tối đa 1 năm (Max Drawdown) | -15,3% | Thông tin | Không có ngưỡng chuẩn (khai mức chịu lỗ để so) | Từ đỉnh xuống đáy của chuỗi giá trị danh mục |
| Kịch bản xấu | Mọi mã cùng giảm sàn | 1 phiên: 5.835.000 đ | Thông tin | 5,8% (1 phiên) / 16,3% (3 phiên) tổng tài sản | Biên độ giá HOSE 7%, HNX 10%, UPCoM 15% |
| Khối ngoại | Room ngoại còn lại (Foreign room) | MBB: 5,7% | Thông tin | Hết room: nhà đầu tư nước ngoài không mua thêm được | Trường remainForeignRoom, totalForeignRoom của SSI |

## Đa dạng hơn

8 mã ở 7 ngành, mỗi mã khoảng 10%, giữ 20% tiền mặt. Kết luận chung: **Cần theo dõi** (Rủi ro cao 0, Cảnh báo 2, Tốt 4, Thông tin 7). Tổng tài sản 100.000.000 đ, tiền mặt 39.315.000 đ (39,3%).

| Mã | Số lượng | Giá đóng cửa | Giá trị (đ) | Tỷ trọng |
| --- | --- | --- | --- | --- |
| FPT | 200 | 45.000 | 9.000.000 | 9,0% |
| VCB | 100 | 50.200 | 5.020.000 | 5,0% |
| MBB | 500 | 18.250 | 9.125.000 | 9,1% |
| HPG | 400 | 20.450 | 8.180.000 | 8,2% |
| MWG | 100 | 71.700 | 7.170.000 | 7,2% |
| VNM | 100 | 51.400 | 5.140.000 | 5,1% |
| GAS | 100 | 70.500 | 7.050.000 | 7,0% |
| SSI | 500 | 20.000 | 10.000.000 | 10,0% |

| Ngành | Tỷ trọng phần cổ phiếu |
| --- | --- |
| Ngân hàng | 23,3% |
| Môi giới chứng khoán | 16,5% |
| Phần mềm | 14,8% |
| Thép và sản phẩm thép | 13,5% |
| Phân phối hàng chuyên dụng | 11,8% |
| Phân phối xăng dầu & khí đốt | 11,6% |
| Thực phẩm | 8,5% |

| Mã | % KL TB 20 phiên đang nắm | Số ngày có tiền | Mức thanh khoản |
| --- | --- | --- | --- |
| FPT | 0,00% | 3 | Cao |
| VCB | 0,00% | 3 | Cao |
| MBB | 0,00% | 3 | Cao |
| HPG | 0,00% | 3 | Cao |
| MWG | 0,00% | 3 | Cao |
| VNM | 0,00% | 3 | Cao |
| GAS | 0,01% | 3 | Cao |
| SSI | 0,00% | 3 | Cao |

| Nhóm | Tiêu chí | Giá trị | Mức | Ngưỡng | Cơ sở |
| --- | --- | --- | --- | --- | --- |
| Mức tập trung | Tỷ trọng mã lớn nhất | SSI: 10,0% | Tốt | ≤ 10% tổng tài sản | UCITS 2009/65/EC, Điều 52 (chuẩn tham chiếu của quỹ đại chúng) |
| Mức tập trung | Tổng các mã chiếm trên 5% | 60,7% | Cảnh báo | ≤ 40% tổng tài sản | UCITS 2009/65/EC, Điều 52 (quy tắc 5/10/40) |
| Mức tập trung | Mức đa dạng hóa (Số mã hiệu dụng) | 7,6 mã | Cảnh báo | ≥ 10 mã: tốt; < 5 mã: tập trung cao | Evans & Archer (1968); tính bằng 1 / HHI |
| Mức tập trung | Ngành chiếm tỷ trọng lớn nhất | Ngân hàng: 23,3% | Tốt | ≤ 50% phần cổ phiếu | Quy tắc tự đặt: quá nửa danh mục phụ thuộc một ngành |
| Thanh khoản | Tài sản khó bán nhanh | 0,0% | Tốt | ≤ 15% tổng tài sản | SEC Rule 22e-4 (17 CFR 270.22e-4) |
| Rủi ro thị trường | Độ biến động năm (Volatility) | 12,9% | Thông tin | VN-Index: 19,2% | Độ lệch chuẩn lợi suất ngày × √252 |
| Rủi ro thị trường | Độ nhạy với thị trường (Beta) | 0,50 | Thông tin | Beta = 1: cùng nhịp VN-Index | Sharpe (1964) |
| Rủi ro thị trường | Phần rủi ro đến từ thị trường chung (R²) | 56% | Tốt | ≥ 50%: rủi ro chủ yếu đến từ thị trường | Mô hình chỉ số đơn - Sharpe (1963) |
| Rủi ro thị trường | Mức lỗ trong một phiên xấu (VaR 95%) | 1,2% ≈ 1.176.191 đ | Thông tin | Không có ngưỡng chuẩn (khai mức chịu lỗ để so) | Jorion (2007), mô phỏng lịch sử |
| Rủi ro thị trường | Độ tin cậy của VaR (kiểm định ngoài mẫu) | 27/497 ngày vượt VaR (5,4%) | Thông tin | Đánh giá công cụ đo, không tính vào kết luận chung | Kupiec (1995); Christoffersen (1998) |
| Rủi ro thị trường | Sụt giảm tối đa 1 năm (Max Drawdown) | -17,5% | Thông tin | Không có ngưỡng chuẩn (khai mức chịu lỗ để so) | Từ đỉnh xuống đáy của chuỗi giá trị danh mục |
| Kịch bản xấu | Mọi mã cùng giảm sàn | 1 phiên: 4.210.000 đ | Thông tin | 4,2% (1 phiên) / 11,7% (3 phiên) tổng tài sản | Biên độ giá HOSE 7%, HNX 10%, UPCoM 15% |
| Khối ngoại | Room ngoại còn lại (Foreign room) | MWG: 0,0% | Thông tin | Hết room: nhà đầu tư nước ngoài không mua thêm được | Trường remainForeignRoom, totalForeignRoom của SSI |
