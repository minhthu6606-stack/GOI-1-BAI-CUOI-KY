"""Kiểm thử src/data/updater.py bằng client SSI giả lập và kho SQLite tạm."""
from datetime import date, timedelta

import pandas as pd
import pytest

from src.data.storage import Storage
from src.data.updater import DataUpdater, history_was_adjusted
from src.ssi_api.client import SSIError

TODAY = date(2026, 11, 16)


def business_days(start: date, end: date) -> list[date]:
    days, day = [], start
    while day <= end:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


class FakeClient:
    """Client giả: trả dữ liệu theo khoảng ngày được hỏi, ghi lại các lần gọi."""

    def __init__(self, stock_price=50000.0, missing_days=(), fail_symbols=()):
        self.stock_price = stock_price
        self.missing_days = set(missing_days)
        self.fail_symbols = set(fail_symbols)
        self.calls = []

    def get_index_daily(self, symbol, start, end):
        self.calls.append(("index", symbol, start, end))
        return [{"tradingDate": d.strftime("%Y/%m/%d"), "open": "1700", "high": "1710", "low": "1690",
                 "close": "1700", "volume": "1"} for d in business_days(start, end)]

    def get_stock_daily(self, symbol, start, end):
        self.calls.append(("stock", symbol, start, end))
        if symbol in self.fail_symbols:
            raise SSIError("HTTP 503 sau 3 lần thử")
        if symbol == "KHONGCO":
            return []
        price = str(self.stock_price)
        return [{"tradingDate": d.strftime("%Y/%m/%d"), "open": price, "high": price, "low": price, "close": price,
                 "priceChangePercentage": "0", "totalMatch": "1000"}
                for d in business_days(start, end) if d not in self.missing_days]

    def get_securities(self, board):
        return [{"symbol": "FPT", "board": board, "icbName": "Công nghệ"}]

    def get_market_summary(self, board, trading_date=None):
        return {"tradingDate": "2026/11/16", "indexValue": "1736.89", "totalAdvanceStock": "97"}


@pytest.fixture
def storage(tmp_path):
    with Storage(tmp_path / "test.db") as store:
        yield store


def test_first_run_downloads_full_history(storage):
    client = FakeClient()
    results = DataUpdater(client, storage, history_years=1, today=TODAY).run(["fpt"])
    assert [r.mode for r in results] == ["full", "full"]
    assert all(r.status == "ok" for r in results)
    stock_call = [c for c in client.calls if c[0] == "stock"][0]
    assert stock_call[1] == "FPT"                          # mã được viết hoa
    assert stock_call[2] == TODAY - timedelta(days=365)    # tải đủ 1 năm
    assert results[1].missing_sessions == 0
    assert len(storage.load_market_summary("HOSE")) == 1
    log = storage.load_fetch_log()
    assert len(log) == 3                                    # chỉ số + 1 mã + tổng hợp thị trường
    assert set(log["dataset"]) == {"index_daily", "stock_daily", "market_summary"}


def test_second_run_is_incremental(storage):
    DataUpdater(FakeClient(), storage, history_years=1, today=TODAY).run(["FPT"])
    client = FakeClient()
    later = TODAY + timedelta(days=3)
    results = DataUpdater(client, storage, history_years=1, overlap_days=14, today=later).run(["FPT"])
    assert [r.mode for r in results] == ["incremental", "incremental"]
    stock_call = [c for c in client.calls if c[0] == "stock"][0]
    assert stock_call[2] == TODAY - timedelta(days=14)     # chỉ tải lại từ phiên cuối - 14 ngày
    assert storage.last_trading_date("stock_daily", "FPT") == later.isoformat()


def test_adjusted_history_triggers_full_refresh(storage):
    DataUpdater(FakeClient(stock_price=50000), storage, history_years=1, today=TODAY).run(["FPT"])
    # Giả lập SSI điều chỉnh lại toàn bộ lịch sử sau khi chia cổ tức: giá cũ giảm 2%
    client = FakeClient(stock_price=49000)
    results = DataUpdater(client, storage, history_years=1, today=TODAY + timedelta(days=1)).run(["FPT"])
    assert results[1].mode == "refresh"
    closes = storage.load_daily("stock_daily", "FPT")["close"].unique().tolist()
    assert closes == [49000.0]                             # không còn trộn giá cũ và giá mới


def test_missing_sessions_counted(storage):
    gap = [date(2026, 11, 11), date(2026, 11, 12)]
    results = DataUpdater(FakeClient(missing_days=gap), storage, history_years=1, today=TODAY).run(["FPT"])
    assert results[1].missing_sessions == 2


def test_error_and_empty_do_not_stop_other_symbols(storage):
    client = FakeClient(fail_symbols={"HPG"})
    results = DataUpdater(client, storage, history_years=1, today=TODAY).run(["HPG", "KHONGCO", "FPT"])
    status = {r.symbol: r.status for r in results}
    assert status == {"VNINDEX": "ok", "HPG": "error", "KHONGCO": "empty", "FPT": "ok"}
    log = storage.load_fetch_log()
    assert "503" in log.loc[log["symbol"] == "HPG", "message"].iloc[0]


def test_history_was_adjusted_ignores_last_stored_session():
    stored = pd.DataFrame({"trading_date": ["2026-11-13", "2026-11-16"], "close": [50000.0, 49000.0]})
    # Phiên 16/11 lần trước lưu trong giờ giao dịch nên khác giá đóng cửa cuối - không tính là điều chỉnh
    fresh = pd.DataFrame({"trading_date": ["2026-11-13", "2026-11-16"], "close": [50000.0, 49400.0]})
    assert history_was_adjusted(stored, fresh, tolerance=0.001) is False
    fresh_adjusted = fresh.assign(close=[49000.0, 49400.0])
    assert history_was_adjusted(stored, fresh_adjusted, tolerance=0.001) is True


class HistoryClient(FakeClient):
    """Client giả có lịch sử tổng hợp thị trường: trả đúng ngày được hỏi."""

    def __init__(self):
        super().__init__()
        self.summary_calls = []

    def get_market_summary(self, board, trading_date=None):
        self.summary_calls.append(trading_date)
        return {"tradingDate": trading_date.strftime("%Y/%m/%d"), "indexValue": "1700",
                "netPurchasesForeignValue": "-1000000000"}


def test_market_summary_backfills_recent_sessions_once(storage):
    client = HistoryClient()
    DataUpdater(client, storage, history_years=1, today=TODAY).run(["FPT"])
    summary = storage.load_market_summary("HOSE")
    assert len(summary) == 20                               # đủ 20 phiên gần nhất
    assert summary["trading_date"].max() == TODAY.isoformat()
    assert client.summary_calls[0] == TODAY                 # hỏi từ phiên mới nhất trở về trước

    client.summary_calls.clear()
    DataUpdater(client, storage, history_years=1, today=TODAY).run(["FPT"])
    assert client.summary_calls == []                       # đã đủ thì không hỏi lại


def test_market_summary_stops_when_history_not_supported(storage):
    """FakeClient luôn trả ngày 16/11: hỏi ngày cũ hơn mà nhận ngày khác thì dừng, không ghi sai ngày."""
    DataUpdater(FakeClient(), storage, history_years=1, today=TODAY).run(["FPT"])
    summary = storage.load_market_summary("HOSE")
    assert summary["trading_date"].tolist() == ["2026-11-16"]
    log = storage.load_fetch_log()
    assert "dừng" in log.loc[log["dataset"] == "market_summary", "message"].iloc[0]


def test_long_gap_is_backfilled_without_missing_or_duplicates(storage):
    """Nghỉ nhiều phiên (vd ngày thi) rồi mới mở lại: một lần tải bù đủ, không thiếu, không trùng."""
    client = FakeClient()
    DataUpdater(client, storage, history_years=1, today=date(2026, 10, 30)).run(["FPT"])
    later = date(2026, 11, 20)                                              # nghỉ 3 tuần
    results = DataUpdater(client, storage, history_years=1, today=later).run(["FPT"])
    stock = next(r for r in results if r.symbol == "FPT")
    frame = storage.load_daily("stock_daily", "FPT")
    assert stock.mode == "incremental" and stock.missing_sessions == 0
    assert frame["trading_date"].max() == later.isoformat()
    assert not frame["trading_date"].duplicated().any()
    assert set(d.isoformat() for d in business_days(date(2026, 11, 2), later)) <= set(frame["trading_date"])


def test_intraday_price_is_replaced_by_close_without_full_refresh(storage):
    """Tải trong giờ giao dịch (giá tạm) rồi tải lại sau giờ chốt: giá được thay, không tải lại toàn bộ."""
    DataUpdater(FakeClient(stock_price=50500), storage, history_years=1, today=TODAY).run(["FPT"])
    client = FakeClient(stock_price=50500)
    original = client.get_stock_daily

    def final_close(symbol, start, end):
        rows = original(symbol, start, end)
        rows[-1] = {**rows[-1], "close": "51000"}                           # phiên hôm nay có giá đóng cửa cuối
        return rows

    client.get_stock_daily = final_close
    results = DataUpdater(client, storage, history_years=1, today=TODAY).run(["FPT"])
    stock = next(r for r in results if r.symbol == "FPT")
    assert stock.mode == "incremental"
    assert storage.load_daily("stock_daily", "FPT", start=TODAY.isoformat())["close"].iloc[0] == 51000
