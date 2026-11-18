"""
Cấu hình chung của dự án: đường dẫn thư mục, múi giờ và tham số gọi SSI API.

Mọi hằng số dùng ở nhiều nơi được gom về đây để khi cần đổi chỉ sửa một chỗ.
"""
from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

# ----- Sản phẩm (hiển thị ở Trang chủ, logo và tiêu đề tab trình duyệt) -----
APP_NAME = "Vốn Ổn"
APP_TAGLINE = "Khám vốn mỗi phiên, đầu tư an yên."      # slogan
APP_DESCRIPTOR = "Khám sức khỏe danh mục cổ phiếu"     # mô tả ngắn đi kèm tên
APP_GOAL = ("Bạn nhập những mã cổ phiếu đang có, ứng dụng chấm sức khỏe danh mục theo 4 câu hỏi: có đang dồn "
            "quá nhiều tiền vào một mã hay một ngành không, cần tiền gấp thì bán hết mất mấy ngày, danh mục lên "
            "xuống mạnh đến đâu so với thị trường, và một phiên giảm sàn có thể làm bạn mất bao nhiêu tiền")
APP_USERS = ("Nhà đầu tư cá nhân mới tham gia thị trường, đang nắm khoảng 3–10 mã cổ phiếu và muốn tự kiểm tra "
             "rủi ro trước khi quyết định mua thêm hay cơ cấu lại")

# ----- Đường dẫn -----
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"            # dữ liệu tải về (không đưa lên GitHub)
LOG_DIR = PROJECT_ROOT / "logs"             # nhật ký chạy chương trình (không đưa lên GitHub)
SAMPLE_DIR = PROJECT_ROOT / "data_sample"   # bản dữ liệu SSI lưu kèm mã nguồn (có đưa lên GitHub)
DB_PATH = DATA_DIR / "portfolio.db"         # kho SQLite
SAMPLE_DB_PATH = SAMPLE_DIR / "sample.db"   # bản chốt dữ liệu thật, dùng khi máy chưa có kho data/ và API key
DEMO_PORTFOLIO_PATH = SAMPLE_DIR / "demo_portfolio.csv"   # danh mục mặc định khi mở ứng dụng

# ----- Múi giờ: mọi dấu thời gian lưu và hiển thị theo giờ Việt Nam (yêu cầu Mục 4 của đề) -----
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# ----- SSI FastConnect API v3 -----
SSI_BASE_URL = "https://api.ssi.com.vn/api/v3"
SSI_MIN_INTERVAL_SECONDS = 1.1   # khoảng cách tối thiểu giữa 2 yêu cầu (~1 yêu cầu/giây)
SSI_TIMEOUT_SECONDS = 20         # chờ tối đa mỗi yêu cầu
SSI_MAX_RETRIES = 3              # số lần thử lại khi lỗi mạng / máy chủ bận
SSI_PAGE_SIZE = 100              # số bản ghi mỗi trang (quan sát: SSI trả tối đa 100)
SSI_MAX_PAGES = 50               # chốt an toàn, tránh vòng lặp lật trang vô hạn
SSI_MAX_DAYS_PER_REQUEST = 365   # endpoint ohlc: chia khoảng thời gian dài thành từng đoạn <= 1 năm
# Endpoint securitiesSummary KHÔNG lật trang được (xin trang 2 vẫn trả trang 1 - quan sát ngày 16/11/2026),
# nên chia đoạn 120 ngày: tối đa ~86 phiên/đoạn, luôn nằm gọn trong 1 trang 100 bản ghi.
SSI_SUMMARY_MAX_DAYS = 120

# ----- Cập nhật dữ liệu -----
DEFAULT_SYMBOLS = ["FPT", "HPG", "VCB", "MBB", "SSI", "MWG"]  # các mã của danh mục mặc định
# Các cổ phiếu vốn hóa lớn thêm vào dải giá chạy ngang (thuộc rổ VN30, nhiều ngành). Tải đủ lịch sử như mọi mã
# khác, nên người dùng thêm các mã này vào danh mục là phân tích được ngay.
TICKER_SYMBOLS = ["ACB", "BID", "CTG", "TCB", "VPB", "VNM", "MSN", "VIC", "VHM", "GAS"]
TRACKED_SYMBOLS = DEFAULT_SYMBOLS + [s for s in TICKER_SYMBOLS if s not in DEFAULT_SYMBOLS]
MARKET_INDEX = "VNINDEX"         # chỉ số thị trường: dùng làm lịch giao dịch chuẩn và để tính beta
HISTORY_YEARS = 3                # độ dài lịch sử tải lần đầu
OVERLAP_DAYS = 14                # mỗi lần cập nhật tải lại 14 ngày gần nhất để phát hiện giá lịch sử bị điều chỉnh
PRICE_ADJUST_TOLERANCE = 0.001   # lệch > 0,1% giữa giá đã lưu và giá mới tải => SSI đã điều chỉnh lại lịch sử
BOARDS = ("HOSE", "HNX", "UPCOM")
SECURITIES_MAX_AGE_DAYS = 7      # danh sách mã (ngành, số cổ phiếu niêm yết) làm mới mỗi tuần
MARKET_SUMMARY_SESSIONS = 20     # lưu tổng hợp thị trường (độ rộng, khối ngoại) cho 20 phiên gần nhất
SESSION_DATA_READY_HOUR = 15     # sau 15:00 coi như dữ liệu phiên trong ngày đã chốt (HOSE đóng cửa 14:45)
AUTO_UPDATE_ON_OPEN = True       # có API key + có kho data/ => mở ứng dụng tự tải phiên mới (mỗi phiên tối đa 1 lần)

# Định dạng ngày SSI chấp nhận - dò bằng scripts/check_ssi_connection.py ngày 16/11/2026
SSI_DATE_FORMAT_SUMMARY = "%Y/%m/%d"           # endpoint securitiesSummary, indexSummary
SSI_DATE_FORMAT_OHLC = "%Y/%m/%d %H:%M:%S"     # endpoint ohlc
