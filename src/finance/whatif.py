"""
Thử điều chỉnh (bước "kê đơn" của một lần khám): đổi tỷ trọng các mã đang có rồi khám lại.

Chỉ là MÔ PHỎNG trên cùng dữ liệu giá lịch sử, không đặt lệnh và không khuyến nghị mua/bán mã cụ thể nào:
người dùng tự chọn tỷ trọng, sản phẩm cho biết kết quả kiểm tra thay đổi ra sao.

    portfolio_from_weights   tỷ trọng mục tiêu -> danh mục (số lượng lẻ, đúng tỷ trọng) cùng tổng tài sản
    to_lots                  làm tròn số lượng theo lô 100 khi áp dụng vào danh mục thật của người dùng
    compare_reports          bảng so sánh các chỉ số chính trước/sau
"""
from __future__ import annotations

import pandas as pd

from src.finance.examples import LOT_SIZE
from src.finance.health import DANGER, GOOD, INFO, WARNING, HealthReport, overall_verdict, pct
from src.finance.portfolio import Portfolio

STATUS_RANK = {DANGER: 0, WARNING: 1, GOOD: 2, INFO: 2}


def portfolio_from_weights(weights: dict[str, float], prices: pd.Series, total: float,
                           avg_costs: dict[str, float] | None = None) -> Portfolio:
    """Danh mục có cùng tổng tài sản `total`, mỗi mã chiếm đúng `weights[mã]`; phần còn lại là tiền mặt.

    Số lượng để dạng số lẻ để tỷ trọng chính xác (chỉ dùng cho mô phỏng). Tổng tỷ trọng phải ≤ 100%.
    """
    invested = sum(weights.values())
    if invested > 1 + 1e-9:
        raise ValueError("Tổng tỷ trọng cổ phiếu vượt 100%")
    rows = []
    for symbol, weight in weights.items():
        price = prices.get(symbol)
        if weight <= 0 or price is None or not price > 0:
            continue
        rows.append({"symbol": symbol, "quantity": weight * total / float(price),
                     "avg_cost": (avg_costs or {}).get(symbol)})
    holdings = pd.DataFrame(rows, columns=["symbol", "quantity", "avg_cost"])
    return Portfolio(holdings=holdings, cash=max(0.0, total * (1 - invested)))


def to_lots(portfolio: Portfolio, prices: pd.Series, lot: int = LOT_SIZE) -> tuple[pd.DataFrame, float]:
    """Làm tròn số lượng về bội số của lô (≥ 1 lô); phần chênh lệch cộng/trừ vào tiền mặt (không âm)."""
    frame = portfolio.holdings.copy()
    if frame.empty:
        return frame, portfolio.cash
    before = float((frame["quantity"] * frame["symbol"].map(prices)).sum())
    frame["quantity"] = (frame["quantity"] / lot).round().clip(lower=1).astype(int) * lot
    after = float((frame["quantity"] * frame["symbol"].map(prices)).sum())
    return frame, max(0.0, round(portfolio.cash + before - after, -3))


def _top_sector(report: HealthReport) -> str:
    if report.sectors.empty:
        return "không đủ dữ liệu"
    return f"{report.sectors.index[0]}: {pct(float(report.sectors.iloc[0]))}"


def key_metrics(report: HealthReport) -> dict[str, str]:
    """Các chỉ số chính, đã định dạng, theo thứ tự hiển thị."""
    valuation = report.valuation.dropna(subset=["weight_total"])
    top = valuation.sort_values("weight_total", ascending=False).head(1)
    m = report.metrics
    level, label, _ = overall_verdict(report.checks)
    return {
        "Kết luận chung": label,
        "Mã lớn nhất": f"{top['symbol'].iloc[0]}: {pct(float(top['weight_total'].iloc[0]))}" if not top.empty else "—",
        "Ngành lớn nhất": _top_sector(report),
        "Tiền mặt": pct(report.totals["cash_weight"]),
        "Biến động 1 năm": pct(m["volatility"]),
        "Mức lỗ phiên xấu (VaR 95%)": pct(m["var_pct"]),
        "Sụt giảm tối đa 1 năm": pct(m["max_drawdown_1y"]),
        "Lỗ nếu mọi mã giảm sàn 1 phiên": pct(m["floor_loss_1"] / report.totals["total_value"])
        if report.totals["total_value"] else "—",
    }


def compare_reports(before: HealthReport, after: HealthReport) -> pd.DataFrame:
    """Bảng "Hiện tại" / "Sau điều chỉnh" cho các chỉ số chính."""
    a, b = key_metrics(before), key_metrics(after)
    return pd.DataFrame({"Chỉ số": list(a), "Hiện tại": list(a.values()), "Sau điều chỉnh": [b[k] for k in a]})


def changed_checks(before: HealthReport, after: HealthReport) -> pd.DataFrame:
    """Các tiêu chí đổi mức đánh giá sau khi điều chỉnh; cột direction: 'tốt lên' / 'xấu đi'."""
    old = {c.name: c for c in before.checks}
    rows = []
    for check in after.checks:
        prev = old.get(check.name)
        if prev is None or prev.status == check.status or INFO in (prev.status, check.status):
            continue
        better = STATUS_RANK[check.status] > STATUS_RANK[prev.status]
        rows.append({"name": check.name, "before": prev.status, "after": check.status,
                     "value_before": prev.value, "value_after": check.value,
                     "direction": "tốt lên" if better else "xấu đi"})
    return pd.DataFrame(rows, columns=["name", "before", "after", "value_before", "value_after", "direction"])



