"""
Lịch phiên giao dịch: phiên gần nhất lẽ ra đã có dữ liệu chốt, và dữ liệu trong kho đã mới chưa.

Dùng chung cho giao diện (nhãn "mới nhất", tự cập nhật khi mở ứng dụng) và cho báo cáo nhật ký thu thập.
Chỉ dựa trên ngày làm việc (thứ Hai–thứ Sáu) và giờ chốt dữ liệu; không biết lịch nghỉ lễ.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from src import config


def expected_latest_session(now: datetime) -> date:
    """Phiên gần nhất lẽ ra đã chốt dữ liệu: hôm nay nếu là ngày làm việc và đã qua giờ chốt, không thì ngày làm việc trước."""
    now = now.astimezone(config.VN_TZ)
    day = now.date()
    if day.weekday() < 5 and now.hour >= config.SESSION_DATA_READY_HOUR:
        return day
    day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def is_up_to_date(last_fetched_at: str | None, now: datetime) -> bool:
    """True nếu lần tải gần nhất diễn ra SAU giờ chốt của phiên gần nhất (ngày lễ không bị báo nhầm là cũ)."""
    if not last_fetched_at:
        return False
    try:
        fetched = datetime.fromisoformat(last_fetched_at).astimezone(config.VN_TZ)
    except ValueError:
        return False
    session = expected_latest_session(now)
    ready = datetime.combine(session, time(config.SESSION_DATA_READY_HOUR), tzinfo=config.VN_TZ)
    return fetched >= ready
