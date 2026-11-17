"""
Các phần dùng chung của giao diện: biểu tượng, màu trạng thái, nhãn tiếng Việt, định dạng thời gian
và quy tắc "dữ liệu đã mới chưa". Tách khỏi main.py để kiểm thử được mà không cần chạy Streamlit.

Biểu tượng dùng bộ Material Symbols có sẵn trong Streamlit (dạng ":material/tên:"), KHÔNG dùng emoji.
Toàn bộ biểu tượng gom ở ICONS: muốn thay bằng biểu tượng tự thiết kế thì chỉ sửa một chỗ này.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from src import config
from src.finance.health import DANGER, GOOD, INFO, WARNING

# ---------------------------------------------------------------- biểu tượng (Material Symbols)
ICONS = {
    "app": ":material/monitor_heart:",
    "overview": ":material/space_dashboard:",
    "portfolio": ":material/edit_note:",
    "alerts": ":material/notifications_active:",
    "allocation": ":material/donut_large:",
    "risk": ":material/show_chart:",
    "liquidity": ":material/water_drop:",
    "market": ":material/candlestick_chart:",
    "method": ":material/menu_book:",
    "source": ":material/database:",
    "session": ":material/event:",
    "connection": ":material/link:",
    "update": ":material/sync:",
    "check": ":material/wifi_tethering:",
    "save": ":material/save:",
    "reset": ":material/restart_alt:",
    "upload": ":material/upload_file:",
    "action": ":material/lightbulb:",
}

# Màu của st.badge theo mức đánh giá (màu trạng thái chỉ dùng cho trạng thái, không dùng cho chuỗi dữ liệu)
STATUS_BADGE = {
    DANGER: ("red", ":material/error:"),
    WARNING: ("orange", ":material/warning:"),
    GOOD: ("green", ":material/check_circle:"),
    INFO: ("blue", ":material/info:"),
}

# ---------------------------------------------------------------- nhãn tiếng Việt cho bảng nhật ký
MODE_LABELS = {
    "full": "Tải toàn bộ lịch sử",
    "incremental": "Tải bổ sung phiên mới",
    "refresh": "Tải lại toàn bộ (SSI điều chỉnh giá)",
}
RESULT_LABELS = {"ok": "Thành công", "empty": "Không có dữ liệu", "error": "Lỗi"}
DATASET_LABELS = {"stock_daily": "Cổ phiếu", "index_daily": "Chỉ số", "market_summary": "Tổng hợp thị trường"}
KIND_LABELS = {"stock": "Cổ phiếu", "index": "Chỉ số"}


# ---------------------------------------------------------------- thời gian
def format_time(iso_text: str | None) -> str:
    """'2026-11-17T15:05:12+07:00' -> '17/11/2026 15:05' (giờ Việt Nam)."""
    if not iso_text:
        return "chưa có"
    try:
        return datetime.fromisoformat(iso_text).astimezone(config.VN_TZ).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso_text


def format_date(iso_date: str | None) -> str:
    """'2026-11-16' -> '16/11/2026'."""
    if not iso_date:
        return "chưa có"
    try:
        return datetime.fromisoformat(str(iso_date)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(iso_date)


def expected_latest_session(now: datetime) -> date:
    """Phiên gần nhất lẽ ra đã có dữ liệu chốt, tính theo ngày làm việc (thứ Hai–thứ Sáu).

    Trong ngày làm việc, sau SESSION_DATA_READY_HOUR giờ thì là hôm nay; trước giờ đó thì là ngày làm việc
    trước. Không biết lịch nghỉ lễ, nên chỉ dùng để quyết định "có nên hỏi SSI phiên mới không".
    """
    now = now.astimezone(config.VN_TZ)
    day = now.date()
    if day.weekday() < 5 and now.hour >= config.SESSION_DATA_READY_HOUR:
        return day
    day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def is_up_to_date(last_fetched_at: str | None, now: datetime) -> bool:
    """True nếu lần tải gần nhất diễn ra SAU thời điểm phiên gần nhất chốt dữ liệu.

    Dựa vào thời điểm tải chứ không dựa vào ngày phiên trong kho, nên ngày nghỉ lễ (không có phiên)
    không bị báo nhầm là dữ liệu cũ, miễn là đã hỏi SSI sau giờ chốt.
    """
    if not last_fetched_at:
        return False
    try:
        fetched = datetime.fromisoformat(last_fetched_at).astimezone(config.VN_TZ)
    except ValueError:
        return False
    session = expected_latest_session(now)
    ready = datetime.combine(session, time(config.SESSION_DATA_READY_HOUR), tzinfo=config.VN_TZ)
    return fetched >= ready
