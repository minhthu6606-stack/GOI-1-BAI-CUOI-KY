"""
Các phần dùng chung của giao diện: biểu tượng, màu trạng thái, nhãn tiếng Việt, định dạng thời gian
và quy tắc "dữ liệu đã mới chưa". Tách khỏi main.py để kiểm thử được mà không cần chạy Streamlit.

Biểu tượng dùng bộ Material Symbols có sẵn trong Streamlit (dạng ":material/tên:"), KHÔNG dùng emoji.
Toàn bộ biểu tượng gom ở ICONS: muốn thay bằng biểu tượng tự thiết kế thì chỉ sửa một chỗ này.
"""
from __future__ import annotations

from datetime import datetime

from src import config
from src.data.sessions import expected_latest_session, is_up_to_date  # noqa: F401 (dùng lại ở giao diện)
from src.finance.health import DANGER, GOOD, INFO, WARNING

# ---------------------------------------------------------------- biểu tượng (Material Symbols)
ICONS = {
    "app": ":material/monitor_heart:",
    "home": ":material/home:",
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
    "whatif": ":material/tune:",
    "add": ":material/add:",
    "delete": ":material/delete:",
    "profile": ":material/person_search:",
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
