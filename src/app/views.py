"""
Nội dung từng trang của ứng dụng. Mỗi hàm nhận AppContext (đã tính sẵn ở main.py) và vẽ một trang.

Thứ tự trang trên thanh điều hướng:
    Bắt đầu:              Trang chủ · Nhập danh mục
    Kết quả kiểm tra:     Tổng quan · Cảnh báo · Phân bổ · Rủi ro · Thanh khoản & giảm sàn
    Thị trường & dữ liệu: Thị trường · Phương pháp & dữ liệu
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd
import streamlit as st

from src import config
from src.app import charts
from src.app.style import HERO_ART
from src.app.ui import (
    DATASET_LABELS, ICONS, KIND_LABELS, MODE_LABELS, RESULT_LABELS, STATUS_BADGE, format_date, format_time,
)
from src.finance.health import (
    DANGER, DISCLAIMER, GOOD, INFO, WARNING, Check, HealthReport, count_by_status, num, overall_verdict, pct, vnd,
    vnd_billion,
)
from src.finance.market_data import MarketData
from src.finance.portfolio import Portfolio

PERIODS = {"1 năm": 250, "2 năm": 500, "3 năm": 750}
HOW_TO_INTERACT = "Rê chuột để xem số liệu từng ngày, kéo chuột để phóng to, nhấp đúp để trở lại."


@dataclass
class AppContext:
    """Mọi thứ các trang cần, tính một lần mỗi lượt chạy."""

    live: bool                                  # True: đọc kho data/ trên máy; False: bản lưu kèm mã nguồn
    has_key: bool                               # máy có API key SSI trong .env
    up_to_date: bool                            # đã tải từ SSI sau giờ chốt của phiên gần nhất
    portfolio: Portfolio | None = None
    portfolio_error: str = ""
    market: MarketData | None = None
    report: HealthReport | None = None
    store_info: dict[str, pd.DataFrame] = field(default_factory=dict)
    data_error: str = ""
    pages: dict[str, Any] = field(default_factory=dict)   # st.Page theo khóa, để tạo liên kết giữa các trang
    save_portfolio: Callable[[pd.DataFrame, float], None] | None = None
    reset_portfolio: Callable[[], None] | None = None


# ====================================================================== phần dùng chung

def badge(status: str, text: str | None = None) -> str:
    """Nhãn màu dạng markdown, vd ':red-badge[:material/error: Rủi ro cao]'."""
    color, icon = STATUS_BADGE[status]
    return f":{color}-badge[{icon} {text or status}]"


def page_header(title: str, question: str) -> None:
    st.title(title)
    st.caption(question)


def how_to_read(text: str) -> None:
    st.caption(f"**Cách đọc:** {text}")


def plot(fig) -> None:
    st.plotly_chart(fig, width="stretch", config=charts.PLOTLY_CONFIG)


def chart_card(fig, note: str, column=None) -> None:
    """Biểu đồ đặt trong một thẻ, kèm dòng "Cách đọc" ngay bên dưới."""
    target = column if column is not None else st
    with target.container(key=card_key(note[:60]), height="stretch"):
        plot(fig)
        how_to_read(note)


def find_check(report: HealthReport, name_start: str) -> Check | None:
    return next((c for c in report.checks if c.name.startswith(name_start)), None)


def card_key(text: str) -> str:
    """Khóa của thẻ (CSS tạo kiểu cho mọi container có khóa bắt đầu bằng "card")."""
    return "card_" + hashlib.md5(text.encode("utf-8")).hexdigest()[:10]


def kpi_card(column, label: str, value: str, note: str, status: str | None = None, delta: str | None = None) -> None:
    """Một ô chỉ số: tên, con số, nhãn mức và một dòng giải thích. Các ô cùng hàng cao bằng nhau."""
    with column.container(key=card_key(label), height="stretch"):
        st.markdown(f"**{label}**")
        st.metric(label, value, delta=delta, label_visibility="collapsed")
        st.markdown((f"{badge(status)} &nbsp; " if status else "") + f":gray[{note}]")


def require_report(ctx: AppContext) -> bool:
    """Trang phân tích cần danh mục hợp lệ và dữ liệu; nếu thiếu thì nói rõ lý do và cách xử lý."""
    if ctx.portfolio_error:
        st.error(f"Danh mục chưa hợp lệ: {ctx.portfolio_error}")
        st.page_link(ctx.pages["portfolio"], label="Sửa danh mục", icon=ICONS["portfolio"])
        return False
    if ctx.data_error or ctx.report is None:
        st.error(ctx.data_error or "Không đủ dữ liệu để phân tích danh mục này.")
        return False
    return True


def show_missing_symbols(ctx: AppContext) -> None:
    if ctx.market and ctx.market.missing_symbols:
        hint = ("Bấm **Cập nhật dữ liệu** ở thanh bên để tải các mã này từ SSI." if ctx.has_key
                else "Máy này chưa có API key SSI nên chưa tải được mã mới.")
        st.warning(f"Chưa có dữ liệu cho **{', '.join(ctx.market.missing_symbols)}**, các mã này tạm chưa được "
                   f"tính. {hint}")


# ====================================================================== Trang chủ

FEATURES = [  # (tên biểu tượng Material Symbols, tiêu đề, câu hỏi)
    ("pie_chart", "Mức tập trung", "Có đang dồn quá nhiều tiền vào một mã hay một ngành không?"),
    ("water_drop", "Thanh khoản", "Cần tiền gấp thì mất mấy ngày mới bán hết danh mục?"),
    ("monitoring", "Rủi ro thị trường", "Danh mục lên xuống mạnh đến đâu so với VN-Index?"),
    ("trending_down", "Kịch bản xấu", "Nếu cả thị trường giảm sàn, bạn mất bao nhiêu tiền?"),
]
STEPS = [
    ("Nhập danh mục", "Gõ mã, số lượng, giá vốn và tiền mặt, hoặc tải file CSV."),
    ("Xem kết luận", "Trang Tổng quan cho biết danh mục Khỏe, Cần theo dõi hay Cần xem lại."),
    ("Đọc giải thích", "Mỗi cảnh báo có con số, ý nghĩa, ngưỡng có nguồn và gợi ý nên làm gì."),
]


def home(ctx: AppContext) -> None:
    with st.container(key="hero"):
        left, right = st.columns([1.15, 1], vertical_alignment="center", gap="large")
        with left:
            st.html(
                f'<div class="hero-kicker">{config.APP_NAME}</div>'
                '<div class="hero-title">Danh mục của bạn<br>có đang <span class="glow">khỏe</span>?</div>'
                f'<div class="hero-sub">{config.APP_GOAL}.</div>'
                '<div class="chips"><span class="chip">Dữ liệu thật từ <b>SSI FastConnect</b></span>'
                '<span class="chip">Ngưỡng có nguồn học thuật</span>'
                '<span class="chip">Không đặt lệnh, không đọc tài khoản</span></div>'
            )
            b1, b2 = st.columns(2)
            if b1.button("Xem kết quả kiểm tra", type="primary", icon=ICONS["overview"], width="stretch"):
                st.switch_page(ctx.pages["overview"])
            if b2.button("Nhập danh mục của bạn", icon=ICONS["portfolio"], width="stretch"):
                st.switch_page(ctx.pages["portfolio"])
        with right:
            st.image(HERO_ART, width="stretch")

    st.html('<div class="section-title">Ứng dụng kiểm tra <span class="glow">4 điều</span> cho danh mục của bạn</div>')
    for number, (column, (icon, title, text)) in enumerate(zip(st.columns(4), FEATURES)):
        with column.container(key=card_key("feature" + title), height="stretch"):
            st.html(f'<div class="feature-icon{" gold" if number % 2 else ""}"><span class="ms">{icon}</span></div>')
            st.markdown(f"**{title}**")
            st.caption(text)

    st.html('<div class="section-title">Dùng trong <span class="glow">3 bước</span></div>')
    for number, (column, (title, text)) in enumerate(zip(st.columns(3), STEPS), 1):
        with column.container(key=card_key("step" + title), height="stretch"):
            st.html(f'<span class="step-no">{number}</span><b>{title}</b>')
            st.caption(text)

    st.html('<div class="section-title">Về sản phẩm</div>')
    who, data = st.columns(2)
    with who.container(key=card_key("who"), height="stretch"):
        st.markdown(f"**:violet[:material/group:] Dành cho ai?**  \n{config.APP_USERS}.")
    with data.container(key=card_key("data"), height="stretch"):
        session = format_date(ctx.market.last_trading_date) if ctx.market else "chưa có"
        source = "kho dữ liệu trên máy" if ctx.live else "bản dữ liệu SSI lưu kèm mã nguồn"
        st.markdown(f"**:violet[:material/database:] Dữ liệu từ đâu?**  \nSSI FastConnect API, dữ liệu theo phiên. "
                    f"Đang dùng {source}, phiên mới nhất **{session}**.")
    st.caption(f":material/gavel: {DISCLAIMER}")


# ====================================================================== Tổng quan

def overview(ctx: AppContext) -> None:
    page_header("Tổng quan", "Kết luận sức khỏe danh mục và 6 chỉ số chính. Bấm vào từng mục ở menu bên trái "
                             "để xem chi tiết.")
    st.caption(f":material/gavel: {DISCLAIMER} Ứng dụng chỉ đọc dữ liệu thị trường từ SSI FastConnect API, "
               "không đặt lệnh và không đọc tài khoản chứng khoán của bạn.")
    if not ctx.live and ctx.market is not None:
        st.info(f"Máy này chưa có kho dữ liệu riêng nên ứng dụng dùng **bản dữ liệu SSI lưu kèm mã nguồn**, chốt "
                f"đến phiên **{format_date(ctx.market.last_trading_date)}**. "
                + ("Bấm **Cập nhật dữ liệu** ở thanh bên để tải dữ liệu mới nhất từ SSI."
                   if ctx.has_key else "Muốn lấy phiên mới: thêm API key SSI vào file .env rồi bấm **Cập nhật dữ liệu**."),
                icon=":material/info:")
    if not require_report(ctx):
        return
    show_missing_symbols(ctx)
    report, m, totals = ctx.report, ctx.report.metrics, ctx.report.totals

    # ----- Kết luận
    level, label, sentence = overall_verdict(report.checks)
    counts = count_by_status(report.checks)
    color, icon = STATUS_BADGE[level]
    level_code = {DANGER: "danger", WARNING: "warning", GOOD: "good"}[level]
    with st.container(key=f"verdict-{level_code}"):
        head, detail = st.columns([1, 2], vertical_alignment="center")
        with head:
            st.caption(f"Kết luận sức khỏe danh mục · phiên {format_date(ctx.market.last_trading_date)}")
            st.markdown(f"## :{color}[{icon} {label}]")
            st.markdown(sentence)
        with detail:
            st.markdown(" &nbsp; ".join(badge(s, f"{counts[s]} {s.lower()}") for s in (DANGER, WARNING, GOOD, INFO)))
            issues = [c for c in report.checks if c.status == DANGER] + [c for c in report.checks if c.status == WARNING]
            if issues:
                st.markdown("**Điểm cần chú ý nhất**")
                for check in issues[:3]:
                    issue_color, issue_icon = STATUS_BADGE[check.status]
                    st.markdown(f":{issue_color}[{issue_icon}] **{check.name}:** {check.value}. {check.action}")
            else:
                st.markdown("Không có mục nào vượt ngưỡng.")
            st.page_link(ctx.pages["alerts"], label="Xem toàn bộ cảnh báo và giải thích", icon=ICONS["alerts"])

    # ----- Sáu ô chỉ số
    top = find_check(report, "Tỷ trọng mã lớn nhất")
    diversity = find_check(report, "Mức đa dạng hóa")
    row1 = st.columns(3)
    row2 = st.columns(3)
    kpi_card(row1[0], "Tổng tài sản", vnd(totals["total_value"]),
             f"Cổ phiếu theo giá đóng cửa phiên {format_date(ctx.market.last_trading_date)} cộng tiền mặt.",
             delta=f"{vnd(totals['pnl'])} lãi/lỗ chưa thực hiện")
    kpi_card(row1[1], "Mã chiếm tỷ trọng lớn nhất", top.value if top else "—",
             "Chuẩn tham chiếu: mỗi mã không quá 10% tổng tài sản.", top.status if top else None)
    kpi_card(row1[2], "Mức đa dạng hóa (Số mã hiệu dụng)", diversity.value if diversity else "—",
             "Rủi ro tương đương số mã có tỷ trọng bằng nhau. Tốt: từ 10 mã.", diversity.status if diversity else None)
    kpi_card(row2[0], "Lỗ trong một phiên xấu (VaR 95%)", vnd(m["var_amount"]),
             f"95/100 phiên không lỗ quá mức này ({pct(m['var_pct'])}). Tính trên 250 phiên gần nhất.", INFO)
    kpi_card(row2[1], "Độ nhạy với thị trường (Beta)", num(m["beta"]),
             f"VN-Index giảm 1% thì danh mục thường giảm khoảng {num(m['beta'])}%. Tính trên 250 phiên.", INFO)
    share = m["floor_loss_1"] / totals["total_value"] if totals["total_value"] else float("nan")
    kpi_card(row2[2], "Lỗ nếu mọi mã giảm sàn 1 phiên", vnd(m["floor_loss_1"]),
             f"Bằng {pct(share)} tổng tài sản. Kịch bản cực đoan, không phải dự báo.", INFO)

    # ----- Đi tiếp
    st.markdown("**Xem chi tiết**")
    links = st.columns(4)
    for column, key, text in zip(links, ["allocation", "risk", "liquidity", "market"],
                                 ["Phân bổ theo mã và ngành", "Biến động và sụt giảm", "Bán gấp và giảm sàn",
                                  "Bối cảnh thị trường"]):
        with column.container(key=card_key("link" + key)):
            st.page_link(ctx.pages[key], label=text, icon=ICONS[key])


# ====================================================================== Nhập danh mục

def portfolio_input(ctx: AppContext) -> None:
    page_header("Nhập danh mục", "Nhập các mã bạn đang nắm, số lượng, giá vốn và tiền mặt, rồi bấm Lưu danh mục. "
                                 "Mọi trang phân tích sẽ tính lại theo danh mục này.")
    state = st.session_state
    with st.form("portfolio_form", border=True):
        edited = st.data_editor(
            state.portfolio_rows, key=f"editor_{state.editor_version}", num_rows="dynamic", hide_index=True,
            width="stretch",
            column_config={
                "symbol": st.column_config.TextColumn("Mã cổ phiếu", required=True, max_chars=10,
                                                      help="Ví dụ: FPT, VCB. Mã niêm yết trên HOSE, HNX hoặc UPCoM."),
                "quantity": st.column_config.NumberColumn("Số lượng (cổ phiếu)", min_value=0, step=100, format="%d"),
                "avg_cost": st.column_config.NumberColumn("Giá vốn bình quân (đ/cổ phiếu)", min_value=0, step=50,
                                                          format="%d", help="Để trống nếu không nhớ; khi đó không "
                                                                            "tính được lãi/lỗ của mã đó."),
            },
        )
        cash = st.number_input("Tiền mặt trong tài khoản (đ)", min_value=0.0, value=float(state.cash),
                               step=1_000_000.0, format="%.0f")
        submitted = st.form_submit_button("Lưu danh mục", type="primary", icon=ICONS["save"])
    if submitted:
        ctx.save_portfolio(edited, cash)

    if ctx.portfolio_error:
        st.error(f"Danh mục chưa hợp lệ: {ctx.portfolio_error}")
    elif ctx.portfolio is not None:
        st.success(f"Đang phân tích **{len(ctx.portfolio.symbols)} mã** ({', '.join(ctx.portfolio.symbols)}) và "
                   f"**{vnd(ctx.portfolio.cash)}** tiền mặt.", icon=":material/check_circle:")
        show_missing_symbols(ctx)
        st.page_link(ctx.pages["overview"], label="Xem kết luận ở trang Tổng quan", icon=ICONS["overview"])

    with st.expander("Tùy chọn khác: tải file CSV, đặt lại danh mục", icon=":material/tune:"):
        st.markdown("**Tải danh mục từ file CSV**")
        st.caption("File gồm 3 cột: `symbol` (mã), `quantity` (số lượng), `avg_cost` (giá vốn). "
                   "Thêm một dòng `CASH` với `quantity` là số tiền mặt nếu muốn.")
        uploaded = st.file_uploader("Chọn file CSV", type="csv", label_visibility="collapsed")
        if uploaded is not None and state.get("uploaded_name") != uploaded.name:
            try:
                frame = pd.read_csv(uploaded, dtype={"symbol": str})
                is_cash = frame["symbol"].str.upper().str.strip() == "CASH"
                ctx.save_portfolio(frame.loc[~is_cash, ["symbol", "quantity", "avg_cost"]],
                                   float(frame.loc[is_cash, "quantity"].sum()))
                state.uploaded_name = uploaded.name
            except (KeyError, ValueError) as exc:
                st.error(f"Không đọc được file: {exc}")
        st.divider()
        st.markdown("**Đặt lại danh mục mặc định**")
        st.caption("Danh mục mặc định: 500.000.000 đ chia cho FPT, VCB, MBB, HPG, SSI, MWG và tiền mặt.")
        if st.button("Đặt lại", icon=ICONS["reset"]):
            ctx.reset_portfolio()


# ====================================================================== Cảnh báo

def alerts(ctx: AppContext) -> None:
    page_header("Cảnh báo và giải thích", "Từng tiêu chí được so với một ngưỡng có nguồn gốc rõ ràng. "
                                          "Mỗi mục cho biết con số, ý nghĩa và nên làm gì.")
    if not require_report(ctx):
        return
    checks = ctx.report.checks
    counts = count_by_status(checks)
    levels = [s for s in (DANGER, WARNING, GOOD, INFO) if counts[s]]
    chosen = st.pills("Lọc theo mức", levels, selection_mode="multi", default=levels,
                      format_func=lambda s: f"{s} ({counts[s]})")
    st.caption("Rủi ro cao và Cảnh báo: vượt ngưỡng tham chiếu. Tốt: đạt ngưỡng. Thông tin: thước đo mô tả, "
               "không có ngưỡng chuẩn để xếp loại. Chỉ có 3 mức đánh giá vì các nguồn tham chiếu chỉ đưa ra 1–2 mốc.")
    shown = [c for c in checks if c.status in (chosen or [])]
    if not shown:
        st.info("Chọn ít nhất một mức để xem.")
    for group in dict.fromkeys(c.group for c in shown):
        st.subheader(group)
        items = [c for c in shown if c.group == group]
        for start in range(0, len(items), 2):
            columns = st.columns(2)
            for column, check in zip(columns, items[start:start + 2]):
                with column.container(key=card_key("alert" + check.name), height="stretch"):
                    st.markdown(f"**{check.name}** &nbsp; {badge(check.status)}")
                    st.markdown(f"#### {check.value}")
                    st.markdown(check.explanation)
                    if check.action:
                        st.markdown(f"{ICONS['action']} **Nên làm gì?** {check.action}")
                    st.caption(f"Ngưỡng: {check.threshold or 'không có'} · Cơ sở: {check.source or '—'}")


# ====================================================================== Phân bổ

def allocation(ctx: AppContext) -> None:
    page_header("Phân bổ", "Tiền của bạn đang nằm ở mã nào, ngành nào, và lãi/lỗ của từng mã.")
    if not require_report(ctx):
        return
    report, totals = ctx.report, ctx.report.totals
    diversity = find_check(report, "Mức đa dạng hóa")
    n_eff = float(diversity.value.split()[0].replace(",", ".")) if diversity and diversity.status != INFO else float("nan")
    col1, col2 = st.columns([1, 2])
    with col1.container(key=card_key("gauge"), height="stretch"):
        if n_eff == n_eff:
            plot(charts.diversity_gauge(n_eff))
        how_to_read("kim chỉ số mã hiệu dụng. Vùng đỏ dưới 5 mã: tập trung cao; vùng vàng 5–10 mã; vùng xanh từ 10 mã: "
                    "đa dạng hóa tốt (Evans & Archer, 1968).")
    with col2.container(key=card_key("weights"), height="stretch"):
        plot(charts.weights_bar(report.valuation, totals["cash_weight"], totals["cash"]))
        how_to_read("mỗi thanh là phần trăm tổng tài sản; thanh có vân sọc là tiền mặt. Vạch chấm 10% là mức tối đa "
                    "cho một mã theo chuẩn UCITS; thanh vượt vạch là mã đang chiếm quá nhiều.")
    with st.container(key=card_key("sectors")):
        plot(charts.sector_bar(report.sectors))
        how_to_read("tỷ trọng từng ngành trên phần cổ phiếu (không tính tiền mặt). Vạch 50%: quá nửa danh mục "
                    "phụ thuộc một ngành.")

    st.subheader("Chi tiết từng mã")
    table = report.valuation.sort_values("market_value", ascending=False)
    st.dataframe(pd.DataFrame({
        "Mã": table["symbol"],
        "Số lượng": table["quantity"].map(lambda v: f"{v:,.0f}".replace(",", ".")),
        "Giá vốn": table["avg_cost"].map(vnd),
        "Giá gần nhất": table["price"].map(vnd),
        "Giá trị": table["market_value"].map(vnd),
        "Tỷ trọng": table["weight_total"].map(pct),
        "Lãi/lỗ": table["pnl"].map(vnd),
        "Lãi/lỗ (%)": table["pnl_pct"].map(pct),
    }), hide_index=True, width="stretch")
    st.caption(f"Giá gần nhất: giá đóng cửa phiên {format_date(ctx.market.last_trading_date)}. Giá vốn do bạn nhập. "
               "Lãi/lỗ chưa trừ thuế, phí.")


# ====================================================================== Rủi ro

def _remember(key: str, widget_key: str) -> None:
    """Giữ lựa chọn khi chuyển trang (Streamlit xóa giá trị của widget khi trang không còn hiển thị)."""
    value = st.session_state[widget_key]
    if value is not None:  # bấm lại nút đang chọn sẽ bỏ chọn (None): giữ lựa chọn cũ
        st.session_state[key] = value


def risk(ctx: AppContext) -> None:
    page_header("Rủi ro", "Danh mục lên xuống mạnh đến đâu so với thị trường, và lúc tệ nhất từng giảm bao nhiêu.")
    if not require_report(ctx):
        return
    report, m, market = ctx.report, ctx.report.metrics, ctx.market

    controls = st.columns([1, 2])
    period = controls[0].segmented_control(
        "Khoảng thời gian", list(PERIODS), default=st.session_state.period, key="period_widget",
        on_change=_remember, args=("period", "period_widget")) or st.session_state.period
    available = [s for s in ctx.portfolio.symbols if s in market.close.columns]
    compare = controls[1].multiselect("So sánh thêm với từng mã (tối đa 3)", available, max_selections=3,
                                      placeholder="Chọn mã để vẽ thêm")
    sessions = PERIODS[period]
    stock_returns = market.close.pct_change(fill_method=None)
    extra = {symbol: stock_returns[symbol] for symbol in compare}

    chart_card(charts.growth_chart(report.portfolio_returns, report.market_returns, extra, sessions),
               "đường cho biết 100 đồng bỏ vào từ đầu giai đoạn sẽ thành bao nhiêu. Đường danh mục nằm trên VN-Index "
                "là danh mục tăng tốt hơn thị trường trong giai đoạn đó. Giả định giữ nguyên tỷ trọng hiện tại suốt "
                "giai đoạn, nên đây là thước đo rủi ro của danh mục hôm nay, không phải lãi/lỗ bạn đã có. "
               f"Kéo thanh trượt bên dưới để chọn một đoạn thời gian. {HOW_TO_INTERACT}")

    r1, r2, r3 = st.columns(3)
    vol_check = find_check(report, "Độ biến động")
    r2_check = find_check(report, "Phần rủi ro")
    kpi_card(r1, "Độ biến động năm (Volatility)", pct(m["volatility"]),
             f"VN-Index: {pct(m['market_volatility'])}. Càng cao, giá trị danh mục lên xuống càng mạnh.",
             vol_check.status if vol_check else None)
    kpi_card(r2, "Rủi ro đến từ thị trường chung (R²)", pct(m["r_squared"], 0),
             f"Còn lại {pct(1 - m['r_squared'], 0)} là rủi ro riêng của từng mã, giảm được bằng đa dạng hóa.",
             r2_check.status if r2_check else None)
    kpi_card(r3, "Sụt giảm tối đa 1 năm (Max Drawdown)", pct(m["max_drawdown_1y"]),
             "Mức giảm sâu nhất so với đỉnh trước đó trong 250 phiên vừa qua.", INFO)
    st.caption("Ba chỉ số trên luôn tính trên 250 phiên gần nhất (khoảng 1 năm giao dịch) để so sánh được với "
               "nhau; nút chọn khoảng thời gian chỉ thay đổi các biểu đồ.")

    col1, col2 = st.columns(2)
    chart_card(charts.drawdown_chart(report.portfolio_returns, sessions),
               "0% là lúc danh mục đang ở đỉnh. Vùng càng sâu xuống dưới là lúc danh mục giảm càng nhiều so với đỉnh "
               "gần nhất; vùng kéo dài là thời gian chờ để hồi lại.", col1)
    chart_card(charts.returns_histogram(report.portfolio_returns, m["var_pct"]),
               "mỗi cột là số phiên có mức lãi/lỗ trong một khoảng. Đường đứt nét là VaR 95%: chỉ khoảng 5% số phiên "
               "nằm bên trái đường này. Biểu đồ này luôn dùng 250 phiên gần nhất, giống cách tính VaR.", col2)


# ====================================================================== Thanh khoản & giảm sàn

def liquidity(ctx: AppContext) -> None:
    page_header("Thanh khoản và kịch bản giảm sàn",
                "Nếu cần tiền gấp thì mất mấy ngày mới bán hết, và nếu thị trường giảm sàn thì lỗ bao nhiêu.")
    if not require_report(ctx):
        return
    report, m, totals = ctx.report, ctx.report.metrics, ctx.report.totals

    st.subheader("Bán hết danh mục mất bao lâu?")
    participation = st.slider(
        "Mỗi phiên bán tối đa bao nhiêu phần trăm khối lượng giao dịch bình quân 20 phiên (ADV20)?",
        min_value=5, max_value=50, value=st.session_state.participation_pct, step=5, format="%d%%",
        key="participation_widget", on_change=_remember, args=("participation_pct", "participation_widget"),
        help="Bán quá nhiều so với khối lượng thường ngày sẽ tự đẩy giá xuống. 20% là giả định mặc định.",
    ) / 100
    liq = report.liquidity.copy()
    price = liq["market_value"] / liq["quantity"]
    max_sell_value = participation * liq["adv"] * price
    st.dataframe(pd.DataFrame({
        "Mã": liq["symbol"],
        "Giá trị đang nắm": liq["market_value"].map(vnd),
        "KLGD bình quân 20 phiên (ADV20)": liq["adv"].map(lambda v: f"{v:,.0f} cp".replace(",", ".") if v == v else "—"),
        "Vị thế so với ADV20": liq["position_pct_adv"].map(lambda v: pct(v, 2)),
        "Bán được tối đa mỗi phiên": max_sell_value.map(vnd),
        "Có tiền sau": liq["days_to_cash"].map(lambda d: f"{d:.0f} ngày làm việc" if d == d and d != float("inf") else "—"),
        "Mức thanh khoản": liq["bucket"],
    }), hide_index=True, width="stretch")
    how_to_read("'Có tiền sau' = số phiên cần để bán hết + 2 ngày thanh toán (T+2). Có tiền trong 3 ngày làm việc là "
                "thanh khoản cao, trong 5 ngày là trung bình (theo SEC Rule 22e-4). 'Bán được tối đa mỗi phiên' cho "
                "biết danh mục còn có thể lớn đến đâu mà vẫn bán hết trong 1 phiên.")

    st.divider()
    st.subheader("Nếu mọi mã cùng giảm sàn")
    s1, s3 = st.columns(2)
    kpi_card(s1, "Giảm sàn 1 phiên", vnd(m["floor_loss_1"]),
             f"Bằng {pct(m['floor_loss_1'] / totals['total_value'])} tổng tài sản.", INFO)
    kpi_card(s3, "Giảm sàn 3 phiên liên tiếp", vnd(m["floor_loss_3"]),
             f"Bằng {pct(m['floor_loss_3'] / totals['total_value'])} tổng tài sản.", INFO)
    chart_card(charts.stress_bar(report.stress_1, report.stress_3),
               "mỗi cặp cột là số tiền lỗ của một mã; cột có vân sọc là kịch bản 3 phiên. Giá sàn = giá tham chiếu × "
               "(1 − biên độ), làm tròn theo bước giá; biên độ HOSE 7%, HNX 10%, UPCoM 15%. Giả định giá tham chiếu "
               "phiên sau bằng giá đóng cửa gần nhất. Đây là kịch bản cực đoan để hình dung rủi ro, không phải dự báo.")


# ====================================================================== Thị trường

def market(ctx: AppContext) -> None:
    page_header("Thị trường", "Bối cảnh chung: VN-Index, số mã tăng giảm và dòng tiền khối ngoại trên sàn HOSE.")
    if ctx.market is None or ctx.market.index_close.empty:
        st.error(ctx.data_error or "Chưa có dữ liệu VN-Index.")
        return
    index = ctx.market.index_close
    summary = ctx.store_info.get("market_summary", pd.DataFrame())

    cols = st.columns(4)
    if len(index) >= 2:
        change = index.iloc[-1] / index.iloc[-2] - 1
        cols[0].metric(f"VN-Index phiên {format_date(str(index.index[-1]))}", num(index.iloc[-1]),
                       delta=pct(change, 2), border=True, height="stretch",
                       chart_data=index.tail(20).round(2).tolist(), chart_type="area",
                       help="Biểu đồ nhỏ: 20 phiên gần nhất.")
    if not summary.empty:
        latest = summary.iloc[-1]
        cols[1].metric("Số mã tăng / giảm", f"{latest['advances']:.0f} / {latest['declines']:.0f}", border=True,
                       height="stretch", help=f"Phiên {format_date(latest['trading_date'])}, sàn HOSE.")
        cols[2].metric("Giá trị khớp lệnh", vnd_billion(latest["total_match_value"]), border=True, height="stretch",
                       chart_data=(summary["total_match_value"] / 1e9).round(0).tolist(), chart_type="bar",
                       help="Sàn HOSE. Biểu đồ nhỏ: các phiên đã lưu gần nhất.")
        cols[3].metric("Khối ngoại mua ròng", vnd_billion(latest["foreign_net_value"]), border=True, height="stretch",
                       chart_data=(summary["foreign_net_value"] / 1e9).round(0).tolist(), chart_type="bar",
                       help="Giá trị mua trừ giá trị bán của nhà đầu tư nước ngoài; số âm là bán ròng.")

    chart_card(charts.index_chart(index), "bấm các nút phía trên để xem nhanh 1 tháng đến toàn bộ lịch sử, hoặc "
               f"kéo thanh trượt bên dưới. {HOW_TO_INTERACT}")

    if len(summary) >= 2:
        col1, col2 = st.columns(2)
        chart_card(charts.foreign_flow_bar(summary),
                   "cột xanh là phiên khối ngoại mua nhiều hơn bán (mua ròng), cột đỏ là bán nhiều hơn mua (bán ròng).", col1)
        chart_card(charts.breadth_chart(summary),
                   "số mã tăng nhiều hơn số mã giảm cho thấy đà tăng lan rộng, không chỉ ở vài mã lớn.", col2)
    elif summary.empty:
        st.info("Chưa có số liệu tổng hợp thị trường. Dữ liệu này được lưu mỗi lần cập nhật từ SSI.")
    with st.expander("Bảng số liệu tổng hợp thị trường theo phiên", icon=":material/table:"):
        if summary.empty:
            st.caption("Chưa có dữ liệu.")
        else:
            data = summary.sort_values("trading_date", ascending=False)
            st.dataframe(pd.DataFrame({
                "Phiên": data["trading_date"].map(format_date),
                "VN-Index": data["index_value"].map(lambda v: num(v)),
                "Số mã tăng": data["advances"].map(lambda v: f"{v:.0f}"),
                "Số mã giảm": data["declines"].map(lambda v: f"{v:.0f}"),
                "Giá trị khớp lệnh": data["total_match_value"].map(vnd_billion),
                "Khối ngoại mua ròng": data["foreign_net_value"].map(vnd_billion),
            }), hide_index=True, width="stretch")


# ====================================================================== Phương pháp & dữ liệu

def method(ctx: AppContext) -> None:
    page_header("Phương pháp và dữ liệu", "Dữ liệu lấy từ đâu, các con số được tính thế nào, ngưỡng dựa trên "
                                          "nguồn nào và sản phẩm có những giới hạn gì.")
    st.subheader("Nguồn và cách cập nhật dữ liệu")
    st.markdown(
        "- **Nguồn:** SSI FastConnect API v3, dữ liệu theo phiên: giá đã điều chỉnh cho cổ tức và cổ phiếu thưởng, "
        "khối lượng, khối ngoại, room ngoại; VN-Index; danh sách mã kèm ngành ICB; tổng hợp thị trường sàn HOSE. "
        "Token không kèm OTP nên chỉ có quyền đọc dữ liệu, không đặt lệnh được.\n"
        "- **Cập nhật:** khi mở ứng dụng trên máy có API key, ứng dụng tự hỏi SSI phiên mới sau 15:00 mỗi ngày làm "
        "việc; có thể bấm **Cập nhật dữ liệu** bất cứ lúc nào. Mỗi lần chỉ tải phần mới, kèm 14 ngày gần nhất để "
        "phát hiện SSI điều chỉnh lại giá lịch sử.\n"
        "- **Máy không có API key** (ví dụ máy người chấm): ứng dụng dùng bản dữ liệu SSI lưu kèm mã nguồn "
        "(`data_sample/sample.db`) và ghi rõ phiên chốt dữ liệu."
    )
    st.subheader("Cách tính")
    st.markdown(
        "- **Lợi suất ngày** = giá đóng cửa đã điều chỉnh hôm nay / phiên trước − 1. Danh mục giữ **tỷ trọng hiện tại** "
        "cố định; tiền mặt có lợi suất 0.\n"
        "- **Số mã hiệu dụng (Effective N)** = 1 / Σ(tỷ trọng²), tức nghịch đảo chỉ số tập trung HHI.\n"
        "- **Độ biến động năm (Volatility)** = độ lệch chuẩn lợi suất ngày × √252, 250 phiên.\n"
        "- **Beta** = Cov(lợi suất danh mục, lợi suất VN-Index) / Var(lợi suất VN-Index), 250 phiên. "
        "**R²** = bình phương hệ số tương quan với VN-Index.\n"
        "- **Giá trị rủi ro (VaR) lịch sử 95%, 1 ngày** = phân vị 5% của 250 lợi suất ngày gần nhất.\n"
        "- **Sụt giảm tối đa (Max Drawdown)** = mức giảm lớn nhất từ một đỉnh xuống đáy sau đó, 250 phiên.\n"
        "- **Thanh khoản:** số phiên bán = ⌈số lượng / (tỷ lệ tham gia × ADV20)⌉; ngày có tiền = số phiên bán + 2 (T+2).\n"
        "- **Kịch bản giảm sàn:** áp biên độ sàn 1 và 3 phiên liên tiếp, làm tròn theo bước giá.\n"
        "- **Kết luận chung** lấy mức xấu nhất trong các tiêu chí: chỉ cần một mục Rủi ro cao là cần xem lại; "
        "không cộng điểm hay gán trọng số."
    )
    if ctx.report is not None:
        st.subheader("Ngưỡng cảnh báo và cơ sở")
        frame = ctx.report.checks_frame()
        st.table(pd.DataFrame({"Nhóm": frame["group"], "Tiêu chí": frame["name"],
                               "Ngưỡng": frame["threshold"].replace("", "không có"), "Cơ sở": frame["source"]}),
                 hide_index=True, border="horizontal")
    st.subheader("Giới hạn của sản phẩm")
    st.markdown(
        "- Dữ liệu theo **phiên** (cuối ngày), không phải thời gian thực.\n"
        "- Các chỉ số rủi ro dựa trên **quá khứ**; quá khứ không bảo đảm cho tương lai. VaR không cho biết mức lỗ "
        "trong 5% phiên xấu nhất.\n"
        "- Giả định tỷ trọng cố định và tỷ lệ tham gia thanh khoản là đơn giản hóa.\n"
        "- Ngưỡng UCITS và SEC là **chuẩn tham chiếu** của quỹ đầu tư, không bắt buộc với nhà đầu tư cá nhân; ngưỡng "
        "ngành 50% là quy tắc tự đặt.\n"
        "- Danh mục do người dùng tự nhập; ứng dụng không đọc tài khoản chứng khoán thật.\n"
        "- Không tính thuế, phí giao dịch, cổ tức tiền mặt và lãi tiền gửi.\n"
        f"- {DISCLAIMER}"
    )

    st.subheader("Chất lượng và truy vết dữ liệu")
    coverage = ctx.store_info.get("coverage", pd.DataFrame())
    log = ctx.store_info.get("fetch_log", pd.DataFrame())
    if coverage.empty:
        st.info("Chưa có dữ liệu trong kho.")
        return
    stock_log = log[log["dataset"] == "stock_daily"].drop_duplicates("symbol") if not log.empty else log
    missing = int(stock_log["missing_sessions"].fillna(0).sum()) if not stock_log.empty else 0
    st.markdown(f"Kho đang có **{(coverage['kind'] == 'stock').sum()} mã cổ phiếu** và VN-Index. "
                + ("Không mã nào thiếu phiên so với lịch giao dịch của VN-Index (kiểm tra ở lần tải gần nhất)."
                   if missing == 0 else f"Có **{missing} phiên thiếu** so với lịch giao dịch của VN-Index."))
    st.dataframe(pd.DataFrame({
        "Loại": coverage["kind"].map(KIND_LABELS),
        "Mã": coverage["symbol"],
        "Số phiên": coverage["sessions"],
        "Từ ngày": coverage["first"].map(format_date),
        "Đến ngày": coverage["last"].map(format_date),
    }), hide_index=True, width="stretch")
    if not log.empty:
        st.markdown("**Nhật ký tải dữ liệu từ SSI** (mỗi dòng là một lần tải một chuỗi dữ liệu, mới nhất ở trên)")
        st.dataframe(pd.DataFrame({
            "Thời điểm": log["started_at"].map(format_time),
            "Dữ liệu": log["dataset"].map(lambda d: DATASET_LABELS.get(d, d)),
            "Mã": log["symbol"],
            "Cách tải": log["mode"].map(lambda d: MODE_LABELS.get(d, d)),
            "Số phiên nhận": log["rows_kept"],
            "Kết quả": log["status"].map(lambda d: RESULT_LABELS.get(d, d)),
            "Ghi chú": log["message"].fillna(""),
        }), hide_index=True, width="stretch")
