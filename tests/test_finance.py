"""Kiểm thử lớp tài chính src/finance/ - mọi ví dụ đều tính tay được."""
import math

import numpy as np
import pandas as pd
import pytest

from src.finance import concentration, liquidity, risk, stress
from src.finance.portfolio import PortfolioError, build_portfolio, value_portfolio


# ---------------------------------------------------------------- danh mục

def test_build_portfolio_merges_duplicates_and_cash():
    rows = pd.DataFrame({
        "symbol": [" fpt", "FPT", "VCB", "CASH"],
        "quantity": [100, 300, 200, 5_000_000],
        "avg_cost": [40_000, 48_000, 60_000, None],
    })
    portfolio = build_portfolio(rows)
    fpt = portfolio.holdings.set_index("symbol").loc["FPT"]
    assert fpt["quantity"] == 400
    # giá vốn bình quân = (100×40.000 + 300×48.000) / 400 = 46.000
    assert fpt["avg_cost"] == pytest.approx(46_000)
    assert portfolio.cash == 5_000_000


@pytest.mark.parametrize("rows, message", [
    ({"symbol": ["FPT"], "quantity": [-10]}, "dương"),
    ({"symbol": ["F@T"], "quantity": [10]}, "không hợp lệ"),
    ({"symbol": ["CASH"], "quantity": [100]}, "chưa có cổ phiếu"),
])
def test_build_portfolio_rejects_bad_input(rows, message):
    with pytest.raises(PortfolioError, match=message):
        build_portfolio(pd.DataFrame(rows))


def test_value_portfolio_weights_include_cash():
    portfolio = build_portfolio(pd.DataFrame({
        "symbol": ["AAA", "BBB", "CASH"], "quantity": [100, 200, 20_000], "avg_cost": [100, 50, None]}))
    table, totals = value_portfolio(portfolio, pd.Series({"AAA": 120.0, "BBB": 40.0}))
    # AAA = 12.000, BBB = 8.000, tiền = 20.000 -> tổng 40.000
    assert totals["total_value"] == 40_000
    weights = table.set_index("symbol")["weight_total"]
    assert weights["AAA"] == pytest.approx(0.30) and weights["BBB"] == pytest.approx(0.20)
    assert table.set_index("symbol").loc["AAA", "pnl"] == pytest.approx(2_000)   # (120 - 100) × 100


def test_value_portfolio_marks_missing_price():
    portfolio = build_portfolio(pd.DataFrame({"symbol": ["AAA", "ZZZ"], "quantity": [100, 100]}))
    table, totals = value_portfolio(portfolio, pd.Series({"AAA": 10.0}))
    assert table.set_index("symbol").loc["ZZZ", "has_price"] == False  # noqa: E712
    assert totals["equity_value"] == 1_000


# ---------------------------------------------------------------- tập trung

def test_hhi_and_effective_number():
    equal = pd.Series([0.25, 0.25, 0.25, 0.25])
    assert concentration.hhi(equal) == pytest.approx(0.25)
    assert concentration.effective_number(equal) == pytest.approx(4)
    # 0,5² + 0,3² + 0,2² = 0,38 -> N_eff = 2,63
    assert concentration.hhi(pd.Series([50, 30, 20])) == pytest.approx(0.38)


def test_ucits_check():
    result = concentration.ucits_check(pd.Series({"A": 0.30, "B": 0.12, "C": 0.08, "D": 0.04}))
    assert result["max_symbol"] == "A" and result["breach_single"]
    assert result["over_single_limit"] == ["A", "B"]
    assert result["large_positions_sum"] == pytest.approx(0.50)   # 0,30 + 0,12 + 0,08 (D <= 5% không tính)
    assert result["breach_aggregate"]


def test_sector_weights():
    valuation = pd.DataFrame({"symbol": ["VCB", "MBB", "FPT"], "market_value": [30.0, 20.0, 50.0]})
    securities = pd.DataFrame({"symbol": ["VCB", "MBB", "FPT"], "icb_name": ["Ngân hàng", "Ngân hàng", "Công nghệ"]})
    weights = concentration.sector_weights(valuation, securities)
    assert weights["Ngân hàng"] == pytest.approx(0.5) and weights["Công nghệ"] == pytest.approx(0.5)


# ---------------------------------------------------------------- thanh khoản

def test_sessions_to_sell_and_bucket():
    # 100.000 cp, ADV 100.000, bán tối đa 20% ADV mỗi phiên = 20.000 cp -> 5 phiên
    assert liquidity.sessions_to_sell(100_000, 100_000, 0.2) == 5
    assert liquidity.sessions_to_sell(1, 100_000, 0.2) == 1
    assert math.isinf(liquidity.sessions_to_sell(100, 0, 0.2))
    # 1 phiên bán + 2 ngày T+2 = 3 ngày -> Cao ; 3 + 2 = 5 -> Trung bình ; 5 + 2 = 7 -> Thấp
    assert liquidity.liquidity_bucket(3) == liquidity.BUCKET_HIGH
    assert liquidity.liquidity_bucket(5) == liquidity.BUCKET_MODERATE
    assert liquidity.liquidity_bucket(7) == liquidity.BUCKET_LOW


def test_liquidity_table_and_illiquid_share():
    valuation = pd.DataFrame({"symbol": ["A", "B"], "quantity": [10_000, 100_000],
                              "market_value": [1.0, 1.0], "weight_total": [0.6, 0.3]})
    volume = pd.DataFrame({"A": [1_000_000] * 20, "B": [100_000] * 20})
    table = liquidity.liquidity_table(valuation, liquidity.average_daily_volume(volume), 0.2).set_index("symbol")
    assert table.loc["A", "days_to_cash"] == 3 and table.loc["A", "bucket"] == liquidity.BUCKET_HIGH
    assert table.loc["B", "days_to_cash"] == 7 and table.loc["B", "bucket"] == liquidity.BUCKET_LOW
    assert liquidity.illiquid_share(table.reset_index()) == pytest.approx(0.3)


# ---------------------------------------------------------------- rủi ro thị trường

def test_daily_returns_and_portfolio_returns():
    close = pd.DataFrame({"A": [100.0, 110.0, 99.0], "B": [50.0, 50.0, 55.0]})
    returns = risk.daily_returns(close)
    assert returns["A"].tolist() == pytest.approx([0.10, -0.10])
    # tỷ trọng A 50%, B 30%, tiền 20% (lợi suất 0): phiên 1 = 0,5×0,1 = 0,05 ; phiên 2 = -0,05 + 0,3×0,1 = -0,02
    port = risk.portfolio_returns(returns, pd.Series({"A": 0.5, "B": 0.3}))
    assert port.tolist() == pytest.approx([0.05, -0.02])


def test_beta_of_scaled_series_is_scale():
    rng = np.random.default_rng(0)
    market = pd.Series(rng.normal(0, 0.01, 300))
    assert risk.beta(market * 1.5, market) == pytest.approx(1.5)


def test_historical_var_is_loss_quantile():
    returns = pd.Series(np.linspace(-0.10, 0.09, 20))   # -10%, -9%, ..., 9%
    var = risk.historical_var(returns, confidence=0.95, window=20)
    assert var == pytest.approx(-returns.quantile(0.05))
    assert var > 0


def test_max_drawdown():
    # giá trị: 1 -> 1,2 -> 0,9 -> 1,08 ; đỉnh 1,2, đáy 0,9 -> sụt 25%
    returns = pd.Series([0.20, -0.25, 0.20])
    assert risk.max_drawdown(returns) == pytest.approx(-0.25)
    assert risk.max_drawdown(pd.Series([-0.10])) == pytest.approx(-0.10)  # đỉnh là mốc ban đầu


# ---------------------------------------------------------------- kịch bản giảm sàn

@pytest.mark.parametrize("price, board, tick", [(9_990, "HOSE", 10), (10_000, "HOSE", 50), (49_950, "HOSE", 50),
                                                (50_000, "HOSE", 100), (8_000, "HNX", 100)])
def test_tick_size(price, board, tick):
    assert stress.tick_size(price, board) == tick


def test_floor_price_rounds_up_to_tick():
    # 49.400 × 0,93 = 45.942 -> bước 50 -> làm tròn lên 45.950
    assert stress.floor_price(49_400, "HOSE") == 45_950
    # 60.000 × 0,93 = 55.800 đúng bước 100
    assert stress.floor_price(60_000, "HOSE") == 55_800
    # HNX 10%: 20.000 × 0,9 = 18.000
    assert stress.floor_price(20_000, "HNX") == 18_000


def test_floor_scenario_multi_session():
    valuation = pd.DataFrame({"symbol": ["A"], "quantity": [100], "price": [60_000.0],
                              "market_value": [6_000_000.0], "has_price": [True]})
    table, summary = stress.floor_scenario(valuation, pd.Series({"A": "HOSE"}), sessions=2)
    # 60.000 -> 55.800 -> 55.800 × 0,93 = 51.894 -> làm tròn lên bước 100 = 51.900
    assert table.loc[0, "stressed_price"] == 51_900
    assert summary["total_loss"] == pytest.approx((60_000 - 51_900) * 100)


def test_r_squared_matches_beta_formula():
    rng = np.random.default_rng(1)
    market = pd.Series(rng.normal(0, 0.01, 300))
    asset = 0.7 * market + pd.Series(rng.normal(0, 0.01, 300))
    r2 = risk.r_squared(asset, market, window=300)
    # R² = β²σ²_m / σ²_tài sản
    expected = risk.beta(asset, market, window=300) ** 2 * market.var() / asset.var()
    assert r2 == pytest.approx(expected)
    assert risk.r_squared(market * 2, market) == pytest.approx(1.0)
