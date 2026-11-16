"""Kiểm thử src/data/storage.py trên một file SQLite tạm (không đụng tới kho thật)."""
import pandas as pd
import pytest

from src.data.storage import Storage


@pytest.fixture
def storage(tmp_path):
    with Storage(tmp_path / "test.db") as store:
        yield store


def daily_frame(symbol, rows):
    """rows: danh sách (ngày, giá đóng cửa)."""
    return pd.DataFrame(
        [{"symbol": symbol, "trading_date": day, "close": close, "volume": 1000.0, "quality_flag": ""} for day, close in rows]
    )


def test_upsert_is_idempotent(storage):
    frame = daily_frame("FPT", [("2026-11-13", 50100.0), ("2026-11-16", 49400.0)])
    storage.upsert_daily("stock_daily", frame, fetched_at="2026-11-17T15:05:00+07:00")
    storage.upsert_daily("stock_daily", frame, fetched_at="2026-11-17T15:06:00+07:00")
    stored = storage.load_daily("stock_daily", "FPT")
    assert len(stored) == 2                      # ghi lại lần 2 không nhân đôi
    assert stored["source"].unique().tolist() == ["SSI"]
    assert stored["fetched_at"].iloc[0] == "2026-11-17T15:06:00+07:00"


def test_upsert_replaces_changed_value(storage):
    storage.upsert_daily("stock_daily", daily_frame("FPT", [("2026-11-16", 49000.0)]), fetched_at="t1")
    storage.upsert_daily("stock_daily", daily_frame("FPT", [("2026-11-16", 49400.0)]), fetched_at="t2")
    assert storage.load_daily("stock_daily", "FPT")["close"].tolist() == [49400.0]


def test_nan_is_stored_as_null(storage):
    frame = daily_frame("FPT", [("2026-11-16", 49400.0)]).assign(volume=float("nan"))
    storage.upsert_daily("stock_daily", frame, fetched_at="t")
    value = storage.conn.execute("SELECT volume FROM stock_daily").fetchone()[0]
    assert value is None


def test_last_date_delete_and_calendar(storage):
    storage.upsert_daily("index_daily", daily_frame("VNINDEX", [("2026-11-13", 1734.9), ("2026-11-16", 1736.9)]), "t")
    assert storage.last_trading_date("index_daily", "VNINDEX") == "2026-11-16"
    assert storage.trading_calendar("VNINDEX") == ["2026-11-13", "2026-11-16"]
    storage.delete_symbol("index_daily", "VNINDEX")
    assert storage.last_trading_date("index_daily", "VNINDEX") is None


def test_rejects_unknown_table(storage):
    with pytest.raises(ValueError):
        storage.upsert_daily("securities; DROP TABLE x", daily_frame("FPT", [("2026-11-16", 1.0)]), "t")


def test_securities_raw_and_log(storage):
    storage.upsert_securities(
        [{"symbol": "FPT", "symbolNameVi": "CTCP FPT", "board": "HOSE", "icbName": "Công nghệ", "listedShare": "1000"}],
        updated_at="2026-11-17T09:00:00+07:00",
    )
    securities = storage.load_securities(["FPT"])
    assert securities.loc[0, "icb_name"] == "Công nghệ" and securities.loc[0, "listed_share"] == 1000.0

    storage.save_raw("data/ohlc", {"symbol": "VNINDEX"}, {"data": []})
    assert storage.conn.execute("SELECT COUNT(*) FROM raw_responses").fetchone()[0] == 1

    storage.log_fetch({"run_id": "abc", "symbol": "FPT", "status": "ok", "rows_kept": 2})
    assert storage.load_fetch_log().loc[0, "symbol"] == "FPT"
