"""Kiểm thử danh mục ví dụ, mức chịu rủi ro tự khai (hỏi bệnh sử) và Thử điều chỉnh (kê đơn)."""
import pandas as pd
import pytest

from src.data.storage import Storage
from src.finance.examples import EXAMPLE_TOTAL, EXAMPLES, build_example, example_symbols, round_to_lot
from src.finance.health import GOOD, INFO, WARNING, RiskProfile, build_health_report
from src.finance.market_data import load_market_data
from src.finance.portfolio import build_portfolio
from src.finance.whatif import changed_checks, compare_reports, portfolio_from_weights, to_lots
from tests.test_health import fill_storage


# ---------------------------------------------------------------- danh mục ví dụ

def test_round_to_lot():
    assert round_to_lot(22_500_000, 49_400) == 400          # 455 cổ phiếu -> làm tròn xuống 400
    assert round_to_lot(10_000_000, 60_000) == 100          # 166 -> 100: không vượt 10% mục tiêu
    assert round_to_lot(1_000_000, 150_000) == 100          # tối thiểu 1 lô


def test_example_uses_lots_and_keeps_total_near_100m():
    prices = pd.Series({"FPT": 49_400.0, "MBB": 25_000.0, "HPG": 27_000.0, "MWG": 60_000.0})
    rows, cash = build_example("beginner", prices)
    assert (rows["quantity"] % 100 == 0).all()
    invested = (rows["quantity"] * rows["avg_cost"]).sum()
    assert cash >= 0 and abs(invested + cash - EXAMPLE_TOTAL) < 1_000
    weights = rows.set_index("symbol")["quantity"] * prices / EXAMPLE_TOTAL
    assert (weights <= 0.225 + 1e-9).all()                  # không mã nào vượt tỷ trọng mục tiêu
    assert set(rows["symbol"]) == set(EXAMPLES["beginner"].weights)


def test_example_skips_symbol_without_price():
    rows, cash = build_example("beginner", pd.Series({"FPT": 49_400.0}))
    assert rows["symbol"].tolist() == ["FPT"] and cash > 70_000_000   # phần của mã thiếu giá thành tiền mặt


def test_examples_are_structurally_different():
    assert len(EXAMPLES["beginner"].weights) == 4 and len(EXAMPLES["diversified"].weights) == 8
    assert all(w <= 0.10 for w in EXAMPLES["diversified"].weights.values())
    assert sum(EXAMPLES["diversified"].weights.values()) == pytest.approx(0.8)
    assert {"FPT", "VCB", "ACB", "TCB", "GAS"} <= set(example_symbols())


# ---------------------------------------------------------------- hỏi bệnh sử và kê đơn (dùng kho thử)

@pytest.fixture
def market_and_portfolio(tmp_path):
    with Storage(tmp_path / "t.db") as storage:
        fill_storage(storage)
        portfolio = build_portfolio(pd.DataFrame({"symbol": ["AAA", "BBB", "CASH"],
                                                  "quantity": [10_000, 20_000, 100_000_000]}))
        yield load_market_data(storage, portfolio.symbols), portfolio


def _check(report, name):
    return next(c for c in report.checks if c.name.startswith(name))


def test_without_profile_var_has_no_threshold(market_and_portfolio):
    market, portfolio = market_and_portfolio
    report = build_health_report(portfolio, market)
    assert _check(report, "Mức lỗ trong một phiên xấu").status == INFO
    assert _check(report, "Sụt giảm tối đa").status == INFO


def test_profile_turns_var_and_drawdown_into_graded_checks(market_and_portfolio):
    market, portfolio = market_and_portfolio
    strict = build_health_report(portfolio, market, profile=RiskProfile(max_daily_loss=0.001, max_drawdown=0.01))
    loose = build_health_report(portfolio, market, profile=RiskProfile(max_daily_loss=0.5, max_drawdown=0.9))
    assert _check(strict, "Mức lỗ trong một phiên xấu").status == WARNING
    assert _check(strict, "Sụt giảm tối đa").status == WARNING
    assert _check(loose, "Mức lỗ trong một phiên xấu").status == GOOD
    assert "mức bạn chịu được" in _check(loose, "Mức lỗ trong một phiên xấu").threshold


def test_portfolio_from_weights_keeps_total_and_weights(market_and_portfolio):
    market, _ = market_and_portfolio
    prices = market.latest["close"]
    simulated = portfolio_from_weights({"AAA": 0.3, "BBB": 0.2}, prices, 500_000_000)
    values = simulated.holdings.set_index("symbol")["quantity"] * prices
    assert values["AAA"] == pytest.approx(150_000_000) and values["BBB"] == pytest.approx(100_000_000)
    assert simulated.cash == pytest.approx(250_000_000)
    with pytest.raises(ValueError):
        portfolio_from_weights({"AAA": 0.7, "BBB": 0.4}, prices, 1e8)


def test_to_lots_rounds_and_moves_difference_to_cash(market_and_portfolio):
    market, _ = market_and_portfolio
    prices = market.latest["close"]
    simulated = portfolio_from_weights({"AAA": 0.3, "BBB": 0.2}, prices, 500_000_000)
    rows, cash = to_lots(simulated, prices)
    assert (rows["quantity"] % 100 == 0).all() and cash >= 0
    total = (rows["quantity"] * rows["symbol"].map(prices)).sum() + cash
    assert total == pytest.approx(500_000_000, rel=0.01)


def test_reducing_concentration_improves_checks(market_and_portfolio):
    market, portfolio = market_and_portfolio
    before = build_health_report(portfolio, market)
    total = before.totals["total_value"]
    after = build_health_report(portfolio_from_weights({"AAA": 0.05, "BBB": 0.05}, market.latest["close"], total),
                                market)
    changes = changed_checks(before, after)
    assert "tốt lên" in set(changes["direction"]) and "xấu đi" not in set(changes["direction"])
    table = compare_reports(before, after)
    assert table.columns.tolist() == ["Chỉ số", "Hiện tại", "Sau điều chỉnh"] and len(table) == 8
