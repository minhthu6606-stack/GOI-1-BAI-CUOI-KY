"""
Cấu hình chung của dự án: đường dẫn thư mục, múi giờ và tham số gọi SSI API.

Mọi hằng số dùng ở nhiều nơi được gom về đây để khi cần đổi chỉ sửa một chỗ.
"""
from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

# ----- Đường dẫn -----
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"            # dữ liệu tải về (không đưa lên GitHub)
LOG_DIR = PROJECT_ROOT / "logs"             # nhật ký chạy chương trình (không đưa lên GitHub)
SAMPLE_DIR = PROJECT_ROOT / "data_sample"   # dữ liệu mẫu cho người chấm (có đưa lên GitHub)
DB_PATH = DATA_DIR / "portfolio.db"         # kho SQLite

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
DEFAULT_SYMBOLS = ["FPT", "HPG", "VCB", "MBB", "SSI", "MWG"]  # các mã của danh mục minh họa
MARKET_INDEX = "VNINDEX"         # chỉ số thị trường: dùng làm lịch giao dịch chuẩn và để tính beta
HISTORY_YEARS = 3                # độ dài lịch sử tải lần đầu
OVERLAP_DAYS = 14                # mỗi lần cập nhật tải lại 14 ngày gần nhất để phát hiện giá lịch sử bị điều chỉnh
PRICE_ADJUST_TOLERANCE = 0.001   # lệch > 0,1% giữa giá đã lưu và giá mới tải => SSI đã điều chỉnh lại lịch sử
BOARDS = ("HOSE", "HNX", "UPCOM")
SECURITIES_MAX_AGE_DAYS = 7      # danh sách mã (ngành, số cổ phiếu niêm yết) làm mới mỗi tuần

# Định dạng ngày SSI chấp nhận - dò bằng scripts/check_ssi_connection.py ngày 16/11/2026
SSI_DATE_FORMAT_SUMMARY = "%Y/%m/%d"           # endpoint securitiesSummary, indexSummary
SSI_DATE_FORMAT_OHLC = "%Y/%m/%d %H:%M:%S"     # endpoint ohlc
