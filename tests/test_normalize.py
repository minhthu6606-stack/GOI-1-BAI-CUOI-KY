"""Kiểm thử cho src/data/normalize.py - các ví dụ đều tính tay được."""
import pandas as pd
import pytest

from src.data.normalize import (
    find_missing_sessions,
    normalize_index_daily,
    normalize_stock_daily,
    parse_ssi_date,
    to_float,
)


def make_record(day: str, close: str, high: str = "52000", low: str = "50000", pct: str = "1") -> dict:
    """Tạo một bản ghi giả theo đúng dạng securitiesSummary của SSI (mọi số là chuỗi)."""
    return {
        "tradingDate": day, "open": "51000", "high": high, "low": low, "close": close,
        "priceChange": "500", "priceChangePercentage": pct,
        "totalMatch": "1000000", "totalMatchValue": "51000000000",
    }


class TestParseSsiDate:
    def test_ssi_format(self):
        assert parse_ssi_date("2026/11/09") == "2026-11-09"

    def test_other_formats(self):
        assert parse_ssi_date("2026-11-09") == "2026-11-09"
        assert parse_ssi_date("09/11/2026") == "2026-11-09"

    def test_invalid(self):
        assert parse_ssi_date("") is None
        assert parse_ssi_date(None) is None
        assert parse_ssi_date("ngày lạ") is None


class TestToFloat:
    def test_numeric_strings(self):
        assert to_float("51000") == 51000.0
        assert to_float("913844751371.7") == pytest.approx(913844751371.7)
        assert to_float("1,234") == 1234.0

    def test_empty_values(self):
        for value in (None, "", "  ", "null", "NaN", "abc"):
            assert to_float(value) is None


class TestNormalizeStockDaily:
    def test_sorted_and_reference_price(self):
        records = [make_record("2026/11/10", "50500", pct="1"), make_record("2026/11/09", "50000", pct="-2")]
        frame, report = normalize_stock_daily(records, "FPT")
        assert list(frame["trading_date"]) == ["2026-11-09", "2026-11-10"]
        # giá tham chiếu = giá đóng cửa / (1 + %thay đổi): 50000 / 0.98 = 51020.41 ; 50500 / 1.01 = 50000
        assert frame.loc[0, "reference_price"] == pytest.approx(51020.408, rel=1e-6)
        assert frame.loc[1, "reference_price"] == pytest.approx(50000.0)
        assert report.kept == 2 and report.total == 2

    def test_reference_price_same_scale_as_adjusted_close(self):
        # Giá đã điều chỉnh (lẻ thập phân) + phần trăm thay đổi -> giá tham chiếu cùng thang
        frame, _ = normalize_stock_daily([make_record("2026/04/14", "68331.301", high="69000", pct="0.29")], "FPT")
        assert frame.loc[0, "reference_price"] == pytest.approx(68331.301 / 1.0029)

    def test_missing_percentage_gives_empty_reference(self):
        frame, report = normalize_stock_daily([make_record("2026/11/09", "50000", pct="")], "FPT")
        assert pd.isna(frame.loc[0, "reference_price"])
        assert report.notes

    def test_drop_duplicate_keeps_last(self):
        records = [make_record("2026/11/09", "50000"), make_record("2026/11/09", "50600")]
        frame, report = normalize_stock_daily(records, "FPT")
        assert len(frame) == 1
        assert frame.loc[0, "close"] == 50600.0
        assert report.dropped_duplicate == 1

    def test_drop_missing_and_non_positive_close(self):
        records = [make_record("2026/11/09", ""), make_record("", "50000"), make_record("2026/11/10", "0"),
                   make_record("2026/11/11", "50500")]
        frame, report = normalize_stock_daily(records, "FPT")
        assert list(frame["trading_date"]) == ["2026-11-11"]
        assert report.dropped_missing == 2
        assert report.dropped_invalid == 1

    def test_flag_close_outside_high_low(self):
        records = [make_record("2026/11/09", "53000", high="52000", low="50000")]
        frame, report = normalize_stock_daily(records, "FPT")
        assert len(frame) == 1  # đánh dấu chứ không loại
        assert frame.loc[0, "quality_flag"] == "close_outside_high_low"
        assert report.flagged == 1

    def test_empty_input(self):
        frame, report = normalize_stock_daily([], "FPT")
        assert frame.empty
        assert "reference_price" in frame.columns
        assert report.total == 0


def test_normalize_index_daily():
    records = [
        {"tradingDate": "2026/11/16", "open": "1733.71", "high": "1753.01", "low": "1733.71", "close": "1736.89",
         "volume": "526138530", "value": "913844751371.7"},
        {"tradingDate": "2026/11/13", "open": "1730", "high": "1740", "low": "1725", "close": "1734.93",
         "volume": "1", "value": "1"},
    ]
    frame, report = normalize_index_daily(records, "VNINDEX")
    assert list(frame["trading_date"]) == ["2026-11-13", "2026-11-16"]
    assert frame.loc[1, "close"] == pytest.approx(1736.89)
    assert report.kept == 2


def test_find_missing_sessions_against_calendar():
    calendar = ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"]
    records = [make_record("2026/11/10", "50000"), make_record("2026/11/13", "50000")]
    frame, _ = normalize_stock_daily(records, "FPT")
    # Chỉ xét từ phiên đầu (10/11) đến phiên cuối (13/11) của mã -> thiếu 11/11 và 12/11
    assert find_missing_sessions(frame, calendar) == ["2026-11-11", "2026-11-12"]


def test_find_missing_sessions_empty_frame():
    frame, _ = normalize_stock_daily([], "FPT")
    assert find_missing_sessions(frame, ["2026-11-09"]) == []
