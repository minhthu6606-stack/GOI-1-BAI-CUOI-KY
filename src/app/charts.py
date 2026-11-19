"""
Các biểu đồ của ứng dụng (Plotly). Mỗi hàm nhận dữ liệu đã tính sẵn và trả về một Figure,
nên kiểm thử được mà không cần chạy giao diện.

Tương tác: rê chuột để xem số liệu từng điểm; kéo chuột để phóng to, nhấp đúp để trở lại;
bấm vào tên trong chú thích để ẩn/hiện một đường; biểu đồ theo thời gian có thanh trượt và
nút chọn nhanh khoảng thời gian.

Quy ước màu (bảng màu tím - vàng của sản phẩm, đã chạy bộ kiểm tra cho người mù màu: đạt mọi tiêu chí
trên nền trắng, mọi màu có độ tương phản >= 3:1):
    - danh mục: tím; VN-Index: vàng đậm; mã so sánh thêm: xanh ngọc, xanh dương, hồng đậm (thứ tự cố định);
    - tiền mặt: xám trung tính, có vân sọc để phân biệt không chỉ bằng màu;
    - tăng/giảm, mua ròng/bán ròng: xanh lá/đỏ theo thói quen của thị trường Việt Nam, luôn kèm dấu ▲▼ hoặc chữ.
"""
from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go

SERIES = ["#6d3fd9", "#f2b100", "#1a9e8f", "#2f6fd6", "#c2336b"]
NEUTRAL = "#9a93ab"
UP, DOWN = "#16a34a", "#dc2626"
GRID = "rgba(109,63,217,0.08)"
FONT = "Montserrat, sans-serif"

# Giao diện tối: thay từng màu của giao diện sáng bằng màu tương ứng (bảng màu tối cũng đã chạy bộ kiểm tra
# cho người mù màu và độ tương phản trên nền tối).
DARK_COLORS = {
    "#6d3fd9": "#8a66f2", "#f2b100": "#bb8b12", "#1a9e8f": "#22a895", "#2f6fd6": "#4f7fe0", "#c2336b": "#d6588a",
    "#16a34a": "#22c55e", "#dc2626": "#ef4444", "#9a93ab": "#6f6888",
    "#fde2e2": "#4a1f2a", "#fff1d6": "#4a3a14", "#dcf5e4": "#163d2a",
    "109,63,217": "138,102,242", "194,51,107": "214,88,138", "rgba(109,63,217,0.08)": "rgba(185,162,255,0.10)",
    '"bgcolor":"white"': '"bgcolor":"#221b3d"', "#1f1937": "#ece8f7", "#d9cdf5": "#3a3163", "#8b7bb8": "#6f6390",
}


def apply_dark(fig: go.Figure) -> go.Figure:
    """Đổi màu một biểu đồ sang giao diện tối (thay chuỗi màu trong cấu hình của biểu đồ)."""
    text = fig.to_json()
    for light, dark in DARK_COLORS.items():
        text = text.replace(light, dark)
    return go.Figure(json.loads(text))
PORTFOLIO_LABEL = "Danh mục (tỷ trọng hiện tại)"
INDEX_LABEL = "VN-Index"

# Truyền vào st.plotly_chart(config=...): bỏ logo Plotly và các nút chọn vùng không dùng tới
PLOTLY_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d", "toggleSpikelines"],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}

RANGE_BUTTONS = [
    dict(count=1, label="1 tháng", step="month", stepmode="backward"),
    dict(count=3, label="3 tháng", step="month", stepmode="backward"),
    dict(count=6, label="6 tháng", step="month", stepmode="backward"),
    dict(count=1, label="1 năm", step="year", stepmode="backward"),
    dict(label="Tất cả", step="all"),
]


def _money(value: float) -> str:
    """Số tiền kiểu Việt Nam cho chú thích khi rê chuột, vd 1234567 -> '1.234.567 đ'."""
    return f"{value:,.0f} đ".replace(",", ".")


def _percent(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%".replace(".", ",")


def _gradient(color: str, top: float = 0.28, start: float | None = None, stop: float | None = None) -> dict:
    """Tô nền dưới đường theo dải màu nhạt dần xuống dưới (giống biểu đồ của các trang tài chính).
    start/stop: khoảng giá trị trục tung mà dải màu trải qua (mặc định cả vùng tô)."""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    gradient = dict(type="vertical", colorscale=[[0, f"rgba({r},{g},{b},0)"], [1, f"rgba({r},{g},{b},{top})"]])
    if start is not None and stop is not None:
        gradient.update(start=start, stop=stop)
    return gradient


def _crosshair(fig: go.Figure) -> None:
    """Đường dóng dọc chạy theo con trỏ chuột, kèm khung số liệu của mọi đường tại ngày đó."""
    fig.update_xaxes(showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1,
                     spikedash="dot", spikecolor="#8b7bb8")
    fig.update_layout(hovermode="x unified", hoverdistance=-1, spikedistance=-1)


def _layout(fig: go.Figure, title: str, y_title: str = "", y_format: str = "", height: int = 360) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=15)),
        height=height,
        margin=dict(l=10, r=10, t=50, b=10),
        hovermode="x unified",
        hoverlabel=dict(namelength=-1, bgcolor="white", bordercolor="#d9cdf5", font=dict(family=FONT, color="#1f1937")),
        font=dict(family=FONT),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1, title_text=""),
        separators=",.",  # dấu thập phân là dấu phẩy, phân cách nghìn là dấu chấm (kiểu Việt Nam)
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(title_text=y_title, gridcolor=GRID, zerolinecolor=GRID, tickformat=y_format)
    return fig


def weights_bar(valuation: pd.DataFrame, cash_weight: float, cash_value: float | None = None) -> go.Figure:
    """Tỷ trọng từng mã và tiền mặt trên tổng tài sản (thanh ngang, xếp từ lớn đến nhỏ)."""
    data = valuation.loc[valuation["has_price"]].reindex(columns=["symbol", "weight_total", "market_value"]).copy()
    cash_row = pd.DataFrame({"symbol": ["Tiền mặt"], "weight_total": [cash_weight],
                             "market_value": [cash_value if cash_value is not None else float("nan")]})
    data = pd.concat([data, cash_row]).sort_values("weight_total")
    colors = [NEUTRAL if s == "Tiền mặt" else SERIES[0] for s in data["symbol"]]
    patterns = ["/" if s == "Tiền mặt" else "" for s in data["symbol"]]
    hover = [f"<b>{s}</b><br>Tỷ trọng: {_percent(w)}" + (f"<br>Giá trị: {_money(v)}" if v == v else "")
             for s, w, v in zip(data["symbol"], data["weight_total"], data["market_value"])]
    fig = go.Figure(go.Bar(
        x=data["weight_total"], y=data["symbol"], orientation="h",
        marker=dict(color=colors, cornerradius=8, pattern=dict(shape=patterns, fgcolor="white", solidity=0.25)),
        text=[_percent(w) for w in data["weight_total"]], textposition="outside",
        customdata=hover, hovertemplate="%{customdata}<extra></extra>",
    ))
    fig.add_vline(x=0.10, line=dict(color=NEUTRAL, dash="dot", width=1),
                  annotation_text="10% (UCITS)", annotation_position="top")
    _layout(fig, "Tỷ trọng trên tổng tài sản", y_format="")
    fig.update_xaxes(tickformat=".0%", range=[0, max(0.35, float(data["weight_total"].max()) * 1.2)])
    fig.update_layout(hovermode="closest")
    return fig


def sector_bar(sectors: pd.Series) -> go.Figure:
    """Tỷ trọng từng ngành trên phần cổ phiếu."""
    data = sectors.sort_values()
    fig = go.Figure(go.Bar(
        x=data.values, y=data.index, orientation="h", marker=dict(color=SERIES[1], cornerradius=8),
        text=[_percent(w) for w in data.values], textposition="outside",
        customdata=[f"<b>{name}</b><br>{_percent(w)} phần cổ phiếu" for name, w in data.items()],
        hovertemplate="%{customdata}<extra></extra>",
    ))
    fig.add_vline(x=0.50, line=dict(color=NEUTRAL, dash="dot", width=1),
                  annotation_text="50%", annotation_position="top")
    _layout(fig, "Tỷ trọng theo ngành (phần cổ phiếu)")
    fig.update_xaxes(tickformat=".0%", range=[0, max(0.6, float(data.max()) * 1.2)])
    fig.update_layout(hovermode="closest")
    return fig


def growth_chart(portfolio_returns: pd.Series, market_returns: pd.Series,
                 extra: dict[str, pd.Series] | None = None, sessions: int = 250) -> go.Figure:
    """Giá trị của 100 đồng đầu tư: danh mục (tỷ trọng hiện tại) so với VN-Index và các mã chọn thêm."""
    series = {PORTFOLIO_LABEL: portfolio_returns, INDEX_LABEL: market_returns, **(extra or {})}
    frame = pd.concat(series, axis=1, join="inner").dropna().tail(sessions)
    fig = go.Figure()
    for i, column in enumerate(frame.columns):
        values = 100 * (1 + frame[column]).cumprod()
        fig.add_trace(go.Scatter(
            x=pd.to_datetime(values.index), y=values, name=column, mode="lines",
            line=dict(color=SERIES[i % len(SERIES)], width=3 if i == 0 else 2, shape="spline", smoothing=0.3),
            hovertemplate=f"{column}: %{{y:,.1f}}<extra></extra>",
        ))
    fig.add_hline(y=100, line=dict(color=NEUTRAL, dash="dot", width=1))
    _layout(fig, "Giá trị của 100 đồng đầu tư", y_title="Giá trị (mốc = 100)", height=420)
    _crosshair(fig)
    fig.update_xaxes(tickformat="%m/%Y", hoverformat="%d/%m/%Y",
                     rangeslider=dict(visible=True, thickness=0.07))
    return fig


def drawdown_chart(portfolio_returns: pd.Series, sessions: int = 250) -> go.Figure:
    """Mức giảm so với đỉnh gần nhất của danh mục theo thời gian."""
    returns = portfolio_returns.dropna().tail(sessions)
    wealth = (1 + returns).cumprod()
    drawdown = wealth / wealth.cummax().clip(lower=1.0) - 1
    fig = go.Figure(go.Scatter(
        x=pd.to_datetime(drawdown.index), y=drawdown, mode="lines", fill="tozeroy",
        line=dict(color=SERIES[4], width=2), fillgradient=dict(type="vertical", colorscale=[
            [0, "rgba(194,51,107,0.30)"], [1, "rgba(194,51,107,0.02)"]]), name="Mức giảm từ đỉnh",
        hovertemplate="Giảm từ đỉnh: %{y:.1%}<extra></extra>",
    ))
    _layout(fig, "Mức giảm so với đỉnh (drawdown)", y_format=".0%", height=320)
    _crosshair(fig)
    fig.update_xaxes(tickformat="%m/%Y", hoverformat="%d/%m/%Y")
    return fig


def returns_histogram(portfolio_returns: pd.Series, var_pct: float, window: int = 250) -> go.Figure:
    """Phân phối lợi suất ngày của danh mục và vị trí ngưỡng VaR 95%."""
    returns = portfolio_returns.dropna().tail(window)
    fig = go.Figure(go.Histogram(
        x=returns, nbinsx=40, marker=dict(color=SERIES[0], line=dict(color="white", width=1), cornerradius=4),
        name="Số phiên", hovertemplate="Lợi suất %{x:.1%}: %{y} phiên<extra></extra>",
    ))
    if var_pct == var_pct:
        fig.add_vline(x=-var_pct, line=dict(color=SERIES[4], width=2, dash="dash"),
                      annotation_text=f"VaR 95% = −{var_pct:.1%}".replace(".", ","),
                      annotation_position="top left")
    _layout(fig, f"Phân phối lợi suất ngày ({len(returns)} phiên gần nhất)", y_title="Số phiên", height=320)
    fig.update_xaxes(tickformat=".0%")
    fig.update_layout(hovermode="closest", bargap=0.05)
    return fig


def stress_bar(stress_1: pd.DataFrame, stress_3: pd.DataFrame) -> go.Figure:
    """Tổn thất từng mã nếu giảm sàn 1 phiên và 3 phiên liên tiếp."""
    fig = go.Figure()
    for i, (label, frame) in enumerate([("Giảm sàn 1 phiên", stress_1), ("Giảm sàn 3 phiên liên tiếp", stress_3)]):
        fig.add_trace(go.Bar(
            x=frame["symbol"], y=frame["loss"], name=label, marker=dict(color=SERIES[i], cornerradius=4),
                customdata=[_money(v) for v in frame["loss"]],
            hovertemplate=f"<b>%{{x}}</b><br>{label}: lỗ %{{customdata}}<extra></extra>",
        ))
    _layout(fig, "Tổn thất theo kịch bản giảm sàn", y_title="Đồng", y_format=",.0f")
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08, hovermode="closest")
    return fig


def index_chart(index_close: pd.Series) -> go.Figure:
    """Diễn biến VN-Index theo phiên, có nút chọn nhanh khoảng thời gian và thanh trượt."""
    low, high = float(index_close.min()), float(index_close.max())
    fig = go.Figure(go.Scatter(
        x=pd.to_datetime(index_close.index), y=index_close.values, mode="lines", name=INDEX_LABEL,
        line=dict(color=SERIES[0], width=2.5), fill="tozeroy",
        fillgradient=_gradient(SERIES[0], 0.32, start=low * 0.95, stop=high),
        hovertemplate="VN-Index: %{y:,.2f} điểm<extra></extra>",
    ))
    _layout(fig, "Diễn biến VN-Index", y_title="Điểm", height=420)
    _crosshair(fig)
    fig.update_yaxes(range=[low * 0.95, high * 1.03])
    fig.update_xaxes(tickformat="%m/%Y", hoverformat="%d/%m/%Y",
                     rangeselector=dict(buttons=RANGE_BUTTONS, x=1, xanchor="right", y=1.04, yanchor="bottom"),
                     rangeslider=dict(visible=True, thickness=0.07))
    fig.update_layout(showlegend=False, title=dict(y=0.97))
    return fig


def _session_labels(summary: pd.DataFrame) -> list[str]:
    return [pd.Timestamp(d).strftime("%d/%m") for d in summary["trading_date"]]


def foreign_flow_bar(summary: pd.DataFrame) -> go.Figure:
    """Giá trị mua ròng của khối ngoại toàn sàn theo phiên (tỷ đồng): dương = mua ròng, âm = bán ròng."""
    values = summary["foreign_net_value"].astype(float) / 1e9
    colors = [UP if v >= 0 else DOWN for v in values]
    hover = [f"<b>Phiên {pd.Timestamp(d).strftime('%d/%m/%Y')}</b><br>"
             + ("Mua ròng" if v >= 0 else "Bán ròng") + f": {abs(v):,.0f} tỷ đ".replace(",", ".")
             for d, v in zip(summary["trading_date"], values)]
    fig = go.Figure(go.Bar(
        x=_session_labels(summary), y=values, marker=dict(color=colors, cornerradius=6),
        customdata=hover, hovertemplate="%{customdata}<extra></extra>",
    ))
    fig.add_hline(y=0, line=dict(color=NEUTRAL, width=1))
    _layout(fig, "Khối ngoại mua ròng (tỷ đồng)", y_title="Tỷ đồng", y_format=",.0f", height=320)
    fig.update_xaxes(type="category")
    fig.update_layout(hovermode="closest", showlegend=False)
    return fig


def breadth_chart(summary: pd.DataFrame) -> go.Figure:
    """Số mã tăng và số mã giảm của sàn theo phiên (độ rộng thị trường)."""
    labels = _session_labels(summary)
    fig = go.Figure()
    for column, name, color in [("advances", "▲ Số mã tăng", UP), ("declines", "▼ Số mã giảm", DOWN)]:
        fig.add_trace(go.Bar(
            x=labels, y=summary[column], name=name, marker=dict(color=color, cornerradius=6),
            hovertemplate=f"{name}: %{{y:,.0f}}<extra></extra>",
        ))
    _layout(fig, "Độ rộng thị trường: số mã tăng / giảm", y_title="Số mã", y_format=",.0f", height=340)
    fig.update_xaxes(type="category")
    fig.update_layout(margin=dict(t=80), legend=dict(y=1.06))
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.06)
    return fig


def diversity_scale(effective_n: float, good: float = 10, concentrated: float = 5) -> go.Figure:
    """Thang "mức đa dạng hóa": 3 vùng theo ngưỡng Evans & Archer (1968) và vị trí danh mục của bạn.

    Dễ đọc hơn đồng hồ: một thanh ngang chia 3 vùng có ghi chữ, mũi tên chỉ vào số mã hiệu dụng của bạn.
    """
    top = max(15.0, float(effective_n) + 2) if effective_n == effective_n else 15.0
    zones = [(0, concentrated, "#fde2e2", "Tập trung cao"), (concentrated, good, "#fff1d6", "Trung bình"),
             (good, top, "#dcf5e4", "Đa dạng tốt")]
    fig = go.Figure()
    for low, high, color, label in zones:
        fig.add_trace(go.Bar(
            x=[high - low], y=[""], base=[low], orientation="h", marker=dict(color=color, cornerradius=10),
            text=[f"<b>{label}</b>"], textposition="inside", insidetextanchor="middle",
            textfont=dict(color="#1f1937", size=13), hovertemplate=f"{label}: %{{base:.0f}}–{high:.0f} mã<extra></extra>",
            showlegend=False, width=0.55,
        ))
    if effective_n == effective_n:
        value = f"{effective_n:.1f}".replace(".", ",")
        fig.add_trace(go.Scatter(
            x=[effective_n], y=[""], mode="markers", marker=dict(symbol="diamond", size=20, color=SERIES[0],
                                                                  line=dict(color="white", width=2)),
            hovertemplate=f"Danh mục của bạn: {value} mã<extra></extra>", showlegend=False,
        ))
        fig.add_annotation(x=effective_n, y=0.42, yref="paper", text=f"<b>Bạn: {value} mã</b>", showarrow=True,
                           arrowhead=0, ay=-34, ax=0, font=dict(color=SERIES[0], size=15), arrowcolor=SERIES[0])
    fig.update_layout(height=230, margin=dict(l=10, r=10, t=60, b=30), barmode="overlay", separators=",.",
                      font=dict(family=FONT), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      title=dict(text="Mức đa dạng hóa (số mã hiệu dụng)", font=dict(size=15)),
                      hoverlabel=dict(bgcolor="white", bordercolor="#d9cdf5", font=dict(family=FONT, color="#1f1937")))
    fig.update_xaxes(range=[0, top], tickvals=[0, concentrated, good, top], showgrid=False, title_text="Số mã hiệu dụng")
    fig.update_yaxes(showticklabels=False, showgrid=False)
    return fig


def backtest_chart(series: pd.DataFrame) -> go.Figure:
    """Kiểm định VaR: lợi suất từng ngày (cột) và ngưỡng −VaR dự báo trước đó (đường); ngày lỗ vượt VaR tô đỏ."""
    dates = pd.to_datetime(series.index)
    colors = [DOWN if hit else "#b9a2ff" for hit in series["exception"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=dates, y=series["return"], name="Lợi suất ngày", marker=dict(color=colors),
        hovertemplate="Lợi suất: %{y:.2%}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=-series["var"], name="Ngưỡng VaR 95% (dự báo hôm trước)", mode="lines",
        line=dict(color=SERIES[1], width=2.5), hovertemplate="−VaR: %{y:.2%}<extra></extra>",
    ))
    hits = series[series["exception"]]
    fig.add_trace(go.Scatter(
        x=pd.to_datetime(hits.index), y=hits["return"], name="Ngày lỗ vượt VaR", mode="markers",
        marker=dict(color=DOWN, size=8, symbol="x"), hovertemplate="Vượt VaR: %{y:.2%}<extra></extra>",
    ))
    _layout(fig, "Kiểm định VaR: lỗ thực tế so với ngưỡng dự báo", y_title="Lợi suất ngày", y_format=".0%", height=400)
    _crosshair(fig)
    fig.update_xaxes(tickformat="%m/%Y", hoverformat="%d/%m/%Y", rangeslider=dict(visible=True, thickness=0.07))
    fig.update_layout(bargap=0)
    return fig
