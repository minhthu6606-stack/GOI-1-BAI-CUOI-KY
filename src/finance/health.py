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
from src.finance.backtest import BacktestResult, backtest_var
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
    explanation: str    # giải thích ngắn cho người dùng
    source: str = ""    # cơ sở của ngưỡng
    action: str = ""    # "Nên làm gì?": gợi ý chung về quản trị rủi ro, KHÔNG khuyến nghị mua/bán mã cụ thể


@dataclass(frozen=True)
class RiskProfile:
    """Mức chịu rủi ro do người dùng TỰ KHAI (tùy chọn) - bước "hỏi bệnh sử" của một lần khám.

    Giống bước đánh giá mức độ phù hợp khi mở tài khoản chứng khoán: hỏi nhà đầu tư chịu lỗ được bao nhiêu.
    Khi có, VaR và sụt giảm tối đa được so với chính các mức này (thay vì "không có ngưỡng chuẩn").
        max_daily_loss  lỗ tối đa chấp nhận trong một phiên xấu, tỷ lệ (vd 0.03 = 3%)
        max_drawdown    mức giảm tối đa từ đỉnh chấp nhận trong một năm, tỷ lệ dương (vd 0.20 = 20%)
    """
    max_daily_loss: float
    max_drawdown: float


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
    backtest: BacktestResult | None = None   # kiểm định ngoài mẫu của VaR (Kupiec, Christoffersen)

    def checks_frame(self) -> pd.DataFrame:
        return pd.DataFrame([c.__dict__ for c in self.checks])


VERDICT_TEXT = {
    DANGER: ("Cần xem lại", "Danh mục có điểm rủi ro cao, nên xem lại cách phân bổ."),
    WARNING: ("Cần theo dõi", "Danh mục chưa có rủi ro cao nhưng có điểm cần theo dõi."),
    GOOD: ("Khỏe", "Danh mục đạt các ngưỡng đang kiểm tra."),
}


def overall_verdict(checks: list[Check]) -> tuple[str, str, str]:
    """Kết luận chung theo nguyên tắc "mức xấu nhất": có một mục Rủi ro cao thì cả danh mục là Rủi ro cao.

    Giống một lần khám sức khỏe: chỉ cần một chỉ số vượt ngưỡng nghiêm trọng là cần xem lại, dù các chỉ số
    khác đều tốt. Không cộng điểm hay gán trọng số (tránh phải tự đặt trọng số không có cơ sở).
    Trả về (mức, nhãn ngắn, câu kết luận).
    """
    statuses = {c.status for c in checks}
    level = DANGER if DANGER in statuses else (WARNING if WARNING in statuses else GOOD)
    label, sentence = VERDICT_TEXT[level]
    return level, label, sentence


def count_by_status(checks: list[Check]) -> dict[str, int]:
    """Đếm số mục theo từng mức, luôn đủ 4 khóa theo thứ tự Rủi ro cao, Cảnh báo, Tốt, Thông tin."""
    return {status: sum(c.status == status for c in checks) for status in (DANGER, WARNING, GOOD, INFO)}


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


def vnd_short(value: float) -> str:
    """Định dạng tiền rút gọn cho ô chỉ số, vd 500000000 -> '500,0 tr đ', 1250000000 -> '1,25 tỷ đ'."""
    if value is None or value != value:
        return "không đủ dữ liệu"
    if abs(value) >= 1e9:
        return f"{_vn_number(value / 1e9, 2)} tỷ đ"
    if abs(value) >= 1e6:
        return f"{_vn_number(value / 1e6, 1)} tr đ"
    return vnd(value)


def _vn_number(value: float, digits: int) -> str:
    """Số kiểu Việt Nam: dấu chấm phân cách nghìn, dấu phẩy thập phân (vd 8540.89 -> '8.540,89')."""
    return f"{value:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def vnd(value: float) -> str:
    """Định dạng tiền kiểu Việt Nam, vd 1234567 -> '1.234.567 đ'."""
    if value is None or value != value:
        return "không đủ dữ liệu"
    return f"{value:,.0f} đ".replace(",", ".")


def vnd_billion(value: float) -> str:
    """Tiền quy mô toàn thị trường, ghi theo tỷ đồng, vd 25432100000000 -> '25.432 tỷ đ'."""
    if value is None or value != value:
        return "không đủ dữ liệu"
    return f"{_vn_number(value / 1e9, 0)} tỷ đ"


def build_health_report(portfolio: Portfolio, market: MarketData,
                        participation: float = liquidity.DEFAULT_PARTICIPATION,
                        profile: RiskProfile | None = None) -> HealthReport:
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
        "r_squared": risk.r_squared(port_ret, market_ret),
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
                          notes=notes, backtest=backtest_var(port_ret))
    _add_checks(report, ucits, n_eff, sectors, illiquid, participation, market, profile)
    return report


def _add_checks(report: HealthReport, ucits: dict, n_eff: float, sectors: pd.Series,
                illiquid: float, participation: float, market: MarketData,
                profile: RiskProfile | None = None) -> None:
    add = report.checks.append
    m, total = report.metrics, report.totals["total_value"]

    # 1. Mã lớn nhất so với chuẩn UCITS 10%
    max_w, top = ucits["max_weight"], ucits["max_symbol"]
    add(Check(
        "Mức tập trung", "Tỷ trọng mã lớn nhất", f"{top}: {pct(max_w)}",
        WARNING if ucits["breach_single"] else GOOD, "≤ 10% tổng tài sản",
        (f"{top} chiếm {pct(max_w)} tổng tài sản"
         + (f", vượt mốc 10%. Nếu riêng {top} giảm 10%, tổng tài sản giảm khoảng {pct(max_w * 0.1)}."
            if ucits["breach_single"] else ", không mã nào vượt mốc 10%.")),
        "UCITS 2009/65/EC, Điều 52 (chuẩn tham chiếu của quỹ đại chúng)",
        ("Cân nhắc phân bổ lại để không mã nào vượt 10% tổng tài sản, hoặc chỉ giữ tỷ trọng cao ở mã bạn hiểu rõ."
         if ucits["breach_single"] else "Duy trì; kiểm tra lại khi giá một mã tăng mạnh làm tỷ trọng phình ra."),
    ))
    # 2. Tổng các khoản lớn (quy tắc 40%)
    add(Check(
        "Mức tập trung", "Tổng các mã chiếm trên 5%", pct(ucits["large_positions_sum"]),
        WARNING if ucits["breach_aggregate"] else GOOD, "≤ 40% tổng tài sản",
        (f"Các mã có tỷ trọng trên 5% cộng lại bằng {pct(ucits['large_positions_sum'])} tổng tài sản"
         + (": phần lớn tài sản phụ thuộc vào vài mã lớn." if ucits["breach_aggregate"] else ".")),
        "UCITS 2009/65/EC, Điều 52 (quy tắc 5/10/40)",
        ("Cân nhắc thêm các vị thế nhỏ hơn hoặc giữ thêm tiền mặt để giảm phụ thuộc vào vài mã lớn."
         if ucits["breach_aggregate"] else "Duy trì."),
    ))
    # 3. Số mã hiệu dụng
    if n_eff == n_eff:
        status = DANGER if n_eff < concentration.EFFECTIVE_N_CONCENTRATED else (
            WARNING if n_eff < concentration.EFFECTIVE_N_WELL_DIVERSIFIED else GOOD)
        value = num(n_eff, 1)
    else:
        status, value = INFO, "không đủ dữ liệu"
    add(Check(
        "Mức tập trung", "Mức đa dạng hóa (Số mã hiệu dụng)", f"{value} mã", status,
        "≥ 10 mã: tốt; < 5 mã: tập trung cao",
        f"Danh mục rủi ro tương đương việc nắm {value} mã có tỷ trọng bằng nhau. Từ 10 mã trở lên là đa dạng hóa tốt.",
        "Evans & Archer (1968); tính bằng 1 / HHI",
        {DANGER: "Cân nhắc thêm mã ở ngành khác hoặc chia tỷ trọng đều hơn giữa các mã đang có.",
         WARNING: "Có thể đa dạng hóa thêm bằng mã ở ngành khác.",
         GOOD: "Mức đa dạng hóa tốt; duy trì.", INFO: ""}[status],
    ))
    # 4. Ngành lớn nhất
    if not sectors.empty:
        top_sector, top_weight = sectors.index[0], float(sectors.iloc[0])
        over = top_weight > concentration.SECTOR_LIMIT
        add(Check(
            "Mức tập trung", "Ngành chiếm tỷ trọng lớn nhất", f"{top_sector}: {pct(top_weight)}",
            WARNING if over else GOOD, "≤ 50% phần cổ phiếu",
            f"Ngành {top_sector} chiếm {pct(top_weight)} phần cổ phiếu" + (", quá nửa danh mục." if over else "."),
            "Quy tắc tự đặt: quá nửa danh mục phụ thuộc một ngành",
            ("Cân nhắc bổ sung mã ở ngành khác để một tin xấu của ngành không ảnh hưởng quá nửa danh mục."
             if over else "Không ngành nào chiếm quá nửa danh mục; duy trì."),
        ))
    # 5. Thanh khoản
    slow = report.liquidity[report.liquidity["bucket"] != liquidity.BUCKET_HIGH]
    slow_text = ", ".join(f"{r.symbol} ({r.days_to_cash:.0f} ngày)" for r in slow.itertuples())
    over = illiquid > liquidity.ILLIQUID_SHARE_LIMIT
    add(Check(
        "Thanh khoản", "Tài sản khó bán nhanh", pct(illiquid),
        WARNING if over else GOOD, "≤ 15% tổng tài sản",
        (f"Giả định mỗi phiên bán tối đa {pct(participation, 0)} khối lượng giao dịch bình quân 20 phiên (ADV20). "
         + (f"Mã cần hơn 3 ngày làm việc mới có tiền: {slow_text}." if slow_text
            else "Mọi mã đều bán hết và có tiền trong 3 ngày làm việc.")),
        "SEC Rule 22e-4 (17 CFR 270.22e-4)",
        ("Giữ phần tiền có thể cần gấp ở tiền mặt hoặc mã thanh khoản cao." if over
         else "Không cần làm gì; kiểm tra lại khi quy mô vốn tăng nhiều."),
    ))
    # 6–10. Rủi ro thị trường
    vol, mvol = m["volatility"], m["market_volatility"]
    add(Check(
        "Rủi ro thị trường", "Độ biến động năm (Volatility)", pct(vol), INFO, f"VN-Index: {pct(mvol)}",
        (f"Danh mục dao động mạnh bằng {num(vol / mvol)} lần VN-Index ({pct(vol)} so với {pct(mvol)}), "
         "tính trên 250 phiên gần nhất." if vol == vol and mvol else "Không đủ dữ liệu để so sánh với thị trường."),
        "Độ lệch chuẩn lợi suất ngày × √252",
        "Thông tin để so sánh: biến động càng cao, giá trị danh mục lên xuống càng mạnh.",
    ))
    b = m["beta"]
    add(Check(
        "Rủi ro thị trường", "Độ nhạy với thị trường (Beta)", num(b), INFO, "Beta = 1: cùng nhịp VN-Index",
        (f"VN-Index tăng hoặc giảm 1% thì danh mục có xu hướng thay đổi khoảng {num(b)}%." if b == b
         else "Không đủ dữ liệu."),
        "Sharpe (1964)",
        "Beta thấp chưa chắc là ít rủi ro: xem thêm mục R² bên dưới.",
    ))
    r2 = m["r_squared"]
    r2_status = INFO if r2 != r2 else (WARNING if r2 < 0.5 else GOOD)
    add(Check(
        "Rủi ro thị trường", "Phần rủi ro đến từ thị trường chung (R²)", pct(r2, 0), r2_status,
        "≥ 50%: rủi ro chủ yếu đến từ thị trường",
        (f"Khoảng {pct(r2, 0)} biến động đến từ thị trường chung, {pct(1 - r2, 0)} còn lại là rủi ro riêng của "
         "từng mã." if r2 == r2 else "Không đủ dữ liệu."),
        "Mô hình chỉ số đơn - Sharpe (1963)",
        {WARNING: "Rủi ro riêng giảm được bằng đa dạng hóa: thêm mã ở ngành khác hoặc giảm tỷ trọng mã lớn.",
         GOOD: "Rủi ro chủ yếu đến từ thị trường chung, đa dạng hóa thêm sẽ ít tác dụng.", INFO: ""}[r2_status],
    ))
    var_pct = m["var_pct"]
    if profile is not None and var_pct == var_pct:
        var_status = GOOD if var_pct <= profile.max_daily_loss else WARNING
        var_threshold = f"≤ {pct(profile.max_daily_loss, 1)} (mức bạn chịu được)"
        var_source = "Jorion (2007), mô phỏng lịch sử; ngưỡng do bạn tự khai"
        var_action = ("Nằm trong mức bạn chịu được." if var_status == GOOD else
                      "Vượt mức bạn chịu được: cân nhắc giảm tỷ trọng cổ phiếu biến động mạnh hoặc giữ thêm tiền mặt "
                      "(thử ở trang Thử điều chỉnh).")
    else:
        var_status, var_threshold = INFO, "Không có ngưỡng chuẩn (khai mức chịu lỗ để so)"
        var_source = "Jorion (2007), mô phỏng lịch sử"
        var_action = ("Nếu mức lỗ này vượt khả năng chịu đựng của bạn, cân nhắc giảm tỷ trọng cổ phiếu hoặc giữ thêm "
                      "tiền mặt.")
    add(Check(
        "Rủi ro thị trường", "Mức lỗ trong một phiên xấu (VaR 95%)", f"{pct(var_pct)} ≈ {vnd(m['var_amount'])}",
        var_status, var_threshold,
        (f"Trong 100 phiên, khoảng 95 phiên danh mục không lỗ quá {pct(var_pct)} "
         f"(≈ {vnd(m['var_amount'])}); 5 phiên còn lại có thể lỗ nhiều hơn. Tính trên 250 phiên gần nhất."),
        var_source, var_action,
    ))
    bt = report.backtest
    if bt is not None and bt.observations:
        if bt.passes_pof and bt.passes_independence:
            bt_status = GOOD
            bt_action = "Mô hình VaR đạt kiểm định: có thể dùng con số VaR làm tham khảo."
        elif not bt.passes_independence:
            bt_status = WARNING
            bt_action = ("Các ngày lỗ vượt VaR có xu hướng dồn vào cùng giai đoạn: khi thị trường xấu, lỗ có thể "
                         "kéo dài nhiều phiên liền, đừng xem VaR như mức lỗ tối đa.")
        elif bt.too_few_exceptions:
            bt_status = INFO
            bt_action = ("VaR đang thận trọng (lỗ thực tế ít khi vượt mức dự báo): con số VaR có thể cao hơn rủi ro "
                         "thực tế, dùng làm tham khảo theo hướng an toàn.")
        else:
            bt_status = WARNING
            bt_action = ("Lỗ thực tế vượt VaR nhiều hơn kỳ vọng: xem con số VaR như mức tối thiểu, thực tế có thể "
                         "lỗ nhiều hơn.")
        add(Check(
            "Rủi ro thị trường", "Độ tin cậy của VaR (kiểm định ngoài mẫu)",
            f"{bt.exceptions}/{bt.observations} ngày vượt VaR ({pct(bt.exception_rate)})", bt_status,
            "Tỷ lệ vượt gần 5%; p-value Kupiec và Christoffersen ≥ 5%",
            (f"Tính lại VaR từng ngày trong {bt.observations} phiên quá khứ (chỉ dùng dữ liệu trước ngày đó, giữ tỷ "
             f"trọng hiện tại): lỗ thực tế vượt VaR {bt.exceptions} lần, kỳ vọng khoảng {bt.expected_exceptions:.0f} "
             f"lần. p-value Kupiec {num(bt.p_pof, 2)}, Christoffersen {num(bt.p_ind, 2)}."),
            "Kupiec (1995); Christoffersen (1998)",
            bt_action,
        ))
    drawdown = abs(m["max_drawdown_1y"]) if m["max_drawdown_1y"] == m["max_drawdown_1y"] else float("nan")
    if profile is not None and drawdown == drawdown:
        dd_status = GOOD if drawdown <= profile.max_drawdown else WARNING
        dd_threshold = f"≤ {pct(profile.max_drawdown, 0)} (mức bạn chịu được)"
        dd_source = "Từ đỉnh xuống đáy của chuỗi giá trị danh mục; ngưỡng do bạn tự khai"
        dd_action = ("Nằm trong mức bạn chịu được." if dd_status == GOOD else
                     "Năm qua danh mục từng giảm sâu hơn mức bạn chịu được: nếu gặp lại, bạn có thể phải bán ở đáy. "
                     "Cân nhắc giảm rủi ro (thử ở trang Thử điều chỉnh).")
    else:
        dd_status, dd_threshold = INFO, "Không có ngưỡng chuẩn (khai mức chịu lỗ để so)"
        dd_source = "Từ đỉnh xuống đáy của chuỗi giá trị danh mục"
        dd_action = ("Tự hỏi: nếu danh mục giảm chừng đó, bạn có phải bán ra không? Nếu có, mức rủi ro hiện tại có thể "
                     "quá cao.")
    add(Check(
        "Rủi ro thị trường", "Sụt giảm tối đa 1 năm (Max Drawdown)", pct(m["max_drawdown_1y"]), dd_status,
        dd_threshold,
        f"Nếu nắm danh mục này trong 250 phiên vừa qua, có lúc giá trị giảm {pct(drawdown)} so với đỉnh trước đó.",
        dd_source, dd_action,
    ))
    # 11. Kịch bản giảm sàn
    share_1 = m["floor_loss_1"] / total if total else float("nan")
    share_3 = m["floor_loss_3"] / total if total else float("nan")
    add(Check(
        "Kịch bản xấu", "Mọi mã cùng giảm sàn", f"1 phiên: {vnd(m['floor_loss_1'])}",
        INFO, f"{pct(share_1)} (1 phiên) / {pct(share_3)} (3 phiên) tổng tài sản",
        (f"Nếu mọi mã cùng giảm sàn, bạn lỗ {vnd(m['floor_loss_1'])} sau 1 phiên và {vnd(m['floor_loss_3'])} sau "
         "3 phiên liên tiếp. Đây là kịch bản cực đoan, không phải dự báo."),
        "Biên độ giá HOSE 7%, HNX 10%, UPCoM 15%",
        "Giữ một phần tiền mặt đủ dùng để không bị buộc phải bán trong những phiên như vậy.",
    ))
    # 12. Room khối ngoại
    if not market.latest.empty and "foreign_room_remaining" in market.latest.columns:
        latest = market.latest
        room_ratio = (latest["foreign_room_remaining"] / latest["foreign_room_total"]).dropna()
        held = [s for s in report.valuation["symbol"] if s in room_ratio.index]
        if held:
            lowest = room_ratio[held].sort_values()
            full = [s for s, v in lowest.items() if v <= 0]
            explanation = "Room còn lại / tổng room: " + ", ".join(f"{s} {pct(float(v))}" for s, v in lowest.items()) + "."
            if full:
                explanation += f" {', '.join(full)} đã hết room: khối ngoại chỉ mua được khi có nhà đầu tư nước ngoài khác bán."
            add(Check(
                "Khối ngoại", "Room ngoại còn lại (Foreign room)", f"{lowest.index[0]}: {pct(float(lowest.iloc[0]))}",
                INFO, "Hết room: nhà đầu tư nước ngoài không mua thêm được", explanation,
                "Trường remainForeignRoom, totalForeignRoom của SSI",
                "Thông tin tham khảo: mã hết room có lực mua từ khối ngoại bị giới hạn.",
            ))
