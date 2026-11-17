"""
Các biểu đồ của ứng dụng (Plotly). Mỗi hàm nhận dữ liệu đã tính sẵn và trả về một Figure,
nên kiểm thử được mà không cần chạy giao diện.

Tương tác: rê chuột để xem số liệu từng điểm; kéo chuột để phóng to, nhấp đúp để trở lại;
bấm vào tên trong chú thích để ẩn/hiện một đường; biểu đồ theo thời gian có thanh trượt và
nút chọn nhanh khoảng thời gian.

Quy ước màu (bảng màu mặc định đã kiểm định cho người mù màu):
    - danh mục: xanh dương; VN-Index: cam; mã so sánh thêm: các màu kế tiếp theo thứ tự cố định;
    - tiền mặt: xám trung tính;
    - không dùng màu trạng thái (xanh lá/đỏ) cho chuỗi dữ liệu.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
NEUTRAL = "#9a9993"
GRID = "rgba(128,128,128,0.18)"
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


def _layout(fig: go.Figure, title: str, y_title: str = "", y_format: str = "", height: int = 360) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=15)),
        height=height,
        margin=dict(l=10, r=10, t=50, b=10),
        hovermode="x unified",
        hoverlabel=dict(namelength=-1),
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
    hover = [f"<b>{s}</b><br>Tỷ trọng: {_percent(w)}" + (f"<br>Giá trị: {_money(v)}" if v == v else "")
             for s, w, v in zip(data["symbol"], data["weight_total"], data["market_value"])]
    fig = go.Figure(go.Bar(
        x=data["weight_total"], y=data["symbol"], orientation="h", marker=dict(color=colors, cornerradius=4),
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
        x=data.values, y=data.index, orientation="h", marker=dict(color=SERIES[0], cornerradius=4),
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
            line=dict(color=SERIES[i % len(SERIES)], width=2.5 if i == 0 else 2),
            hovertemplate=f"{column}: %{{y:,.1f}}<extra></extra>",
        ))
    fig.add_hline(y=100, line=dict(color=NEUTRAL, dash="dot", width=1))
    _layout(fig, "Giá trị của 100 đồng đầu tư", y_title="Giá trị (mốc = 100)", height=420)
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
        line=dict(color=SERIES[0], width=2), fillcolor="rgba(42,120,214,0.15)", name="Mức giảm từ đỉnh",
        hovertemplate="Giảm từ đỉnh: %{y:.1%}<extra></extra>",
    ))
    _layout(fig, "Mức giảm so với đỉnh (drawdown)", y_format=".0%", height=300)
    fig.update_xaxes(tickformat="%m/%Y", hoverformat="%d/%m/%Y")
    return fig


def returns_histogram(portfolio_returns: pd.Series, var_pct: float, window: int = 250) -> go.Figure:
    """Phân phối lợi suất ngày của danh mục và vị trí ngưỡng VaR 95%."""
    returns = portfolio_returns.dropna().tail(window)
    fig = go.Figure(go.Histogram(
        x=returns, nbinsx=40, marker=dict(color=SERIES[0], line=dict(color="white", width=1)),
        name="Số phiên", hovertemplate="Lợi suất %{x:.1%}: %{y} phiên<extra></extra>",
    ))
    if var_pct == var_pct:
        fig.add_vline(x=-var_pct, line=dict(color=SERIES[1], width=2, dash="dash"),
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
    fig = go.Figure(go.Scatter(
        x=pd.to_datetime(index_close.index), y=index_close.values, mode="lines", name=INDEX_LABEL,
        line=dict(color=SERIES[0], width=2), fill="tozeroy", fillcolor="rgba(42,120,214,0.08)",
        hovertemplate="VN-Index: %{y:,.2f} điểm<extra></extra>",
    ))
    _layout(fig, "Diễn biến VN-Index", y_title="Điểm", height=420)
    low, high = float(index_close.min()), float(index_close.max())
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
    colors = [SERIES[0] if v >= 0 else SERIES[1] for v in values]
    hover = [f"<b>Phiên {pd.Timestamp(d).strftime('%d/%m/%Y')}</b><br>"
             + ("Mua ròng" if v >= 0 else "Bán ròng") + f": {abs(v):,.0f} tỷ đ".replace(",", ".")
             for d, v in zip(summary["trading_date"], values)]
    fig = go.Figure(go.Bar(
        x=_session_labels(summary), y=values, marker=dict(color=colors, cornerradius=4),
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
    for i, (column, name) in enumerate([("advances", "Số mã tăng"), ("declines", "Số mã giảm")]):
        fig.add_trace(go.Bar(
            x=labels, y=summary[column], name=name, marker=dict(color=SERIES[i], cornerradius=4),
            hovertemplate=f"{name}: %{{y:,.0f}}<extra></extra>",
        ))
    _layout(fig, "Độ rộng thị trường: số mã tăng / giảm", y_title="Số mã", y_format=",.0f", height=320)
    fig.update_xaxes(type="category")
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.06)
    return fig
