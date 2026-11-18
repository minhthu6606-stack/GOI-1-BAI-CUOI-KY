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


def test_market_charts():
    import pandas as pd
    from src.app import charts
    index = pd.Series([1700.0, 1710.0, 1695.0], index=["2026-11-12", "2026-11-13", "2026-11-16"])
    fig = charts.index_chart(index)
    assert fig.layout.xaxis.rangeselector.buttons[-1].label == "Tất cả"
    summary = pd.DataFrame({"trading_date": ["2026-11-13", "2026-11-16"], "foreign_net_value": [5e11, -2e11],
                            "advances": [120, 90], "declines": [100, 160]})
    flow = charts.foreign_flow_bar(summary)
    assert list(flow.data[0].x) == ["13/11", "16/11"]
    assert "Bán ròng" in flow.data[0].customdata[1]
    assert len(charts.breadth_chart(summary).data) == 2


def test_diversity_scale_dark_and_ticker():
    from src.app import charts
    from src.app.style import ticker_html
    scale = charts.diversity_scale(4.8)
    assert [t.base[0] for t in scale.data[:3]] == [0, 5, 10]          # 3 vùng bắt đầu ở 0, 5, 10 mã
    assert scale.data[3].x[0] == 4.8                                  # điểm đánh dấu danh mục
    dark = charts.apply_dark(scale)
    assert dark.data[3].marker.color == charts.DARK_COLORS[charts.SERIES[0]]
    html = ticker_html([("VN-Index", 1736.89, -0.0061), ("FPT", 98500, 0.012), ("VCB", 60000, 0.0)], "Phiên 16/11/2026")
    assert "1.736,89" in html and "▼ 0,61%" in html and "▲ 1,20%" in html and "98.500" in html
    assert html.count("FPT") == 2          # nội dung nhân đôi để chạy vòng liền mạch


def test_theme_css_and_script():
    from src.app.style import hero_art, theme_css, theme_sync_script
    assert "--card-bg: #ffffff" in theme_css(False) and "--card-bg: #1b1630" in theme_css(True)
    assert '"Dark"' in theme_sync_script(True) and '"Light"' in theme_sync_script(False)
    assert 'fill="#ffffff"' in hero_art(False) and '"CARD"' not in hero_art(True)
