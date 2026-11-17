"""Kiểm thử src/app/ui.py: quy tắc "dữ liệu đã mới chưa" và nhãn tiếng Việt."""
from datetime import date, datetime

from src import config
from src.app.ui import (
    MODE_LABELS, RESULT_LABELS, expected_latest_session, format_date, format_time, is_up_to_date,
)

VN = config.VN_TZ


def test_expected_session_before_and_after_close():
    assert expected_latest_session(datetime(2026, 11, 17, 11, 0, tzinfo=VN)) == date(2026, 11, 16)  # thứ Ba, trước 15h
    assert expected_latest_session(datetime(2026, 11, 17, 15, 30, tzinfo=VN)) == date(2026, 11, 17)  # sau 15h


def test_expected_session_skips_weekend():
    assert expected_latest_session(datetime(2026, 11, 22, 10, 0, tzinfo=VN)) == date(2026, 11, 20)  # Chủ nhật
    assert expected_latest_session(datetime(2026, 11, 23, 9, 0, tzinfo=VN)) == date(2026, 11, 20)   # sáng thứ Hai


def test_is_up_to_date_uses_fetch_time():
    now = datetime(2026, 11, 17, 11, 0, tzinfo=VN)
    assert is_up_to_date("2026-11-17T00:00:38+07:00", now)        # tải sau 15h ngày 16 -> mới
    assert not is_up_to_date("2026-11-16T14:00:00+07:00", now)    # tải trước giờ chốt -> cũ
    assert not is_up_to_date(None, now)
    later = datetime(2026, 11, 17, 16, 0, tzinfo=VN)
    assert not is_up_to_date("2026-11-17T00:00:38+07:00", later)  # đã qua 15h ngày 17 -> cần tải phiên 17


def test_vietnamese_labels_and_formats():
    assert MODE_LABELS["incremental"] == "Tải bổ sung phiên mới"
    assert RESULT_LABELS["ok"] == "Thành công"
    assert format_date("2026-11-16") == "16/11/2026"
    assert format_time("2026-11-17T00:00:38+07:00") == "17/11/2026 00:00"
