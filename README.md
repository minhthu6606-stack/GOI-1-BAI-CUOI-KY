# [Tên sản phẩm – sẽ cập nhật]

Đồ án cá nhân cuối kỳ – Gói phần mềm ứng dụng cho tài chính 1 (UEL).
Sản phẩm: công cụ kiểm tra sức khỏe danh mục cổ phiếu cho nhà đầu tư cá nhân.
Nguồn dữ liệu: SSI FastConnect API v3, chỉ sử dụng quyền đọc dữ liệu thị trường (không đặt lệnh giao dịch).

> Đây là công cụ phân tích học thuật, không phải khuyến nghị đầu tư.

## Trạng thái
Giai đoạn 0: đã có lớp gọi API SSI và lớp chuẩn hóa dữ liệu kèm kiểm thử. Hướng dẫn đầy đủ (chạy ứng dụng, cấu trúc dữ liệu, giới hạn) sẽ được bổ sung ở các giai đoạn sau.

## Cài đặt (Windows, PowerShell)
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    Copy-Item .env.example .env   # rồi điền SSI_API_KEY, SSI_API_SECRET của bạn

## Các lệnh hiện có
    python scripts\check_ssi_connection.py   # kiểm tra kết nối và định dạng dữ liệu SSI
    python scripts\try_fetch.py              # tải thử 3 năm dữ liệu FPT, VN-Index và báo cáo chất lượng
    python -m pytest                         # chạy kiểm thử tự động (không cần mạng, không cần key)

## Cấu trúc mã nguồn
    src/config.py            cấu hình chung: đường dẫn, múi giờ, tham số SSI
    src/logging_setup.py     ghi nhật ký ra màn hình và logs/
    src/ssi_api/client.py    gọi SSI: xác thực, giới hạn tần suất, thử lại, lật trang
    src/data/normalize.py    chuẩn hóa dữ liệu và kiểm tra chất lượng
    tests/                   kiểm thử tự động
    scripts/                 các script chạy thủ công

## Bảo mật
- Không đưa file `.env` lên kho mã nguồn; tệp `.env.example` chỉ chứa tên biến.
- Chương trình chỉ lấy access token không kèm OTP, nên token chỉ có quyền đọc dữ liệu thị trường.
