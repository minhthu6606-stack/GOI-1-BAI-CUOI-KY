# Chất lượng dữ liệu

Tạo lúc 20/11/2026 00:53 (giờ Việt Nam) từ kho `data\portfolio.db`.

Đối chiếu: lợi suất tự tính từ giá đóng cửa đã điều chỉnh so với `priceChangePercentage` do SSI công bố; lệch quá 1 điểm phần trăm thì đếm là lệch. Phiên thiếu tính theo lịch giao dịch của VN-Index.

| Mã | Số phiên | Từ ngày | Đến ngày | Phiên thiếu | Dòng bị gắn cờ | Phiên có giá đã điều chỉnh | Số phiên đối chiếu | Lệch > 1 điểm % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FPT | 747 | 2023-11-20 | 2026-11-19 | 0 | 0 | 703 | 746 | 0 |
| HPG | 747 | 2023-11-20 | 2026-11-19 | 0 | 0 | 621 | 746 | 0 |
| VCB | 747 | 2023-11-20 | 2026-11-19 | 0 | 0 | 662 | 746 | 0 |
| MBB | 747 | 2023-11-20 | 2026-11-19 | 0 | 0 | 676 | 746 | 0 |
| SSI | 747 | 2023-11-20 | 2026-11-19 | 0 | 0 | 681 | 746 | 0 |
| MWG | 747 | 2023-11-20 | 2026-11-19 | 0 | 0 | 711 | 746 | 0 |
| ACB | 747 | 2023-11-20 | 2026-11-19 | 0 | 0 | 620 | 746 | 1 |
| BID | 747 | 2023-11-20 | 2026-11-19 | 0 | 0 | 670 | 746 | 0 |
| CTG | 747 | 2023-11-20 | 2026-11-19 | 0 | 0 | 651 | 746 | 0 |
| TCB | 747 | 2023-11-20 | 2026-11-19 | 0 | 0 | 731 | 746 | 0 |
| VPB | 747 | 2023-11-20 | 2026-11-19 | 0 | 0 | 701 | 746 | 0 |
| VNM | 747 | 2023-11-20 | 2026-11-19 | 0 | 0 | 736 | 746 | 0 |
| MSN | 747 | 2023-11-20 | 2026-11-19 | 0 | 0 | 0 | 746 | 0 |
| VIC | 747 | 2023-11-20 | 2026-11-19 | 0 | 0 | 0 | 746 | 0 |
| VHM | 747 | 2023-11-20 | 2026-11-19 | 0 | 0 | 565 | 746 | 0 |
| GAS | 747 | 2023-11-20 | 2026-11-19 | 0 | 0 | 694 | 746 | 0 |

**Tổng:** 16 mã, 0 phiên thiếu, 1 phiên lệch.

## Chi tiết các phiên lệch

Cột cuối khác 1 rõ rệt nghĩa là giá tham chiếu của sở khác giá đóng cửa phiên trước trong chuỗi đã điều chỉnh, tức là có điều chỉnh giá (vd ngày giao dịch không hưởng quyền). Cần tra lịch sự kiện của mã để xác nhận.

| Mã | Ngày | Đóng cửa phiên trước (đã điều chỉnh) | Đóng cửa | Lợi suất tự tính (%) | % thay đổi SSI | Giá tham chiếu SSI / đóng cửa trước |
| --- | --- | --- | --- | --- | --- | --- |
| ACB | 2025-07-03 | 18.352,08 | 18.438,24 | 0,47 | -1,41 | 1,0191 |
