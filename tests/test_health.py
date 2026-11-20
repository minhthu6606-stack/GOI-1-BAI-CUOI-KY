"""Kiểm thử đầu-cuối: từ kho SQLite tạm -> đọc dữ liệu -> báo cáo sức khỏe danh mục."""
import numpy as np
import pandas as pd
import pytest

from src.data.storage import Storage
from src.finance.health import DANGER, GOOD, INFO, WARNING, build_health_report, pct, vnd
from src.finance.market_data import load_market_data
from src.finance.portfolio import build_portfolio

DAYS = pd.bdate_range("2025-01-01", periods=300).strftime("%Y-%m-%d").tolist()


def fill_storage(storage: Storage) -> None:
    rng = np.random.default_rng(42)
    market = rng.normal(0.0005, 0.01, len(DAYS))
    index_close = 1500 * np.cumprod(1 + market)
    storage.upsert_daily("index_daily", pd.DataFrame(
        {"symbol": "VNINDEX", "trading_date": DAYS, "close": index_close, "volume": 1e9}), "t")
    for symbol, beta, price, volume in [("AAA", 1.5, 50_000, 2_000_000), ("BBB", 0.5, 20_000, 50_000)]:
        returns = beta * market + rng.normal(0, 0.005, len(DAYS))
        storage.upsert_daily("stock_daily", pd.DataFrame({
            "symbol": symbol, "trading_date": DAYS, "close": price * np.cumprod(1 + returns),
            "volume": volume, "foreign_room_remaining": 1e6, "foreign_room_total": 1e7}), "2026-11-17T15:05:00+07:00")
    storage.upsert_securities([
        {"symbol": "AAA", "board": "HOSE", "icbName": "Ngân hàng"},
        {"symbol": "BBB", "board": "HNX", "icbName": "Công nghệ"},
    ], updated_at="t")


@pytest.fixture
def report(tmp_path):
    with Storage(tmp_path / "t.db") as storage:
        fill_storage(storage)
        portfolio = build_portfolio(pd.DataFrame({
            "symbol": ["AAA", "BBB", "KHONGCO", "CASH"], "quantity": [10_000, 50_000, 100, 100_000_000]}))
        market = load_market_data(storage, portfolio.symbols)
        yield build_health_report(portfolio, market)


def test_report_runs_and_notes_missing_symbol(report):
    assert "KHONGCO" in report.notes[0]
    assert report.metrics["return_sessions"] == len(DAYS) - 1
    assert report.checks_frame()["status"].isin([GOOD, WARNING, DANGER, INFO]).all()


def test_beta_close_to_constructed_value(report):
    # AAA (beta 1,5) và BBB (beta 0,5) trộn theo tỷ trọng -> beta danh mục nằm giữa 0,5 và 1,5
    assert 0.5 < report.metrics["beta"] < 1.5


def test_illiquid_position_flagged(report):
    liq = report.liquidity.set_index("symbol")
    # BBB: 50.000 cp, ADV 50.000, 20%/phiên -> 5 phiên + 2 ngày T+2 = 7 ngày -> thanh khoản thấp
    assert liq.loc["BBB", "bucket"] == "Thấp"
    check = next(c for c in report.checks if c.group == "Thanh khoản")
    assert "BBB" in check.explanation


def test_var_and_stress_are_positive_losses(report):
    assert report.metrics["var_pct"] > 0
    assert report.metrics["floor_loss_3"] > report.metrics["floor_loss_1"] > 0


def test_formatters():
    assert pct(0.1234) == "12,3%"
    assert vnd(1234567) == "1.234.567 đ"
    assert pct(float("nan")) == "không đủ dữ liệu"


def test_vnd_short():
    from src.finance.health import vnd_short
    assert vnd_short(500_000_000) == "500,0 tr đ"
    assert vnd_short(1_250_000_000) == "1,25 tỷ đ"
    assert vnd_short(-52_415_000) == "-52,4 tr đ"
    assert vnd_short(950_000) == "950.000 đ"


def test_vnd_short_thousands():
    from src.finance.health import vnd_short
    assert vnd_short(8_540_894_758_680) == "8.540,89 tỷ đ"


def test_every_check_has_action_and_verdict_uses_worst_level(report):
    from src.finance.health import DANGER, GOOD, WARNING, Check, count_by_status, overall_verdict
    assert all(c.action for c in report.checks)
    good = Check("g", "a", "1", GOOD, "", "")
    warn = Check("g", "b", "1", WARNING, "", "")
    bad = Check("g", "c", "1", DANGER, "", "")
    assert overall_verdict([good, good])[0] == GOOD
    assert overall_verdict([good, warn])[0] == WARNING
    assert overall_verdict([good, warn, bad])[1] == "Cần xem lại"
    assert count_by_status([good, warn, bad, bad]) == {DANGER: 2, WARNING: 1, GOOD: 1, "Thông tin": 0}


def test_vnd_full_and_billion():
    from src.finance.health import vnd, vnd_billion
    assert vnd(500_000_000) == "500.000.000 đ"
    assert vnd(-52_415_000) == "-52.415.000 đ"
    assert vnd_billion(25_432_100_000_000) == "25.432 tỷ đ"


def test_var_reliability_is_info_and_does_not_change_verdict(report):
    """Độ tin cậy của VaR đánh giá công cụ đo, không đánh giá danh mục: luôn ở mức Thông tin."""
    from src.finance.health import overall_verdict
    check = next(c for c in report.checks if c.name.startswith("Độ tin cậy của VaR"))
    assert check.status == INFO and "không tính vào kết luận chung" in check.threshold
    without = [c for c in report.checks if c is not check]
    assert overall_verdict(report.checks) == overall_verdict(without)
