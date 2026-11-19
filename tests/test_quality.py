"""Kiểm thử src/data/quality.py và src/data/sessions.py: nhật ký thu thập theo phiên, bảng chất lượng."""
import pandas as pd
import pytest

from src.data.normalize import normalize_stock_daily
from src.data.quality import collection_summary, quality_table, sessions_collected
from src.data.storage import Storage


def log_rows(run_id, started, statuses):
    return [{"run_id": run_id, "started_at": started, "symbol": f"M{i}", "status": s} for i, s in enumerate(statuses)]


def test_collection_summary_maps_runs_to_sessions():
    log = pd.DataFrame(
        log_rows("a", "2026-11-17T00:00:38+07:00", ["ok", "ok"])       # nửa đêm -> phiên 16/11, tải bù
        + log_rows("b", "2026-11-17T15:20:00+07:00", ["ok", "error"])  # sau 15h -> phiên 17/11, đúng ngày
        + log_rows("c", "2026-11-18T10:00:00+07:00", ["error", "error"])  # trước 15h, lỗi hết
    )
    summary = collection_summary(log)
    assert summary["run_id"].tolist() == ["c", "b", "a"]              # mới nhất ở trên
    row_b = summary[summary["run_id"] == "b"].iloc[0]
    assert row_b["session"] == "2026-11-17" and bool(row_b["on_time"]) and row_b["error"] == 1
    row_a = summary[summary["run_id"] == "a"].iloc[0]
    assert row_a["session"] == "2026-11-16" and not bool(row_a["on_time"])
    assert sessions_collected(summary) == ["2026-11-16", "2026-11-17"]  # lần c lỗi hết nên không tính


def test_collection_summary_empty():
    assert collection_summary(pd.DataFrame()).empty
    assert sessions_collected(pd.DataFrame()) == []


def test_normalize_handles_all_empty_numeric_column():
    rows = [{"tradingDate": "2026/11/17", "close": "50000"}, {"tradingDate": "2026/11/18", "close": None}]
    frame, report = normalize_stock_daily(rows, "TEST")             # high/low trống toàn bộ: không lỗi kiểu dữ liệu
    assert report.kept == 1 and report.dropped_missing == 1 and frame["close"].dtype == float


@pytest.fixture
def storage(tmp_path):
    with Storage(tmp_path / "q.db") as store:
        yield store


def test_quality_table_counts_missing_and_cross_check(storage):
    days = ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19"]
    index = pd.DataFrame({"symbol": "VNINDEX", "trading_date": days, "close": [1700.0] * 4})
    storage.upsert_daily("index_daily", index, fetched_at="2026-11-19T16:00:00+07:00")
    stock = pd.DataFrame({"symbol": "AAA", "trading_date": ["2026-11-16", "2026-11-17", "2026-11-19"],
                          "close": [100.0, 101.0, 110.0], "price_change_pct": [0.0, 1.0, 1.0]})
    storage.upsert_daily("stock_daily", stock, fetched_at="2026-11-19T16:00:00+07:00")
    table = quality_table(storage, ["AAA"]).iloc[0]
    assert table["sessions"] == 3 and table["missing"] == 1             # thiếu phiên 18/11
    assert table["cross_checked"] == 2 and table["cross_mismatch"] == 1  # 101->110 là +8,9% nhưng SSI ghi 1%


def test_collection_summary_skips_holidays_with_calendar():
    # 02/09/2026 (thứ Tư) là ngày lễ: lần tải chiều hôm đó phải tính cho phiên giao dịch thật gần nhất (28/08)
    log = pd.DataFrame(log_rows("h", "2026-09-02T16:00:00+07:00", ["ok"]))
    calendar = ["2026-08-27", "2026-08-28", "2026-09-03"]
    assert collection_summary(log)["session"].iloc[0] == "2026-09-02"            # không có lịch: chỉ biết ngày làm việc
    assert collection_summary(log, calendar)["session"].iloc[0] == "2026-08-28"  # có lịch thật: bỏ qua ngày lễ


def test_quality_table_tolerates_missing_reported_change(storage):
    index = pd.DataFrame({"symbol": "VNINDEX", "trading_date": ["2026-11-18", "2026-11-19"], "close": [1700.0] * 2})
    storage.upsert_daily("index_daily", index, fetched_at="2026-11-19T16:00:00+07:00")
    stock = pd.DataFrame({"symbol": "BBB", "trading_date": ["2026-11-18", "2026-11-19"], "close": [10.5, 11.2],
                          "price_change_pct": [None, None]})                # SSI không trả % thay đổi
    storage.upsert_daily("stock_daily", stock, fetched_at="2026-11-19T16:00:00+07:00")
    row = quality_table(storage, ["BBB"]).iloc[0]
    assert row["cross_checked"] == 0 and row["adjusted"] == 2 and row["missing"] == 0
