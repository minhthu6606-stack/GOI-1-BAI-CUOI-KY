"""Kiểm thử các hàm vẽ biểu đồ: dựng được Figure với đúng số chuỗi dữ liệu, không lỗi với dữ liệu thiếu."""
import numpy as np
import pandas as pd

from src.app import charts

DAYS = pd.bdate_range("2026-01-01", periods=60).strftime("%Y-%m-%d")
RNG = np.random.default_rng(0)
PORT = pd.Series(RNG.normal(0, 0.01, 60), index=DAYS)
MARKET = pd.Series(RNG.normal(0, 0.01, 60), index=DAYS)


def test_growth_chart_has_portfolio_index_and_extra():
    fig = charts.growth_chart(PORT, MARKET, {"FPT": PORT * 1.2}, sessions=250)
    assert [t.name for t in fig.data] == [charts.PORTFOLIO_LABEL, charts.INDEX_LABEL, "FPT"]
    assert fig.data[0].y[0] == 100 * (1 + PORT.iloc[0])   # mốc 100 đồng


def test_weights_and_sector_bars():
    valuation = pd.DataFrame({"symbol": ["A", "B"], "weight_total": [0.6, 0.3], "has_price": [True, True]})
    fig = charts.weights_bar(valuation, cash_weight=0.1)
    assert list(fig.data[0].y) == ["Tiền mặt", "B", "A"]          # xếp từ nhỏ đến lớn
    assert fig.data[0].marker.color[0] == charts.NEUTRAL          # tiền mặt màu xám
    assert len(charts.sector_bar(pd.Series({"Ngân hàng": 0.7, "Phần mềm": 0.3})).data) == 1


def test_drawdown_and_histogram():
    assert max(charts.drawdown_chart(PORT).data[0].y) <= 0
    fig = charts.returns_histogram(PORT, var_pct=0.02)
    assert len(fig.layout.shapes) == 1                            # đường VaR
    assert len(charts.returns_histogram(PORT, var_pct=float("nan")).layout.shapes) == 0


def test_stress_bar_two_series():
    frame = pd.DataFrame({"symbol": ["A"], "loss": [1000.0]})
    assert [t.name for t in charts.stress_bar(frame, frame).data] == ["Giảm sàn 1 phiên", "Giảm sàn 3 phiên liên tiếp"]
