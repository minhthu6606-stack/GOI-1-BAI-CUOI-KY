"""Kiểm thử src/finance/backtest.py: kiểm định Kupiec và Christoffersen cho VaR lịch sử."""
import math

import numpy as np
import pandas as pd

from src.finance.backtest import (
    BacktestResult, backtest_var, chi2_1_pvalue, christoffersen_independence, kupiec_pof,
)


def test_chi2_pvalue_known_values():
    assert math.isclose(chi2_1_pvalue(3.841), 0.05, abs_tol=1e-3)    # giá trị tới hạn 5% của χ²(1)
    assert math.isclose(chi2_1_pvalue(0.0), 1.0)


def test_kupiec_exact_rate_is_not_rejected():
    statistic, p = kupiec_pof(500, 25, 0.05)                          # đúng 5%
    assert statistic < 1e-9 and p > 0.99


def test_kupiec_too_many_exceptions_is_rejected():
    _, p = kupiec_pof(500, 50, 0.05)                                   # 10% thay vì 5%
    assert p < 0.01


def test_kupiec_zero_exceptions_handled():
    statistic, p = kupiec_pof(250, 0, 0.05)
    assert statistic > 0 and 0 <= p < 0.05                            # 0 lần vượt trong 250 ngày cũng đáng ngờ


def test_independence_detects_clustering():
    clustered = pd.Series([0] * 200 + [1] * 10 + [0] * 200 + [1] * 10)
    _, p_clustered = christoffersen_independence(clustered)
    spread = pd.Series(([0] * 19 + [1]) * 21)
    _, p_spread = christoffersen_independence(spread)
    assert p_clustered < 0.01 and p_spread > 0.05


def test_backtest_uses_only_past_data_and_counts_exceptions():
    rng = np.random.default_rng(7)
    returns = pd.Series(rng.normal(0, 0.01, 800), index=[f"d{i:04d}" for i in range(800)])
    result = backtest_var(returns, confidence=0.95, window=250)
    assert result.observations == 800 - 250
    assert 0.02 < result.exception_rate < 0.09                       # gần 5% với dữ liệu chuẩn
    first_day = result.series.index[0]
    expected_var = -returns.iloc[:250].quantile(0.05)                 # VaR ngày đầu chỉ dùng 250 ngày trước
    assert first_day == "d0250" and math.isclose(result.series["var"].iloc[0], expected_var)


def test_backtest_too_short_series():
    result = backtest_var(pd.Series([0.01] * 100), window=250)
    assert result.observations == 0


def test_too_few_exceptions_is_flagged_as_conservative():
    few = BacktestResult(500, 8, 0.05, *kupiec_pof(500, 8, 0.05), 0.0, 1.0)     # 1,6% thay vì 5%
    many = BacktestResult(500, 45, 0.05, *kupiec_pof(500, 45, 0.05), 0.0, 1.0)  # 9% thay vì 5%
    assert not few.passes_pof and few.too_few_exceptions                        # VaR thận trọng
    assert not many.passes_pof and not many.too_few_exceptions                  # VaR đánh giá thấp rủi ro
