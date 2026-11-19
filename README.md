# Vốn Ổn – khám sức khỏe danh mục cổ phiếu

> *Khám vốn mỗi phiên, đầu tư an yên.*

Đồ án cá nhân cuối kỳ – Gói phần mềm ứng dụng cho tài chính 1 (UEL).
Sản phẩm: công cụ kiểm tra sức khỏe danh mục cổ phiếu cho nhà đầu tư cá nhân.
Nguồn dữ liệu: SSI FastConnect API v3, chỉ sử dụng quyền đọc dữ liệu thị trường (không đặt lệnh giao dịch).

> Đây là công cụ phân tích học thuật, không phải khuyến nghị đầu tư.

## Trạng thái
Đã có: lớp gọi API SSI, chuẩn hóa và kiểm tra chất lượng dữ liệu, kho SQLite, script cập nhật dữ liệu,
lớp tính toán tài chính (tập trung, thanh khoản, rủi ro thị trường, kịch bản giảm sàn), ứng dụng Streamlit,
kiểm thử tự động, kiểm định VaR ngoài mẫu (Kupiec, Christoffersen), nhật ký thu thập theo phiên và kịch bản thử lỗi. Đang làm: báo cáo và video.

## Chạy nhanh KHÔNG cần API key (dành cho người chấm)
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    streamlit run src\app\main.py

Máy chưa có kho `data/` thì ứng dụng tự dùng bản dữ liệu SSI lưu kèm mã nguồn (`data_sample/sample.db`): đây là
dữ liệu THẬT tải từ SSI, chốt đến một phiên; thanh bên ghi rõ phiên chốt. Không cần chọn gì thêm.

## Giao diện
Tông tím - vàng gold, phông Montserrat. Mặc định giao diện sáng; mục **Cài đặt → Giao diện tối** ở cuối thanh bên để
chuyển sáng/tối. Mở ứng dụng là **Trang chủ** (giới thiệu, hình minh họa động, 4 điều được kiểm tra, 3 bước sử dụng,
câu hỏi thường gặp). Đầu mỗi trang có dải giá chạy ngang: VN-Index, các mã trong danh mục và 10 cổ phiếu vốn hóa lớn
(`TICKER_SYMBOLS` trong `src/config.py`), lấy giá đóng cửa phiên mới nhất trong kho.
Thanh bên trái là menu: **Trang chủ**, **Nhập danh mục**, **Tổng quan** (kết luận và 6 chỉ số chính), **Cảnh báo**,
**Phân bổ**, **Rủi ro**, **Thanh khoản & giảm sàn**, **Thị trường**, **Phương pháp & dữ liệu**. Dưới menu là khung
**Dữ liệu**: nguồn, phiên mới nhất, thời điểm tải, trạng thái kết nối và hai nút *Kiểm tra kết nối*, *Cập nhật dữ liệu*.
Máy có API key và có kho `data/`: mở ứng dụng sau 15:00 ngày làm việc sẽ tự tải phiên mới (mỗi phiên một lần).

## Cài đặt (Windows, PowerShell)
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    Copy-Item .env.example .env   # rồi điền SSI_API_KEY, SSI_API_SECRET của bạn

## Chạy với dữ liệu trực tiếp từ SSI
    python scripts\update_data.py            # tải/cập nhật dữ liệu các mã mặc định vào data/portfolio.db
    python scripts\update_data.py --symbols FPT ACB   # tải/cập nhật các mã chỉ định
    python scripts\update_data.py --status   # xem kho đang có gì và nhật ký cập nhật, không tải
    python scripts\make_demo_portfolio.py    # tạo danh mục mặc định data_sample\demo_portfolio.csv theo giá mới nhất
    python scripts\portfolio_report.py       # in báo cáo sức khỏe danh mục ra màn hình
    python scripts\export_sample.py          # xuất bản dữ liệu SSI data_sample\sample.db để đưa lên GitHub
    streamlit run src\app\main.py            # mở ứng dụng
    python scripts\check_ssi_connection.py   # kiểm tra kết nối và định dạng dữ liệu SSI
    python scripts\try_fetch.py              # tải thử 3 năm dữ liệu FPT, VN-Index và báo cáo chất lượng
    python -m pytest                         # chạy kiểm thử tự động (không cần mạng, không cần key)

Lần đầu `update_data.py` tải đủ 3 năm cho 16 mã (6 mã danh mục mặc định + 10 mã của dải giá, khoảng 2–3 phút);
các lần sau chỉ tải phần mới, kèm tổng hợp thị trường HOSE của 20 phiên gần nhất. Nên chạy sau 15:00 để có giá đóng
cửa cuối phiên.

## Kiểm thử và kiểm chứng
    python -m pytest                              # 100 kiểm thử tự động (không cần mạng, không cần key)
    python scripts\verification_report.py         # chất lượng dữ liệu, nhật ký thu thập, kiểm định VaR -> docs\kiem_chung\
    python scripts\test_error_scenarios.py        # thử 9 tình huống lỗi -> docs\kiem_chung\thu_loi.md
    python scripts\update_data.py --sessions      # in nhật ký thu thập theo phiên

Dữ liệu theo phiên, không cần ghi thời gian thực: mỗi lần cập nhật tải lại từ (phiên cuối trong kho − 14 ngày) đến
hôm nay, nên nghỉ nhiều ngày không mở máy thì lần sau vẫn tải bù đủ (tình huống 8 của script thử lỗi); tải trong giờ
giao dịch thì giá tạm được thay bằng giá đóng cửa ở lần tải sau 15:00 (tình huống 9).

Kiểm định VaR: tính lại VaR 95% cho từng ngày trong quá khứ (mỗi ngày chỉ dùng 250 phiên trước đó), đếm số ngày lỗ
thực tế vượt VaR, rồi kiểm định Kupiec (1995) cho tỷ lệ vượt và Christoffersen (1998) cho tính độc lập. Kết quả hiện
ở trang Phương pháp & dữ liệu và trong mục Cảnh báo.

Tự cập nhật hằng ngày không cần mở ứng dụng (tùy chọn, Windows):
`powershell -ExecutionPolicy Bypass -File scripts\dang_ky_cap_nhat_tu_dong.ps1` (15:30 thứ Hai–thứ Sáu; máy tắt thì
chạy bù khi bật lại).

## Cấu trúc mã nguồn
    src/config.py            cấu hình chung: đường dẫn, múi giờ, tham số SSI
    src/logging_setup.py     ghi nhật ký ra màn hình và logs/
    src/ssi_api/client.py    gọi SSI: xác thực, giới hạn tần suất, thử lại, lật trang
    src/data/normalize.py    chuẩn hóa dữ liệu và kiểm tra chất lượng
    src/data/storage.py      kho SQLite: dữ liệu theo phiên, danh sách mã, response thô, nhật ký cập nhật
    src/data/updater.py      tải lần đầu, cập nhật phần mới, phát hiện giá lịch sử bị điều chỉnh
    src/data/sessions.py     lịch phiên: phiên gần nhất đã chốt dữ liệu, dữ liệu đã mới chưa
    src/data/quality.py      nhật ký thu thập theo phiên, bảng chất lượng dữ liệu từng mã
    src/finance/portfolio.py      đọc, kiểm tra và định giá danh mục
    src/finance/market_data.py    đọc dữ liệu thị trường từ kho cho lớp tài chính
    src/finance/concentration.py  mức tập trung theo mã và ngành (HHI, số mã hiệu dụng, quy tắc 5/10/40)
    src/finance/liquidity.py      thanh khoản: số ngày bán hết và có tiền (SEC Rule 22e-4, T+2)
    src/finance/risk.py           biến động, beta, VaR lịch sử, mức sụt giảm tối đa
    src/finance/stress.py         kịch bản mọi mã giảm sàn (biên độ, bước giá)
    src/finance/health.py         tổng hợp báo cáo sức khỏe, ngưỡng và lời giải thích
    src/finance/backtest.py       kiểm định ngoài mẫu VaR (Kupiec, Christoffersen)
    src/app/main.py               ứng dụng Streamlit: chọn nguồn dữ liệu, tính toán chung, menu điều hướng, khung Dữ liệu
    src/app/views.py              nội dung từng trang
    src/app/charts.py             các biểu đồ Plotly (có tương tác: rê chuột, phóng to, thanh trượt thời gian)
    src/app/ui.py                 biểu tượng, nhãn tiếng Việt, quy tắc "dữ liệu đã mới chưa"
    src/app/style.py              CSS bổ sung, dải giá chạy ngang, hình minh họa trang chủ (SVG tự vẽ)
    src/app/assets/               logo của sản phẩm (SVG, bản sáng và bản tối)
    .streamlit/config.toml        màu giao diện sáng/tối, phông chữ (Montserrat), bo góc
    tests/                   kiểm thử tự động
    scripts/                 các script chạy thủ công

## Bảo mật
- Không đưa file `.env` lên kho mã nguồn; tệp `.env.example` chỉ chứa tên biến.
- Chương trình chỉ lấy access token không kèm OTP, nên token chỉ có quyền đọc dữ liệu thị trường.
