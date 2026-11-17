# Khám Sức Khỏe Danh Mục

Đồ án cá nhân cuối kỳ – Gói phần mềm ứng dụng cho tài chính 1 (UEL).
Sản phẩm: công cụ kiểm tra sức khỏe danh mục cổ phiếu cho nhà đầu tư cá nhân.
Nguồn dữ liệu: SSI FastConnect API v3, chỉ sử dụng quyền đọc dữ liệu thị trường (không đặt lệnh giao dịch).

> Đây là công cụ phân tích học thuật, không phải khuyến nghị đầu tư.

## Trạng thái
Đã có: lớp gọi API SSI, chuẩn hóa và kiểm tra chất lượng dữ liệu, kho SQLite, script cập nhật dữ liệu,
lớp tính toán tài chính (tập trung, thanh khoản, rủi ro thị trường, kịch bản giảm sàn), ứng dụng Streamlit,
kiểm thử tự động. Đang làm: kiểm định VaR ngoài mẫu và hoàn thiện tài liệu.

## Chạy nhanh KHÔNG cần API key (dành cho người chấm)
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    streamlit run src\app\main.py

Ở thanh bên trái, chọn **Dữ liệu mẫu (không cần API key)**. Dữ liệu mẫu (`data_sample/sample.db`) là dữ liệu THẬT
tải từ SSI và chốt ở một ngày; giao diện ghi rõ ngày chốt.

## Cài đặt (Windows, PowerShell)
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    Copy-Item .env.example .env   # rồi điền SSI_API_KEY, SSI_API_SECRET của bạn

## Chạy với dữ liệu trực tiếp từ SSI
    python scripts\update_data.py            # tải/cập nhật dữ liệu danh mục minh họa vào data/portfolio.db
    python scripts\update_data.py --symbols FPT ACB   # tải/cập nhật các mã chỉ định
    python scripts\update_data.py --status   # xem kho đang có gì và nhật ký cập nhật, không tải
    python scripts\make_demo_portfolio.py    # tạo danh mục minh họa data_sample\demo_portfolio.csv theo giá mới nhất
    python scripts\portfolio_report.py       # in báo cáo sức khỏe danh mục ra màn hình
    python scripts\export_sample.py          # xuất dữ liệu mẫu data_sample\sample.db cho người chấm
    streamlit run src\app\main.py            # mở ứng dụng (chọn "Dữ liệu trực tiếp (SSI)")
    python scripts\check_ssi_connection.py   # kiểm tra kết nối và định dạng dữ liệu SSI
    python scripts\try_fetch.py              # tải thử 3 năm dữ liệu FPT, VN-Index và báo cáo chất lượng
    python -m pytest                         # chạy kiểm thử tự động (không cần mạng, không cần key)

Lần đầu `update_data.py` tải đủ 3 năm; các lần sau chỉ tải phần mới. Nên chạy sau 15:00 để có giá đóng cửa cuối phiên.

## Cấu trúc mã nguồn
    src/config.py            cấu hình chung: đường dẫn, múi giờ, tham số SSI
    src/logging_setup.py     ghi nhật ký ra màn hình và logs/
    src/ssi_api/client.py    gọi SSI: xác thực, giới hạn tần suất, thử lại, lật trang
    src/data/normalize.py    chuẩn hóa dữ liệu và kiểm tra chất lượng
    src/data/storage.py      kho SQLite: dữ liệu theo phiên, danh sách mã, response thô, nhật ký cập nhật
    src/data/updater.py      tải lần đầu, cập nhật phần mới, phát hiện giá lịch sử bị điều chỉnh
    src/finance/portfolio.py      đọc, kiểm tra và định giá danh mục
    src/finance/market_data.py    đọc dữ liệu thị trường từ kho cho lớp tài chính
    src/finance/concentration.py  mức tập trung theo mã và ngành (HHI, số mã hiệu dụng, quy tắc 5/10/40)
    src/finance/liquidity.py      thanh khoản: số ngày bán hết và có tiền (SEC Rule 22e-4, T+2)
    src/finance/risk.py           biến động, beta, VaR lịch sử, mức sụt giảm tối đa
    src/finance/stress.py         kịch bản mọi mã giảm sàn (biên độ, bước giá)
    src/finance/health.py         tổng hợp báo cáo sức khỏe, ngưỡng và lời giải thích
    src/app/main.py               ứng dụng Streamlit (giao diện)
    src/app/charts.py             các biểu đồ Plotly
    tests/                   kiểm thử tự động
    scripts/                 các script chạy thủ công

## Bảo mật
- Không đưa file `.env` lên kho mã nguồn; tệp `.env.example` chỉ chứa tên biến.
- Chương trình chỉ lấy access token không kèm OTP, nên token chỉ có quyền đọc dữ liệu thị trường.
