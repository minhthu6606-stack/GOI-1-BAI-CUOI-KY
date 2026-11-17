"""
Tổng hợp "báo cáo sức khỏe danh mục": chạy mọi thước đo, so với ngưỡng có nguồn,
và sinh lời giải thích bằng tiếng Việt theo quy tắc (KHÔNG dùng mô hình ngôn ngữ, nên
không có nguy cơ "bịa" nội dung - mọi câu giải thích đều suy ra trực tiếp từ con số).

Mỗi kiểm tra (Check) có trạng thái:
    "Tốt"         đạt ngưỡng
    "Cảnh báo"    vượt ngưỡng tham chiếu
    "Rủi ro cao"  vượt ngưỡng nghiêm trọng
    "Thông tin"   thước đo mô tả, không có ngưỡng chuẩn để xếp loại

Đây là công cụ phân tích học thuật, không phải khuyến nghị đầu tư.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.finance import concentration, liquidity, risk, stress
from src.finance.market_data import MarketData
from src.finance.portfolio import Portfolio, value_portfolio

GOOD, WARNING, DANGER, INFO = "Tốt", "Cảnh báo", "Rủi ro cao", "Thông tin"
DISCLAIMER = "Công cụ phân tích học thuật, không phải khuyến nghị đầu tư."


@dataclass
class Check:
    group: str          # Tập trung / Thanh khoản / Rủi ro thị trường / Kịch bản / Khối ngoại
    name: str
    value: str          # giá trị đã định dạng để hiển thị
    status: str
    threshold: str      # ngưỡng so sánh
    explanation: str    # giải thích cho người dùng
    source: str = ""    # cơ sở của ngưỡng


@dataclass
class HealthReport:
    valuation: pd.DataFrame
    totals: dict
    sectors: pd.Series
    liquidity: pd.DataFrame
    metrics: dict
    stress_1: pd.DataFrame
    stress_3: pd.DataFrame
    portfolio_returns: pd.Series
    market_returns: pd.Series
    checks: list[Check] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def checks_frame(self) -> pd.DataFrame:
        return pd.DataFrame([c.__dict__ for c in self.checks])


def pct(value: float, digits: int = 1) -> str:
    """Định dạng tỷ lệ thành phần trăm kiểu Việt Nam, vd 0.1234 -> '12,3%'."""
    if value is None or value != value:
        return "không đủ dữ liệu"
    return f"{value * 100:.{digits}f}%".replace(".", ",")


def num(value: float, digits: int = 2) -> str:
    """Định dạng số thập phân kiểu Việt Nam, vd 1.234 -> '1,23'."""
    if value is None or value != value:
        return "không đủ dữ liệu"
    return f"{value:.{digits}f}".replace(".", ",")


def vnd(value: float) -> str:
    """Định dạng tiền kiểu Việt Nam, vd 1234567 -> '1.234.567 đ'."""
    if value is None or value != value:
        return "không đủ dữ liệu"
    return f"{value:,.0f} đ".replace(",", ".")


def build_health_report(portfolio: Portfolio, market: MarketData,
                        participation: float = liquidity.DEFAULT_PARTICIPATION) -> HealthReport:
    notes: list[str] = []
    if market.missing_symbols:
        notes.append(f"Chưa có dữ liệu cho: {', '.join(market.missing_symbols)}. Các mã này bị loại khỏi phép tính.")

    latest_prices = market.latest["close"] if not market.latest.empty else pd.Series(dtype=float)
    valuation, totals = value_portfolio(portfolio, latest_prices)
    weights_total = valuation.set_index("symbol")["weight_total"].dropna()
    boards = market.securities.set_index("symbol")["board"] if not market.securities.empty else pd.Series(dtype=str)

    # ----- Tập trung
    ucits = concentration.ucits_check(weights_total)
    n_eff = concentration.effective_number(valuation.set_index("symbol")["market_value"])
    sectors = concentration.sector_weights(valuation, market.securities)

    # ----- Thanh khoản
    adv = liquidity.average_daily_volume(market.volume)
    liq = liquidity.liquidity_table(valuation, adv, participation)
    illiquid = liquidity.illiquid_share(liq)

    # ----- Rủi ro thị trường
    stock_returns = risk.daily_returns(market.close)
    port_ret = risk.portfolio_returns(stock_returns, weights_total)
    market_ret = risk.daily_returns(market.index_close)
    last_year = port_ret.tail(risk.TRADING_DAYS_PER_YEAR)
    metrics = {
        "volatility": risk.annualized_volatility(last_year),
        "market_volatility": risk.annualized_volatility(market_ret.tail(risk.TRADING_DAYS_PER_YEAR)),
        "beta": risk.beta(port_ret, market_ret),
        "var_pct": risk.historical_var(port_ret),
        "max_drawdown_1y": risk.max_drawdown(last_year),
        "return_sessions": int(len(port_ret)),
    }
    metrics["var_amount"] = metrics["var_pct"] * totals["total_value"]

    # ----- Kịch bản giảm sàn
    stress_1, s1 = stress.floor_scenario(valuation, boards, sessions=1)
    stress_3, s3 = stress.floor_scenario(valuation, boards, sessions=3)
    metrics["floor_loss_1"] = s1["total_loss"]
    metrics["floor_loss_3"] = s3["total_loss"]

    report = HealthReport(valuation, totals, sectors, liq, metrics, stress_1, stress_3, port_ret, market_ret,
                          notes=notes)
    _add_checks(report, ucits, n_eff, sectors, illiquid, participation, market)
    return report


def _add_checks(report: HealthReport, ucits: dict, n_eff: float, sectors: pd.Series,
                illiquid: float, participation: float, market: MarketData) -> None:
    add = report.checks.append
    m, total = report.metrics, report.totals["total_value"]

    # 1. Mã lớn nhất so với chuẩn UCITS 10%
    max_w = ucits["max_weight"]
    add(Check(
        "Tập trung", "Tỷ trọng mã lớn nhất", f"{ucits['max_symbol']}: {pct(max_w)}",
        WARNING if ucits["breach_single"] else GOOD, "≤ 10% tổng tài sản",
        (f"{ucits['max_symbol']} chiếm {pct(max_w)} tổng tài sản. "
         + (f"Các mã vượt 10%: {', '.join(ucits['over_single_limit'])}. Nếu một mã giảm mạnh, cả danh mục chịu ảnh hưởng lớn."
            if ucits["breach_single"] else "Không mã nào vượt 10%.")),
        "UCITS 2009/65/EC, Điều 52 (chuẩn tham chiếu của quỹ đại chúng)",
    ))
    # 2. Tổng các khoản lớn (quy tắc 40%)
    add(Check(
        "Tập trung", "Tổng các mã chiếm trên 5%", pct(ucits["large_positions_sum"]),
        WARNING if ucits["breach_aggregate"] else GOOD, "≤ 40% tổng tài sản",
        f"Các mã chiếm trên 5% cộng lại bằng {pct(ucits['large_positions_sum'])} tổng tài sản.",
        "UCITS 2009/65/EC, Điều 52 (quy tắc 5/10/40)",
    ))
    # 3. Số mã hiệu dụng
    if n_eff == n_eff:
        status = DANGER if n_eff < concentration.EFFECTIVE_N_CONCENTRATED else (
            WARNING if n_eff < concentration.EFFECTIVE_N_WELL_DIVERSIFIED else GOOD)
        value = num(n_eff, 1)
    else:
        status, value = INFO, "không đủ dữ liệu"
    add(Check(
        "Tập trung", "Số mã hiệu dụng (1/HHI)", value, status, "≥ 10 mã: tốt; < 5 mã: tập trung cao",
        f"Về mức đa dạng hóa, danh mục tương đương {value} mã có tỷ trọng bằng nhau.",
        "Evans & Archer (1968)",
    ))
    # 4. Ngành lớn nhất
    if not sectors.empty:
        top_sector, top_weight = sectors.index[0], float(sectors.iloc[0])
        add(Check(
            "Tập trung", "Ngành chiếm tỷ trọng lớn nhất", f"{top_sector}: {pct(top_weight)}",
            WARNING if top_weight > concentration.SECTOR_LIMIT else GOOD, "≤ 50% phần cổ phiếu",
            f"Ngành {top_sector} chiếm {pct(top_weight)} phần cổ phiếu của danh mục.",
            "Quy tắc nghiệp vụ tự đặt: quá nửa danh mục phụ thuộc một ngành",
        ))
    # 5. Thanh khoản
    slow = report.liquidity[report.liquidity["bucket"] != liquidity.BUCKET_HIGH]
    slow_text = ", ".join(f"{r.symbol} ({r.days_to_cash:.0f} ngày)" for r in slow.itertuples()) or "không có"
    add(Check(
        "Thanh khoản", "Tỷ trọng tài sản thanh khoản thấp", pct(illiquid),
        WARNING if illiquid > liquidity.ILLIQUID_SHARE_LIMIT else GOOD, "≤ 15% tổng tài sản",
        (f"Giả định mỗi phiên chỉ bán tối đa {pct(participation, 0)} khối lượng trung bình 20 phiên, "
         f"cộng 2 ngày thanh toán T+2. Mã cần hơn 3 ngày làm việc để có tiền: {slow_text}."),
        "SEC Rule 22e-4 (17 CFR 270.22e-4)",
    ))
    # 6–8. Rủi ro thị trường (mô tả)
    vol, mvol = m["volatility"], m["market_volatility"]
    add(Check(
        "Rủi ro thị trường", "Độ biến động năm (250 phiên)", pct(vol), INFO, f"VN-Index: {pct(mvol)}",
        (f"Biến động của danh mục bằng {num(vol / mvol)} lần VN-Index."
         if vol == vol and mvol else "Không đủ dữ liệu để so sánh với thị trường."),
        "Độ lệch chuẩn lợi suất ngày × căn(252)",
    ))
    b = m["beta"]
    add(Check(
        "Rủi ro thị trường", "Beta so với VN-Index", num(b),
        INFO, "Beta = 1: biến động cùng nhịp thị trường",
        (f"Khi VN-Index thay đổi 1%, danh mục có xu hướng thay đổi khoảng {num(b)}%."
         if b == b else "Không đủ dữ liệu."),
        "Sharpe (1964)",
    ))
    add(Check(
        "Rủi ro thị trường", "VaR lịch sử 1 ngày, độ tin cậy 95%",
        f"{pct(m['var_pct'])} ≈ {vnd(m['var_amount'])}", INFO, "Kiểm định ngoài mẫu ở phần Kiểm chứng",
        (f"Trong 250 phiên gần nhất, 95% số phiên danh mục (với tỷ trọng hiện tại) không lỗ quá "
         f"{pct(m['var_pct'])}, tương đương {vnd(m['var_amount'])}. VaR không cho biết mức lỗ trong 5% phiên xấu nhất."),
        "Jorion (2007), mô phỏng lịch sử",
    ))
    add(Check(
        "Rủi ro thị trường", "Mức sụt giảm tối đa trong 1 năm", pct(m["max_drawdown_1y"]), INFO, "",
        f"Nếu nắm giữ danh mục này trong 250 phiên vừa qua, lúc tệ nhất giá trị giảm {pct(abs(m['max_drawdown_1y']))} so với đỉnh.",
        "Từ đỉnh xuống đáy của chuỗi giá trị danh mục",
    ))
    # 9. Kịch bản giảm sàn
    add(Check(
        "Kịch bản", "Mọi mã giảm sàn 1 phiên / 3 phiên liên tiếp",
        f"{vnd(m['floor_loss_1'])} / {vnd(m['floor_loss_3'])}", INFO,
        f"{pct(m['floor_loss_1'] / total if total else float('nan'))} / {pct(m['floor_loss_3'] / total if total else float('nan'))} tổng tài sản",
        "Kịch bản cực đoan theo biên độ sàn (HOSE 7%, HNX 10%, UPCoM 15%), dùng để hình dung rủi ro đuôi, không phải dự báo.",
        "Quy chế biên độ giá của HOSE, HNX",
    ))
    # 10. Room khối ngoại
    if not market.latest.empty and "foreign_room_remaining" in market.latest.columns:
        latest = market.latest
        room_ratio = (latest["foreign_room_remaining"] / latest["foreign_room_total"]).dropna()
        held = [s for s in report.valuation["symbol"] if s in room_ratio.index]
        if held:
            lowest = room_ratio[held].sort_values()
            add(Check(
                "Khối ngoại", "Room ngoại còn lại thấp nhất", f"{lowest.index[0]}: {pct(float(lowest.iloc[0]))}", INFO,
                "Hết room: nhà đầu tư nước ngoài không mua thêm được",
                "Tỷ lệ room còn lại / tổng room của từng mã: "
                + ", ".join(f"{s} {pct(float(v))}" for s, v in lowest.items()) + ".",
                "Dữ liệu remainForeignRoom, totalForeignRoom của SSI",
            ))
