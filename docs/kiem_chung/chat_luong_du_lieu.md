# Chất lượng dữ liệu

Tạo lúc 20/11/2026 23:58 (giờ Việt Nam) từ kho `data\portfolio.db`.

Đối chiếu: lợi suất tự tính từ giá đóng cửa đã điều chỉnh so với `priceChangePercentage` do SSI công bố; lệch quá 1 điểm phần trăm thì đếm là lệch. Phiên thiếu tính theo lịch giao dịch của VN-Index.

| Mã | Số phiên | Từ ngày | Đến ngày | Phiên thiếu | Dòng bị gắn cờ | Phiên có giá đã điều chỉnh | Số phiên đối chiếu | Lệch > 1 điểm % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FPT | 748 | 2023-11-20 | 2026-11-20 | 0 | 0 | 703 | 747 | 0 |
| HPG | 748 | 2023-11-20 | 2026-11-20 | 0 | 0 | 621 | 747 | 0 |
| VCB | 748 | 2023-11-20 | 2026-11-20 | 0 | 0 | 662 | 747 | 0 |
| MBB | 748 | 2023-11-20 | 2026-11-20 | 0 | 0 | 676 | 747 | 0 |
| SSI | 748 | 2023-11-20 | 2026-11-20 | 0 | 0 | 681 | 747 | 0 |
| MWG | 748 | 2023-11-20 | 2026-11-20 | 0 | 0 | 711 | 747 | 0 |
| ACB | 748 | 2023-11-20 | 2026-11-20 | 0 | 0 | 620 | 747 | 1 |
| BID | 748 | 2023-11-20 | 2026-11-20 | 0 | 0 | 670 | 747 | 0 |
| CTG | 748 | 2023-11-20 | 2026-11-20 | 0 | 0 | 651 | 747 | 0 |
| TCB | 748 | 2023-11-20 | 2026-11-20 | 0 | 0 | 731 | 747 | 0 |
| VPB | 748 | 2023-11-20 | 2026-11-20 | 0 | 0 | 701 | 747 | 0 |
| VNM | 748 | 2023-11-20 | 2026-11-20 | 0 | 0 | 736 | 747 | 0 |
| MSN | 748 | 2023-11-20 | 2026-11-20 | 0 | 0 | 0 | 747 | 0 |
| VIC | 748 | 2023-11-20 | 2026-11-20 | 0 | 0 | 0 | 747 | 0 |
| VHM | 748 | 2023-11-20 | 2026-11-20 | 0 | 0 | 565 | 747 | 0 |
| GAS | 748 | 2023-11-20 | 2026-11-20 | 0 | 0 | 694 | 747 | 0 |

**Tổng:** 16 mã, 0 phiên thiếu, 1 phiên lệch.

## Chi tiết các phiên lệch

Cột cuối khác 1 rõ rệt nghĩa là giá tham chiếu của sở khác giá đóng cửa phiên trước trong chuỗi đã điều chỉnh, tức là có điều chỉnh giá (vd ngày giao dịch không hưởng quyền). Cần tra lịch sự kiện của mã để xác nhận.

| Mã | Ngày | Đóng cửa phiên trước (đã điều chỉnh) | Đóng cửa | Lợi suất tự tính (%) | % thay đổi SSI | Giá tham chiếu SSI / đóng cửa trước |
| --- | --- | --- | --- | --- | --- | --- |
| ACB | 2025-07-03 | 18.352,08 | 18.438,24 | 0,47 | -1,41 | 1,0191 |
