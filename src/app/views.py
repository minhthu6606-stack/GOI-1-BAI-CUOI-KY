"""
Nội dung từng trang của ứng dụng. Mỗi hàm nhận AppContext (đã tính sẵn ở main.py) và vẽ một trang.

Thứ tự trang trên thanh điều hướng:
    (không nhóm):                Trang chủ
    1 · Hồ sơ danh mục:          Nhập danh mục
    2 · Xem kết quả:             Tổng quan · Cảnh báo · Phân bổ · Rủi ro · Thanh khoản & giảm sàn (có thanh tab)
    3 · Phương án cải thiện:     Thử điều chỉnh
    Tham khảo:                   Thị trường · Phương pháp & dữ liệu
Cuối mọi trang có nút Trước/Tiếp theo đúng thứ tự trên.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd
import streamlit as st

from src import config
from src.app import charts
from src.app.style import flow_html, hero_art
from src.app.ui import (
    DATASET_LABELS, ICONS, KIND_LABELS, MODE_LABELS, RESULT_LABELS, STATUS_BADGE, format_date, format_time,
)
from src.finance.health import (
    DANGER, DISCLAIMER, GOOD, INFO, WARNING, Check, HealthReport, RiskProfile, build_health_report, count_by_status,
    num, overall_verdict, pct, vnd, vnd_billion,
)
from src.finance.examples import EXAMPLE_TOTAL, EXAMPLES
from src.finance import whatif as whatif_calc
from src.finance.market_data import MarketData
from src.data.quality import sessions_collected
from src.finance.portfolio import Portfolio

PERIODS = {"1 tháng": 21, "3 tháng": 63, "6 tháng": 126, "1 năm": 250, "2 năm": 500, "3 năm": 750}
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
    dark: bool = False                                    # người dùng chọn giao diện tối ở mục Cài đặt
    save_portfolio: Callable[..., None] | None = None
    reset_portfolio: Callable[[], None] | None = None
    load_example: Callable[[str], None] | None = None
    active_example: str | None = None                     # khóa danh mục ví dụ đang dùng (None: tự nhập)
    latest_prices: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))  # giá mới nhất mọi mã trong kho
    symbol_names: dict[str, str] = field(default_factory=dict)                        # mã -> tên công ty
    profile: RiskProfile | None = None                    # mức chịu rủi ro tự khai (tùy chọn)
    participation: float = 0.2


# ====================================================================== điều hướng giữa các trang

PAGE_ORDER = [  # thứ tự đi một vòng, giống thứ tự trong menu bên
    ("home", "Trang chủ"), ("portfolio", "Nhập danh mục"), ("overview", "Tổng quan"), ("alerts", "Cảnh báo"),
    ("allocation", "Phân bổ"), ("risk", "Rủi ro"), ("liquidity", "Thanh khoản & giảm sàn"),
    ("whatif", "Thử điều chỉnh"), ("market", "Thị trường"), ("method", "Phương pháp & dữ liệu"),
]
RESULT_TABS = ["overview", "alerts", "allocation", "risk", "liquidity"]   # 5 trang của bước 2 · Xem kết quả
TAB_LABELS = {"overview": "Tổng quan", "alerts": "Cảnh báo", "allocation": "Phân bổ", "risk": "Rủi ro",
              "liquidity": "Thanh khoản"}


def _icon_name(key: str) -> str:
    """':material/space_dashboard:' -> 'space_dashboard' (để vẽ biểu tượng trong HTML)."""
    return ICONS[key].removeprefix(":material/").rstrip(":")


def result_tabs(ctx: AppContext, current: str) -> None:
    """Thanh tab dưới tiêu đề của 5 trang kết quả: bấm để chuyển nhanh, tab đang xem được tô màu."""
    with st.container(key="result-tabs"):
        for column, key in zip(st.columns(len(RESULT_TABS)), RESULT_TABS):
            if key == current:
                column.html(f'<div class="tab-active"><span class="ms">{_icon_name(key)}</span>{TAB_LABELS[key]}</div>')
            else:
                column.page_link(ctx.pages[key], label=TAB_LABELS[key], icon=ICONS[key])


def page_footer(ctx: AppContext, current: str) -> None:
    """Cuối mỗi trang: nút về trang trước và sang trang tiếp theo, theo thứ tự PAGE_ORDER."""
    keys = [k for k, _ in PAGE_ORDER]
    if current not in keys or not ctx.pages:
        return
    i, titles = keys.index(current), dict(PAGE_ORDER)
    with st.container(key="page-footer"):
        left, right = st.columns(2, vertical_alignment="center")
        if i > 0:
            left.page_link(ctx.pages[keys[i - 1]], label=f"Trước: {titles[keys[i - 1]]}",
                           icon=":material/arrow_back:")
        if i < len(keys) - 1:
            with right.container(key="page-footer-next"):
                st.page_link(ctx.pages[keys[i + 1]], label=f"Tiếp: {titles[keys[i + 1]]}",
                             icon=":material/arrow_forward:")


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
    if st.session_state.get("dark_mode"):
        fig = charts.apply_dark(fig)
    st.plotly_chart(fig, width="stretch", config=charts.PLOTLY_CONFIG)


def chart_card(fig, note: str, column=None, tone: str = "p") -> None:
    """Biểu đồ đặt trong một thẻ, kèm dòng "Cách đọc" ngay bên dưới."""
    target = column if column is not None else st
    with target.container(key=card_key(note[:60], tone), height="stretch"):
        plot(fig)
        how_to_read(note)


def find_check(report: HealthReport, name_start: str) -> Check | None:
    return next((c for c in report.checks if c.name.startswith(name_start)), None)


STATUS_TONE = {DANGER: "r", WARNING: "o", GOOD: "k", INFO: "v"}


def card_key(text: str, tone: str = "v") -> str:
    """Khóa của thẻ: "card" + tông màu nền (p tím, g vàng, r đỏ, o cam, k xanh lá, v tím nhạt) + mã băm."""
    return f"card{tone}_" + hashlib.md5(text.encode("utf-8")).hexdigest()[:10]


def kpi_card(column, label: str, value: str, note: str, status: str | None = None, delta: str | None = None,
             tone: str = "p", **metric_args) -> None:
    """Một ô chỉ số: tên, con số, nhãn mức và một dòng giải thích. Các ô cùng hàng cao bằng nhau."""
    with column.container(key=card_key(label, tone), height="stretch"):
        st.markdown(f"**{label}**")
        st.metric(label, value, delta=delta, label_visibility="collapsed", **metric_args)
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
STEPS = [  # (tên bước, mô tả, trang mở ra) - quy trình 3 bước, dùng chung cho trang chủ và nhóm menu
    ("Hồ sơ danh mục", "Chọn một danh mục ví dụ hoặc nhập các mã bạn đang nắm. Có thể khai thêm mức lỗ bạn chịu "
                       "được (không bắt buộc).", "portfolio"),
    ("Xem kết quả", "Kết luận Khỏe, Cần theo dõi hay Cần xem lại, kèm giải thích từng chỉ số: con số, ngưỡng và "
                    "nguồn của ngưỡng.", "overview"),
    ("Phương án cải thiện", "Xem gợi ý \"Nên làm gì?\" và thử đổi tỷ trọng để thấy kết luận thay đổi ra sao "
                            "trước khi tự quyết định.", "whatif"),
]
FAQ = [
    ("Dữ liệu có phải theo thời gian thực không?",
     "Không. Ứng dụng dùng dữ liệu theo phiên (giá đóng cửa) từ SSI FastConnect API, tự cập nhật sau 15:00 mỗi "
     "ngày làm việc khi máy có API key. Thanh bên luôn ghi rõ phiên mới nhất và thời điểm tải."),
    ("Ứng dụng có đọc tài khoản chứng khoán của tôi không?",
     "Không. Ứng dụng chỉ đọc dữ liệu thị trường, không đặt lệnh và không đọc tài khoản. Danh mục do bạn tự nhập "
     "hoặc chọn từ danh mục ví dụ (giá thật, số lượng giả định), và chỉ nằm trong phiên làm việc trên máy của bạn."),
    ("Ứng dụng có khuyên tôi mua hay bán mã nào không?",
     "Không. Các gợi ý \"Nên làm gì?\" chỉ là nguyên tắc quản trị rủi ro chung, còn trang Thử điều chỉnh là mô "
     "phỏng do bạn tự chọn tỷ trọng. Đây là công cụ phân tích học thuật, không phải khuyến nghị đầu tư."),
    ("\"Cần xem lại\" nghĩa là danh mục đang lỗ?",
     "Không hẳn. Kết luận nói về mức rủi ro, không nói về lãi/lỗ: chỉ cần một tiêu chí vượt ngưỡng nghiêm trọng "
     "(ví dụ quá tập trung vào vài mã) là cần xem lại cách phân bổ."),
    ("Các ngưỡng cảnh báo lấy từ đâu?",
     "Từ chuẩn tham chiếu của quỹ đầu tư (UCITS của châu Âu, SEC Rule 22e-4 của Mỹ), nghiên cứu học thuật "
     "(Evans & Archer, 1968; Sharpe, 1963–1964; Jorion, 2007) và quy định biên độ giá của HOSE, HNX. Trang "
     "Phương pháp & dữ liệu liệt kê đầy đủ."),
    ("Danh mục ví dụ là gì? Có phải dữ liệu giả không?",
     "Giá trong danh mục ví dụ là giá đóng cửa thật từ SSI. Chỉ có số lượng cổ phiếu là giả định (mỗi danh mục "
     "khoảng 100 triệu đồng) để bạn xem thử ngay. Muốn khám danh mục của mình, chọn \"Danh mục của tôi\" ở trang "
     "Nhập danh mục."),
    ("Vì sao chỉ cần nhập số lượng, không cần giá vốn?",
     "Rủi ro của danh mục phụ thuộc vào giá trị hiện tại của từng mã (số lượng × giá đóng cửa mới nhất), không phụ "
     "thuộc giá bạn đã mua. Giá vốn chỉ dùng để tính lãi/lỗ, nên là tùy chọn."),
    ("\"Mức lỗ trong một phiên xấu (VaR 95%)\" nghĩa là gì?",
     "Nhìn lại 250 phiên gần nhất: trong khoảng 95 trên 100 phiên, danh mục không lỗ quá con số này. 5 phiên còn "
     "lại có thể lỗ nhiều hơn, nên đây không phải mức lỗ tối đa."),
    ("Tôi có 4 mã, sao \"số mã hiệu dụng\" chỉ khoảng 3?",
     "Số mã hiệu dụng cho biết danh mục của bạn đa dạng tương đương bao nhiêu mã có tỷ trọng bằng nhau. Nếu 4 mã "
     "nhưng một mã chiếm phần lớn tiền thì mức đa dạng thực tế thấp hơn 4. Chia đều 4 mã thì được đúng 4."),
    ("Mở ứng dụng lúc 10 giờ sáng thì dữ liệu là của phiên nào?",
     "Của phiên gần nhất đã đóng cửa (thường là hôm trước). Dữ liệu của phiên hôm nay được tải sau 15:00, khi giá "
     "đóng cửa đã chốt. Khung Dữ liệu ở thanh bên luôn ghi rõ đang dùng phiên nào."),
]


def home(ctx: AppContext) -> None:
    with st.container(key="hero"):
        left, right = st.columns([1, 1.12], vertical_alignment="center", gap="medium")
        with left:
            st.html(
                f'<div class="hero-kicker">{config.APP_NAME} · {config.APP_DESCRIPTOR}</div>'
                '<div class="hero-title">Danh mục<br>của bạn<br>có đang <span class="glow">khỏe</span>?</div>'
                f'<div class="hero-slogan">“{config.APP_TAGLINE}”</div>'
                f'<div class="hero-sub">{config.APP_PITCH}.</div>'
                '<div class="chips"><span class="chip">Dữ liệu thật từ <b>SSI FastConnect</b></span>'
                '<span class="chip">Ngưỡng có nguồn học thuật</span>'
                '<span class="chip">Không đặt lệnh, không đọc tài khoản</span></div>'
            )
            b1, b2 = st.columns([1, 1.15], vertical_alignment="center")
            if b1.button("Bắt đầu khám", type="primary", icon=":material/arrow_forward:", width="stretch"):
                st.switch_page(ctx.pages["portfolio"])
            b2.page_link(ctx.pages["overview"], label="Xem thử với danh mục ví dụ", icon=":material/visibility:")
        with right:
            st.image(hero_art(ctx.dark), width="stretch")

    st.html('<div class="section-title">Ứng dụng kiểm tra <span class="glow">4 điều</span> cho danh mục của bạn</div>')
    for number, (column, (icon, title, text)) in enumerate(zip(st.columns(4), FEATURES)):
        with column.container(key=card_key("feature" + title, "g" if number % 2 else "p"), height="stretch"):
            st.html(f'<div class="feature-icon{" gold" if number % 2 else ""}"><span class="ms">{icon}</span></div>')
            st.markdown(f"**{title}**")
            st.caption(text)

    st.html('<div class="section-title">Quy trình <span class="glow">3 bước</span></div>')
    columns = st.columns([1, 0.13, 1, 0.13, 1], vertical_alignment="center")
    for number, (title, text, page) in enumerate(STEPS, 1):
        with columns[(number - 1) * 2].container(key=card_key("step" + title, "g"), height="stretch"):
            st.html(f'<span class="step-no">{number}</span><b>{title}</b>')
            st.caption(text)
            st.page_link(ctx.pages[page], label="Mở", icon=":material/arrow_forward:")
        if number < len(STEPS):
            columns[number * 2 - 1].html('<div class="step-arrow"><span class="ms">arrow_forward</span></div>')

    st.html('<div class="section-title">Về sản phẩm</div>')
    who, data = st.columns(2)
    with who.container(key=card_key("who", "p"), height="stretch"):
        st.markdown(f"**:violet[:material/group:] Dành cho ai?**  \n{config.APP_USERS}.")
    with data.container(key=card_key("data", "g"), height="stretch"):
        session = format_date(ctx.market.last_trading_date) if ctx.market else "chưa có"
        source = "kho dữ liệu trên máy" if ctx.live else "bản dữ liệu SSI lưu kèm mã nguồn"
        st.markdown(f"**:violet[:material/database:] Dữ liệu từ đâu?**  \nSSI FastConnect API, dữ liệu theo phiên. "
                    f"Đang dùng {source}, phiên mới nhất **{session}**.")
    st.html('<div class="section-title">Câu hỏi thường gặp</div>')
    for question, answer in FAQ:
        with st.expander(question, icon=":material/help:"):
            st.markdown(answer)
    st.caption(f":material/gavel: {DISCLAIMER}")


# ====================================================================== Tổng quan

def overview(ctx: AppContext) -> None:
    page_header("Tổng quan", "Kết luận sức khỏe danh mục và 6 chỉ số chính. Bấm vào từng mục ở menu bên trái "
                             "để xem chi tiết.")
    result_tabs(ctx, "overview")
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
    example_banner(ctx)
    show_missing_symbols(ctx)
    report, m, totals = ctx.report, ctx.report.metrics, ctx.report.totals

    # ----- Kết luận
    level, label, sentence = overall_verdict(report.checks)
    counts = count_by_status(report.checks)
    color, icon = STATUS_BADGE[level]
    level_code = {DANGER: "danger", WARNING: "warning", GOOD: "good"}[level]
    with st.container(key=f"verdict-{level_code}"):
        head, detail = st.columns([1, 1.6], vertical_alignment="center", gap="large")
        with head:
            pill = {DANGER: "Có mục rủi ro cao", WARNING: "Có mục cần theo dõi", GOOD: "Đạt các ngưỡng"}[level]
            pill_icon = {DANGER: "priority_high", WARNING: "visibility", GOOD: "check"}[level]
            st.html(
                f'<div class="verdict-kicker">Kết luận sức khỏe danh mục · phiên '
                f'{format_date(ctx.market.last_trading_date)}</div>'
                f'<div class="verdict-label">{label}</div>'
                f'<span class="verdict-pill pill-{level_code}"><span class="ms" style="font-size:18px">{pill_icon}'
                f'</span>{pill}</span><div class="verdict-text">{sentence}</div>'
            )
        with detail:
            st.markdown(" &nbsp; ".join(badge(s_, f"{counts[s_]} {s_.lower()}") for s_ in (DANGER, WARNING, GOOD, INFO)))
            issues = [c for c in report.checks if c.status == DANGER] + [c for c in report.checks if c.status == WARNING]
            if issues:
                st.markdown("**Điểm cần chú ý nhất**")
                for check in issues[:3]:
                    st.markdown(f"{ICONS['action']} **{check.name}:** {check.value}. {check.action}")
            else:
                st.markdown("Không có mục nào vượt ngưỡng.")
            st.page_link(ctx.pages["alerts"], label="Xem toàn bộ cảnh báo và giải thích", icon=ICONS["alerts"])
            st.page_link(ctx.pages["whatif"], label="Thử điều chỉnh tỷ trọng và xem kết quả thay đổi",
                         icon=ICONS["whatif"])

    # ----- Sáu ô chỉ số
    top = find_check(report, "Tỷ trọng mã lớn nhất")
    diversity = find_check(report, "Mức đa dạng hóa")
    row1 = st.columns(3)
    row2 = st.columns(3)
    has_cost = report.valuation["avg_cost"].notna().any() and ctx.active_example not in EXAMPLES
    kpi_card(row1[0], "Tổng tài sản", vnd(totals["total_value"]),
             f"Cổ phiếu theo giá đóng cửa phiên {format_date(ctx.market.last_trading_date)} cộng tiền mặt."
             + ("" if has_cost else " Chưa nhập giá vốn nên chưa tính lãi/lỗ."),
             delta=f"{vnd(totals['pnl'])} lãi/lỗ chưa thực hiện" if has_cost else None, tone="g")
    kpi_card(row1[1], "Mã chiếm tỷ trọng lớn nhất", top.value if top else "—",
             "Chuẩn tham chiếu: mỗi mã không quá 10% tổng tài sản.", top.status if top else None)
    kpi_card(row1[2], "Mức đa dạng hóa (Số mã hiệu dụng)", diversity.value if diversity else "—",
             "Rủi ro tương đương số mã có tỷ trọng bằng nhau. Tốt: từ 10 mã.", diversity.status if diversity else None,
             tone="g")
    kpi_card(row2[0], "Lỗ trong một phiên xấu (VaR 95%)", vnd(m["var_amount"]),
             f"95/100 phiên không lỗ quá mức này ({pct(m['var_pct'])}). Tính trên 250 phiên gần nhất.", INFO, tone="g")
    kpi_card(row2[1], "Độ nhạy với thị trường (Beta)", num(m["beta"]),
             f"VN-Index giảm 1% thì danh mục thường giảm khoảng {num(m['beta'])}%. Tính trên 250 phiên.", INFO)
    share = m["floor_loss_1"] / totals["total_value"] if totals["total_value"] else float("nan")
    kpi_card(row2[2], "Lỗ nếu mọi mã giảm sàn 1 phiên", vnd(m["floor_loss_1"]),
             f"Bằng {pct(share)} tổng tài sản. Kịch bản cực đoan, không phải dự báo.", INFO)


# ====================================================================== Nhập danh mục (bước 1)

def _saved_signature() -> tuple:
    """Dấu nhận dạng danh mục đã lưu, để biết bản đang sửa có thay đổi chưa lưu không."""
    state = st.session_state
    rows = tuple((r.symbol, float(r.quantity), None if pd.isna(r.avg_cost) else float(r.avg_cost))
                 for r in state.portfolio_rows.itertuples(index=False))
    return rows, float(state.cash)


def _draft_signature() -> tuple:
    state = st.session_state
    rows = tuple((r["symbol"], float(r["quantity"] or 0), r["avg_cost"]) for r in state.draft if r["symbol"])
    return rows, float(state.draft_cash or 0)


def _new_row(symbol: str = "", quantity: float = 100, avg_cost: float | None = None) -> dict:
    state = st.session_state
    state.row_counter = state.get("row_counter", 0) + 1
    return {"id": state.row_counter, "symbol": symbol, "quantity": quantity, "avg_cost": avg_cost}


def _load_draft_from_saved() -> None:
    """Bản đang sửa = danh mục đã lưu (chạy khi mở trang lần đầu hoặc sau mỗi lần lưu)."""
    state = st.session_state
    state.draft = [_new_row(r.symbol, float(r.quantity), None if pd.isna(r.avg_cost) else float(r.avg_cost))
                   for r in state.portfolio_rows.itertuples(index=False)]
    state.draft_cash = float(state.cash)
    state.draft_version = state.editor_version
    state.cash_nonce = state.get("cash_nonce", 0) + 1   # tạo lại ô tiền mặt với giá trị mới


def _add_row() -> None:
    st.session_state.draft.append(_new_row())


def _delete_row(row_id: int) -> None:
    st.session_state.draft = [r for r in st.session_state.draft if r["id"] != row_id]


def _clear_draft() -> None:
    st.session_state.draft = [_new_row()]
    st.session_state.draft_cash = 0.0
    st.session_state.draft_version = st.session_state.editor_version   # không bị nạp đè bằng danh mục đã lưu
    st.session_state.cash_nonce = st.session_state.get("cash_nonce", 0) + 1   # tạo lại ô tiền mặt


def _sync_cell(row_id: int, field_name: str, widget_key: str) -> None:
    """Ghi giá trị ô vừa sửa vào bản đang sửa (giữ được khi chuyển trang)."""
    for row in st.session_state.draft:
        if row["id"] == row_id:
            row[field_name] = st.session_state[widget_key]


def step_head(number: int | str, title: str, optional: bool = False) -> None:
    st.html(f'<div class="step-head"><span class="num">{number}</span>{title}'
            + ('<span class="opt">· không bắt buộc</span>' if optional else "") + "</div>")


def _switch_to_own() -> None:
    """Chuyển sang "Danh mục của tôi": bắt đầu từ bảng trống (danh mục đã lưu vẫn giữ đến khi bấm Xem kết quả)."""
    st.session_state.decl_mode = "own"
    if st.session_state.active_example:
        _clear_draft()


def example_banner(ctx: AppContext, show_button: bool = True) -> None:
    """Khung nổi bật nhắc người xem rằng đây là danh mục ví dụ (giá thật, số lượng giả định)."""
    if ctx.active_example not in EXAMPLES:
        return
    example = EXAMPLES[ctx.active_example]
    session = format_date(ctx.market.last_trading_date) if ctx.market else "mới nhất"
    with st.container(key="example-banner"):
        text, action = st.columns([3, 1.2], vertical_alignment="center")
        text.html(
            f'<div class="example-title"><span class="tag">DANH MỤC VÍ DỤ</span>{example.title}</div>'
            f'<div class="example-line">Giá: <b>giá đóng cửa thật từ SSI, phiên {session}</b>. Số lượng: <b>giả định</b> '
            f'(khoảng {vnd(EXAMPLE_TOTAL)}), không phải tài khoản thật của ai.</div>')
        if show_button:
            if action.button("Nhập danh mục của tôi", icon=":material/arrow_forward:", width="stretch",
                             key="banner_own"):
                _switch_to_own()
                st.switch_page(ctx.pages["portfolio"])


def _example_table(ctx: AppContext) -> None:
    """Bảng chỉ xem của danh mục ví dụ đang dùng."""
    state, prices, names = st.session_state, ctx.latest_prices, ctx.symbol_names
    rows = state.portfolio_rows
    values = rows["quantity"] * rows["symbol"].map(prices)
    total = float(values.sum()) + float(state.cash)
    with st.container(key=card_key("example-holdings", "p")):
        table = pd.DataFrame({
            "Mã": rows["symbol"], "Công ty": rows["symbol"].map(lambda s_: names.get(s_, "")),
            "Số lượng": rows["quantity"].map(lambda q: f"{int(q):,}".replace(",", ".")),
            "Tỷ trọng": (values / total).map(lambda w: pct(w) if w == w else "—"),
        })
        if not table["Công ty"].astype(bool).any():   # kho không có tên công ty: bỏ cột trống
            table = table.drop(columns="Công ty")
        st.dataframe(table, hide_index=True, width="stretch")
        st.markdown(f"Tiền mặt **{vnd(state.cash)}** ({pct(state.cash / total) if total else '—'}) · "
                    f"Tổng **{vnd(total)}**")
    st.caption("Muốn khám danh mục thật của bạn? Chọn **Danh mục của tôi** ở Bước 1.")


def _own_table(ctx: AppContext) -> list[str]:
    """Bảng nhập theo dòng: Mã + Số lượng (+ Giá vốn nếu chọn). Trả về các lưu ý cần hiện cho người dùng."""
    state, prices, names = st.session_state, ctx.latest_prices, ctx.symbol_names
    show_cost = state.get("show_cost", False)
    options = sorted(set(names) | set(prices.index) | {r["symbol"] for r in state.draft if r["symbol"]})
    values = {}
    for row in state.draft:
        price = prices.get(str(row["symbol"]).upper()) if row["symbol"] else None
        values[row["id"]] = (row["quantity"] or 0) * price if price else 0.0
    total = sum(values.values()) + float(state.draft_cash or 0)
    widths = [3, 1.4] + ([1.5] if show_cost else []) + [1, 0.45]
    problems = []
    with st.container(key="holdings"):
        header = st.columns(widths)
        labels = ["Mã cổ phiếu", "Số lượng"] + (["Giá vốn (đ/cp)"] if show_cost else []) + ["Tỷ trọng", ""]
        for column, text in zip(header, labels):
            column.caption(f"**{text}**")
        for row in state.draft:
            rid = row["id"]
            cols = st.columns(widths, vertical_alignment="center")
            cols[0].selectbox(
                "Mã cổ phiếu", options, index=options.index(row["symbol"]) if row["symbol"] in options else None,
                key=f"sym_{rid}", placeholder="Gõ mã để tìm, vd FPT", label_visibility="collapsed",
                format_func=lambda s_: f"{s_} · {names[s_]}" if names.get(s_) else s_, accept_new_options=True,
                on_change=_sync_cell, args=(rid, "symbol", f"sym_{rid}"))
            cols[1].number_input("Số lượng", min_value=0, step=100, value=int(row["quantity"] or 0),
                                 key=f"qty_{rid}", label_visibility="collapsed",
                                 on_change=_sync_cell, args=(rid, "quantity", f"qty_{rid}"))
            k = 2
            if show_cost:
                cols[2].number_input("Giá vốn", min_value=0.0, step=100.0, value=row["avg_cost"], format="%.0f",
                                     key=f"cost_{rid}", placeholder="không bắt buộc", label_visibility="collapsed",
                                     on_change=_sync_cell, args=(rid, "avg_cost", f"cost_{rid}"))
                k = 3
            symbol = (row["symbol"] or "").upper()
            price = prices.get(symbol) if symbol else None
            cols[k].markdown(pct(values[rid] / total) if price and total else ":gray[—]")
            cols[k + 1].button("", icon=ICONS["delete"], key=f"del_{rid}", help="Xóa dòng này", type="tertiary",
                               on_click=_delete_row, args=(rid,))
            if symbol and not price:
                problems.append(f"**{symbol}** chưa có dữ liệu: "
                                + ("sau khi xem kết quả, bấm **Cập nhật** ở thanh bên để tải từ SSI." if ctx.has_key
                                   else "máy này chưa có API key SSI nên mã này tạm chưa được tính."))
            if symbol and row["quantity"] and int(row["quantity"]) % 100:
                problems.append(f"**{symbol}**: {int(row['quantity'])} cổ phiếu không phải bội số của 100 (lô chẵn). "
                                "Vẫn tính được, chỉ lưu ý khi đặt lệnh thật.")
        st.button("Thêm mã", icon=ICONS["add"], on_click=_add_row, type="tertiary")

    with st.container(key="cashbox"):
        cash_col, total_col = st.columns([1, 1.6], vertical_alignment="bottom")
        cash_key = f"cash_{state.get('cash_nonce', 0)}"
        cash_col.number_input("Tiền mặt trong tài khoản (đ)", min_value=0.0, step=1_000_000.0, format="%.0f",
                              value=float(state.draft_cash or 0), key=cash_key,
                              on_change=_remember, args=("draft_cash", cash_key))
        stock_value = sum(values.values())
        total_col.markdown(f"Tổng tài sản **{vnd(total)}** :gray[· cổ phiếu {vnd(stock_value)} · tiền mặt "
                           f"{pct(float(state.draft_cash or 0) / total) if total else '—'}]")
    st.checkbox("Nhập thêm giá vốn để tính lãi/lỗ", value=show_cost, key="show_cost_widget",
                on_change=_remember, args=("show_cost", "show_cost_widget"))
    return problems


def portfolio_input(ctx: AppContext) -> None:
    page_header("Nhập danh mục", "Bước 1 · Hồ sơ danh mục. Ba câu hỏi ngắn, xong thì bấm Xem kết quả.")
    state = st.session_state
    if state.get("draft_version") != state.editor_version:
        _load_draft_from_saved()
    if "decl_mode" not in state:
        state.decl_mode = "example" if ctx.active_example in EXAMPLES else "own"
    if state.get("flash"):
        st.toast(state.pop("flash"), icon=":material/check_circle:")
    if state.decl_mode == "example":   # đang tự nhập thì không hiện khung "danh mục ví dụ" để khỏi nhầm
        example_banner(ctx, show_button=False)

    # ---------------- Bước 1
    step_head(1, "Bạn muốn khám danh mục nào?")
    choice = st.radio("Loại danh mục", ["example", "own"], index=0 if state.decl_mode == "example" else 1,
                      key=f"mode_{state.editor_version}", horizontal=True, label_visibility="collapsed",
                      format_func={"example": "Danh mục ví dụ (xem thử ngay)",
                                   "own": "Danh mục của tôi (tự nhập)"}.get)
    if choice != state.decl_mode:
        if choice == "own":
            _switch_to_own()
        else:
            state.decl_mode = "example"
        st.rerun()

    problems: list[str] = []
    if state.decl_mode == "example":
        keys = list(EXAMPLES)
        current = ctx.active_example if ctx.active_example in EXAMPLES else keys[0]
        picked = st.selectbox("Chọn danh mục ví dụ", keys, index=keys.index(current),
                              format_func=lambda k: f"{EXAMPLES[k].title} – {EXAMPLES[k].description}",
                              key=f"example_{state.editor_version}")
        if picked != ctx.active_example:
            ctx.load_example(picked)
        step_head(2, "Các mã trong danh mục")
        _example_table(ctx)
    else:
        step_head(2, "Các mã bạn đang nắm")
        st.caption("Mỗi dòng một mã: chọn mã và nhập số cổ phiếu. Tỷ trọng tự tính theo giá đóng cửa mới nhất.")
        problems = _own_table(ctx)
        for text in problems:
            st.caption(f":material/warning: {text}")

    # ---------------- Bước 3 (không bắt buộc)
    step_head(3, "Bạn chịu lỗ được bao nhiêu?", optional=True)
    answer = st.segmented_control("Mức chịu lỗ", ["skip", "answer"], default="answer" if state.profile_on else "skip",
                                  format_func={"skip": "Bỏ qua", "answer": "Trả lời"}.get,
                                  key=f"profile_choice_{state.get('profile_nonce', 0)}",
                                  label_visibility="collapsed")
    if (answer == "answer") != state.profile_on and answer is not None:
        state.profile_on = answer == "answer"
        st.rerun()
    if state.profile_on:
        a, b = st.columns(2)
        a.slider("Trong một phiên xấu, tôi chịu lỗ tối đa", 1.0, 10.0, value=float(state.max_daily_loss), step=0.5,
                 format="%.1f%%", key="daily_widget", on_change=_remember, args=("max_daily_loss", "daily_widget"),
                 help="So với VaR 95%: mức lỗ mà 95% số phiên không vượt quá.")
        b.slider("Trong một năm, tôi chịu được danh mục giảm từ đỉnh tối đa", 5, 50, value=int(state.max_drawdown),
                 step=5, format="%d%%", key="drawdown_widget", on_change=_remember,
                 args=("max_drawdown", "drawdown_widget"),
                 help="So với mức sụt giảm tối đa của danh mục trong 250 phiên gần nhất.")
        st.caption("Hai mục \"Mức lỗ trong một phiên xấu\" và \"Sụt giảm tối đa 1 năm\" sẽ được so với đúng mức này.")
    else:
        st.caption("Bỏ qua thì hai mục về mức lỗ chỉ để tham khảo, không xếp mức Tốt/Cảnh báo.")

    # ---------------- Xem kết quả
    st.write("")
    changed = state.decl_mode == "own" and _draft_signature() != _saved_signature()
    go, undo, _ = st.columns([1.4, 1, 2.6], vertical_alignment="center")
    if go.button("Xem kết quả", type="primary", icon=":material/arrow_forward:", width="stretch"):
        if changed:
            rows = pd.DataFrame([{k: r[k] for k in ("symbol", "quantity", "avg_cost")}
                                 for r in state.draft if r["symbol"]], columns=["symbol", "quantity", "avg_cost"])
            ctx.save_portfolio(rows, float(state.draft_cash or 0), go=True)
        else:
            st.switch_page(ctx.pages["overview"])
    if changed:
        if undo.button("Hoàn tác", type="tertiary", icon=ICONS["reset"]):
            _load_draft_from_saved()
            st.rerun()
        st.caption(":orange[:material/edit:] Bạn có thay đổi: bấm **Xem kết quả** để lưu và xem kết quả.")
    if ctx.portfolio_error:
        st.error(f"Danh mục chưa hợp lệ: {ctx.portfolio_error}")

    with st.expander("Đã có file danh mục (CSV)? Nhập từ file", icon=ICONS["upload"]):
        st.caption("File gồm 3 cột: `symbol` (mã), `quantity` (số lượng), `avg_cost` (giá vốn, có thể để trống). "
                   "Thêm một dòng `CASH` với `quantity` là số tiền mặt nếu muốn.")
        uploaded = st.file_uploader("Chọn file CSV", type="csv", label_visibility="collapsed")
        if uploaded is not None and state.get("uploaded_name") != uploaded.name:
            try:
                frame = pd.read_csv(uploaded, dtype={"symbol": str})
                is_cash = frame["symbol"].str.upper().str.strip() == "CASH"
                state.uploaded_name = uploaded.name
                state.decl_mode = "own"
                ctx.save_portfolio(frame.loc[~is_cash, ["symbol", "quantity", "avg_cost"]],
                                   float(frame.loc[is_cash, "quantity"].sum()))
            except (KeyError, ValueError) as exc:
                st.error(f"Không đọc được file: {exc}")


# ====================================================================== Thử điều chỉnh

def _whatif_weights_key() -> str:
    return f"whatif_{st.session_state.editor_version}"


def _set_whatif(weights: dict[str, float]) -> None:
    state = st.session_state
    state[_whatif_weights_key()] = dict(weights)
    state.whatif_nonce = state.get("whatif_nonce", 0) + 1   # tạo lại thanh kéo với giá trị mới


def _sync_whatif(symbol: str, widget_key: str) -> None:
    st.session_state[_whatif_weights_key()][symbol] = st.session_state[widget_key]


def whatif(ctx: AppContext) -> None:
    page_header("Thử điều chỉnh", "Bước 3 · Phương án cải thiện. Đổi tỷ trọng các mã bạn đang có và xem ngay kết "
                                  "luận thay đổi ra sao, trước khi tự quyết định. Đây là mô phỏng trên dữ liệu quá khứ, "
                                  "không phải khuyến nghị mua/bán.")
    if not require_report(ctx):
        return
    state, report = st.session_state, ctx.report
    valuation = report.valuation.dropna(subset=["price"])
    total = float(report.totals["total_value"])
    prices = valuation.set_index("symbol")["price"]
    current = {r.symbol: round(float(r.weight_total) * 100, 1) for r in valuation.itertuples()}
    if _whatif_weights_key() not in state:
        state[_whatif_weights_key()] = dict(current)
    weights = state[_whatif_weights_key()]
    nonce = state.get("whatif_nonce", 0)

    left, right = st.columns([1, 1.5], gap="large")
    with left.container(key=card_key("whatif-controls", "p")):
        st.markdown("**Tỷ trọng mới (% tổng tài sản)**")
        for symbol in current:
            st.slider(symbol, 0.0, 100.0, value=float(weights.get(symbol, current[symbol])), step=0.5,
                      format="%.1f%%", key=f"wi_{nonce}_{symbol}", on_change=_sync_whatif,
                      args=(symbol, f"wi_{nonce}_{symbol}"),
                      help=f"Hiện tại: {current[symbol]:.1f}%".replace(".", ","))
        invested = sum(weights.get(s, 0.0) for s in current)
        cash_share = 100 - invested
        if cash_share < -1e-9:
            st.error(f"Tổng tỷ trọng cổ phiếu là {invested:.1f}%, vượt 100%. Hãy giảm bớt một vài mã.".replace(".", ","))
        else:
            st.markdown(f"Tiền mặt còn lại: **{cash_share:.1f}%**".replace(".", ","))
        st.caption("Gợi ý nhanh:")
        a, b, c = st.columns(3)
        if a.button("Hiện tại", width="stretch", help="Trả về tỷ trọng đang có"):
            _set_whatif(current)
            st.rerun()
        if b.button("Chia đều", width="stretch", help="Chia đều phần cổ phiếu hiện có cho các mã"):
            equal = sum(current.values()) / len(current)
            _set_whatif({s: round(equal, 1) for s in current})
            st.rerun()
        if c.button("≤ 10%/mã", width="stretch", help="Giảm mã nào trên 10% về 10% (mốc UCITS), phần thừa "
                                                          "chuyển sang tiền mặt"):
            _set_whatif({s: min(w, 10.0) for s, w in current.items()})
            st.rerun()

    with right:
        if cash_share < -1e-9:
            st.info("Điều chỉnh để tổng tỷ trọng cổ phiếu không quá 100% thì kết quả sẽ hiện ở đây.")
            return
        avg_costs = valuation.set_index("symbol")["avg_cost"].to_dict()
        simulated_portfolio = whatif_calc.portfolio_from_weights({s: weights.get(s, 0.0) / 100 for s in current},
                                                            prices, total, avg_costs)
        if simulated_portfolio.holdings.empty:
            st.info("Hãy giữ ít nhất một mã có tỷ trọng lớn hơn 0 để có kết quả.")
            return
        simulated = build_health_report(simulated_portfolio, ctx.market, participation=ctx.participation,
                                        profile=ctx.profile)
        before_level, before_label, _ = overall_verdict(report.checks)
        after_level, after_label, _ = overall_verdict(simulated.checks)
        with st.container(key=card_key("whatif-verdict", "g")):
            st.markdown(f"**Kết luận chung** &nbsp; {badge(before_level, before_label)} &nbsp;→&nbsp; "
                        f"{badge(after_level, after_label)}")
            changes = whatif_calc.changed_checks(report, simulated)
            if changes.empty:
                st.caption("Chưa có tiêu chí nào đổi mức đánh giá.")
            remaining = [c for c in simulated.checks if c.status in (DANGER, WARNING)]
            remaining.sort(key=lambda c: c.status != DANGER)
            if remaining:
                st.caption("Còn cần chú ý: " + "; ".join(f"{c.name} ({c.value}, {c.status.lower()})"
                                                         for c in remaining[:4]))
            for item in changes.itertuples():
                arrow = ":green[:material/arrow_upward:]" if item.direction == "tốt lên" else \
                    ":red[:material/arrow_downward:]"
                st.markdown(f"{arrow} **{item.name}**: {item.value_before} → {item.value_after} "
                            f"({badge(item.before)} → {badge(item.after)})")
        st.table(whatif_calc.compare_reports(report, simulated), hide_index=True, border="horizontal")
        rows, cash = whatif_calc.to_lots(simulated_portfolio, prices)
        st.caption("Áp dụng sẽ đổi danh mục của bạn theo tỷ trọng mới, số lượng làm tròn theo lô 100 cổ phiếu "
                   "(tỷ trọng thật có thể lệch nhẹ). Bạn vẫn có thể sửa lại ở trang Nhập danh mục.")
        unchanged = all(abs(weights.get(sym, 0.0) - w) < 0.05 for sym, w in current.items())
        if st.button("Áp dụng vào danh mục của tôi", type="primary", icon=ICONS["save"], disabled=unchanged):
            ctx.save_portfolio(rows, cash)


# ====================================================================== Cảnh báo

def alerts(ctx: AppContext) -> None:
    page_header("Cảnh báo và giải thích", "Từng tiêu chí được so với một ngưỡng có nguồn gốc rõ ràng. "
                                          "Mỗi mục cho biết con số, ý nghĩa và nên làm gì.")
    result_tabs(ctx, "alerts")
    if not require_report(ctx):
        return
    checks = ctx.report.checks
    counts = count_by_status(checks)
    levels = [s for s in (DANGER, WARNING, GOOD, INFO) if counts[s]]
    chosen = st.pills("Lọc theo mức", levels, selection_mode="multi", default=levels,
                      format_func=lambda s: f"{s} ({counts[s]})")
    st.caption("Rủi ro cao và Cảnh báo: vượt ngưỡng tham chiếu. Tốt: đạt ngưỡng. Thông tin: thước đo mô tả không có "
               "ngưỡng chuẩn, hoặc ghi chú về độ tin cậy của công cụ đo; không tính vào kết luận chung. Chỉ có 3 mức "
               "đánh giá vì các nguồn tham chiếu chỉ đưa ra 1–2 mốc.")
    shown = [c for c in checks if c.status in (chosen or [])]
    if not shown:
        st.info("Chọn ít nhất một mức để xem.")
    for group in dict.fromkeys(c.group for c in shown):
        st.subheader(group)
        items = [c for c in shown if c.group == group]
        for start in range(0, len(items), 2):
            columns = st.columns(2)
            for column, check in zip(columns, items[start:start + 2]):
                with column.container(key=card_key("alert" + check.name, STATUS_TONE[check.status]),
                                      height="stretch"):
                    st.markdown(f"**{check.name}** &nbsp; {badge(check.status)}")
                    st.markdown(f"#### {check.value}")
                    st.markdown(check.explanation)
                    if check.action:
                        st.markdown(f"{ICONS['action']} **Nên làm gì?** {check.action}")
                    st.caption(f"Ngưỡng: {check.threshold or 'không có'} · Cơ sở: {check.source or '—'}")


# ====================================================================== Phân bổ

def allocation(ctx: AppContext) -> None:
    page_header("Phân bổ", "Tiền của bạn đang nằm ở mã nào, ngành nào, và lãi/lỗ của từng mã.")
    result_tabs(ctx, "allocation")
    if not require_report(ctx):
        return
    report, totals = ctx.report, ctx.report.totals
    diversity = find_check(report, "Mức đa dạng hóa")
    n_eff = float(diversity.value.split()[0].replace(",", ".")) if diversity and diversity.status != INFO else float("nan")
    with st.container(key=card_key("scale", "g")):
        if n_eff == n_eff:
            plot(charts.diversity_scale(n_eff))
        how_to_read(f"danh mục của bạn rủi ro tương đương việc nắm **{diversity.value if diversity else '—'}** có tỷ "
                    "trọng bằng nhau (hình thoi tím). Dưới 5 mã: tập trung cao; 5–10 mã: trung bình; từ 10 mã trở lên: "
                    "đa dạng hóa tốt (Evans & Archer, 1968). Muốn tiến sang phải: thêm mã ở ngành khác hoặc chia tỷ "
                    "trọng đều hơn.")
    col1, col2 = st.columns([3, 2])
    with col1.container(key=card_key("weights", "p"), height="stretch"):
        plot(charts.weights_bar(report.valuation, totals["cash_weight"], totals["cash"]))
        how_to_read("mỗi thanh là phần trăm tổng tài sản; thanh có vân sọc là tiền mặt. Vạch chấm 10% là mức tối đa "
                    "cho một mã theo chuẩn UCITS; thanh vượt vạch là mã đang chiếm quá nhiều.")
    with col2.container(key=card_key("sectors", "g"), height="stretch"):
        plot(charts.sector_bar(report.sectors))
        how_to_read("tỷ trọng từng ngành trên phần cổ phiếu (không tính tiền mặt). Vạch 50%: quá nửa danh mục "
                    "phụ thuộc một ngành.")

    table = report.valuation.sort_values("market_value", ascending=False)
    with st.container(key=card_key("table-alloc", "p")):
        st.markdown("**Chi tiết từng mã**")
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
        st.caption(f"Giá gần nhất: giá đóng cửa phiên {format_date(ctx.market.last_trading_date)}. Giá vốn do bạn "
                   "nhập. Lãi/lỗ chưa trừ thuế, phí.")


# ====================================================================== Rủi ro

def _remember(key: str, widget_key: str) -> None:
    """Giữ lựa chọn khi chuyển trang (Streamlit xóa giá trị của widget khi trang không còn hiển thị)."""
    value = st.session_state[widget_key]
    if value is not None:  # bấm lại nút đang chọn sẽ bỏ chọn (None): giữ lựa chọn cũ
        st.session_state[key] = value


def risk(ctx: AppContext) -> None:
    page_header("Rủi ro", "Danh mục lên xuống mạnh đến đâu so với thị trường, và lúc tệ nhất từng giảm bao nhiêu.")
    result_tabs(ctx, "risk")
    if not require_report(ctx):
        return
    report, m, market = ctx.report, ctx.report.metrics, ctx.market

    controls = st.columns([3, 2])
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
             r2_check.status if r2_check else None, tone="g")
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
               "nằm bên trái đường này. Biểu đồ này luôn dùng 250 phiên gần nhất, giống cách tính VaR.", col2, "g")


# ====================================================================== Thanh khoản & giảm sàn

def liquidity(ctx: AppContext) -> None:
    page_header("Thanh khoản và kịch bản giảm sàn",
                "Nếu cần tiền gấp thì mất mấy ngày mới bán hết, và nếu thị trường giảm sàn thì lỗ bao nhiêu.")
    result_tabs(ctx, "liquidity")
    if not require_report(ctx):
        return
    report, m, totals = ctx.report, ctx.report.metrics, ctx.report.totals

    with st.container(key=card_key("liq-table", "p")):
        st.markdown("#### Bán hết danh mục mất bao lâu?")
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
            "Có tiền sau": liq["days_to_cash"].map(
                lambda d: f"{d:.0f} ngày làm việc" if d == d and d != float("inf") else "—"),
            "Mức thanh khoản": liq["bucket"],
        }), hide_index=True, width="stretch")
        how_to_read("'Có tiền sau' = số phiên cần để bán hết + 2 ngày thanh toán (T+2). Có tiền trong 3 ngày làm việc "
                    "là thanh khoản cao, trong 5 ngày là trung bình (theo SEC Rule 22e-4). 'Bán được tối đa mỗi "
                    "phiên' cho biết danh mục còn có thể lớn đến đâu mà vẫn bán hết trong 1 phiên.")

    st.html('<div class="section-title">Nếu mọi mã cùng giảm sàn</div>')
    s1, s3 = st.columns(2)
    kpi_card(s1, "Giảm sàn 1 phiên", vnd(m["floor_loss_1"]),
             f"Bằng {pct(m['floor_loss_1'] / totals['total_value'])} tổng tài sản.", INFO, tone="p")
    kpi_card(s3, "Giảm sàn 3 phiên liên tiếp", vnd(m["floor_loss_3"]),
             f"Bằng {pct(m['floor_loss_3'] / totals['total_value'])} tổng tài sản.", INFO, tone="g")
    chart_card(charts.stress_bar(report.stress_1, report.stress_3),
               "mỗi cặp cột là số tiền lỗ của một mã; cột vàng có vân sọc là kịch bản 3 phiên. Giá sàn = giá tham "
               "chiếu × (1 − biên độ), làm tròn theo bước giá; biên độ HOSE 7%, HNX 10%, UPCoM 15%. Giả định giá tham "
               "chiếu phiên sau bằng giá đóng cửa gần nhất. Đây là kịch bản cực đoan để hình dung rủi ro, không phải "
               "dự báo.")


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
        kpi_card(cols[0], f"VN-Index phiên {format_date(str(index.index[-1]))}", num(index.iloc[-1]),
                 "Biểu đồ nhỏ: 20 phiên gần nhất.", delta=pct(change, 2), tone="p",
                 chart_data=index.tail(20).round(2).tolist(), chart_type="area")
    if not summary.empty:
        latest = summary.iloc[-1]
        previous = summary.iloc[-2] if len(summary) >= 2 else None
        match_change = (latest["total_match_value"] / previous["total_match_value"] - 1
                        if previous is not None and previous["total_match_value"] else float("nan"))
        kpi_card(cols[1], "Số mã tăng / giảm", f"{latest['advances']:.0f} / {latest['declines']:.0f}",
                 f"Sàn HOSE, phiên {format_date(latest['trading_date'])}.", tone="g")
        kpi_card(cols[2], "Giá trị khớp lệnh", vnd_billion(latest["total_match_value"]),
                 "So với phiên trước. Biểu đồ nhỏ: các phiên đã lưu.", tone="p",
                 delta=pct(match_change, 1) if match_change == match_change else None,
                 chart_data=(summary["total_match_value"] / 1e9).round(0).tolist(), chart_type="bar")
        net = float(latest["foreign_net_value"])
        kpi_card(cols[3], "Khối ngoại mua ròng", vnd_billion(net),
                 "Số âm là bán ròng. Biểu đồ nhỏ: các phiên đã lưu.", tone="g",
                 delta="Mua ròng" if net >= 0 else "Bán ròng",
                 delta_color="normal" if net >= 0 else "inverse", delta_arrow="up" if net >= 0 else "down",
                 chart_data=(summary["foreign_net_value"] / 1e9).round(0).tolist(), chart_type="bar")

    chart_card(charts.index_chart(index), "bấm các nút phía trên để xem nhanh 1 tháng đến toàn bộ lịch sử, hoặc "
               f"kéo thanh trượt bên dưới. {HOW_TO_INTERACT}")

    if len(summary) >= 2:
        col1, col2 = st.columns(2)
        chart_card(charts.foreign_flow_bar(summary),
                   "cột xanh là phiên khối ngoại mua nhiều hơn bán (mua ròng), cột đỏ là bán nhiều hơn mua (bán ròng).", col1)
        chart_card(charts.breadth_chart(summary),
                   "số mã tăng nhiều hơn số mã giảm cho thấy đà tăng lan rộng, không chỉ ở vài mã lớn.", col2, "g")
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

METHOD_CARDS = [
    ("pie_chart", "Số mã hiệu dụng (Effective N)", "1 / Σ(tỷ trọng²)",
     "Danh mục rủi ro như đang nắm bao nhiêu mã chia đều. Nghịch đảo của chỉ số tập trung HHI."),
    ("show_chart", "Độ biến động năm (Volatility)", "độ lệch chuẩn lợi suất ngày × √252",
     "Giá trị danh mục lên xuống mạnh đến đâu trong một năm. Tính trên 250 phiên."),
    ("swap_vert", "Beta và R²", "Cov(danh mục, VN-Index) / Var(VN-Index)",
     "Beta: VN-Index đổi 1% thì danh mục đổi bao nhiêu %. R²: phần biến động đến từ thị trường chung."),
    ("warning", "Giá trị rủi ro (VaR) 95%", "phân vị 5% của 250 lợi suất ngày",
     "Mức lỗ mà 95/100 phiên không vượt quá. Phương pháp mô phỏng lịch sử (Jorion, 2007)."),
    ("trending_down", "Sụt giảm tối đa (Max Drawdown)", "min(giá trị / đỉnh trước đó − 1)",
     "Lần giảm sâu nhất từ một đỉnh xuống đáy trong 250 phiên vừa qua."),
    ("water_drop", "Thanh khoản", "⌈số lượng / (tỷ lệ tham gia × ADV20)⌉ + 2",
     "Số ngày làm việc để bán hết và nhận tiền (T+2), xếp loại theo SEC Rule 22e-4."),
    ("south", "Kịch bản giảm sàn", "giá × (1 − biên độ), làm tròn theo bước giá",
     "Áp biên độ HOSE 7%, HNX 10%, UPCoM 15% liên tiếp 1 và 3 phiên."),
    ("monitor_heart", "Kết luận chung", "mức xấu nhất trong các tiêu chí",
     "Chỉ cần một mục Rủi ro cao là cần xem lại; không cộng điểm hay gán trọng số."),
]
LIMITS = [
    ("schedule", "Dữ liệu theo phiên (cuối ngày), không phải thời gian thực."),
    ("history", "Chỉ số rủi ro dựa trên quá khứ; quá khứ không bảo đảm cho tương lai. VaR không cho biết mức lỗ "
                "trong 5% phiên xấu nhất."),
    ("tune", "Giả định tỷ trọng cố định và tỷ lệ tham gia thanh khoản là đơn giản hóa."),
    ("policy", "Ngưỡng UCITS và SEC là chuẩn tham chiếu của quỹ đầu tư, không bắt buộc với nhà đầu tư cá nhân; "
               "ngưỡng ngành 50% là quy tắc tự đặt."),
    ("person", "Danh mục do người dùng tự nhập hoặc chọn từ 3 danh mục ví dụ (giá thật, số lượng giả định); ứng dụng "
               "không đọc tài khoản chứng khoán thật."),
    ("tune", "Thử điều chỉnh là mô phỏng trên dữ liệu quá khứ, không phải khuyến nghị mua/bán; mức chịu lỗ do người "
             "dùng tự khai nên chỉ phản ánh cảm nhận của chính họ."),
    ("receipt_long", "Không tính thuế, phí giao dịch, cổ tức tiền mặt và lãi tiền gửi."),
]


def method(ctx: AppContext) -> None:
    page_header("Phương pháp và dữ liệu", "Dữ liệu lấy từ đâu, các con số được tính thế nào, ngưỡng dựa trên "
                                          "nguồn nào và sản phẩm có những giới hạn gì.")
    st.html('<div class="section-title">Dữ liệu đi qua 5 bước</div>')
    st.html(flow_html())
    st.caption("Token SSI không kèm OTP nên chỉ có quyền đọc dữ liệu, không đặt lệnh được. Máy có API key: mở ứng dụng "
               "sau 15:00 ngày làm việc sẽ tự tải phiên mới; máy không có key (vd máy người chấm) dùng bản dữ liệu SSI "
               "lưu kèm mã nguồn và ghi rõ phiên chốt.")

    st.html('<div class="section-title">Cách tính từng chỉ số</div>')
    for start in range(0, len(METHOD_CARDS), 4):
        for i, (column, (icon, title, formula, text)) in enumerate(zip(st.columns(4), METHOD_CARDS[start:start + 4])):
            with column.container(key=card_key("method" + title, "g" if (start // 4 + i) % 2 else "p"),
                                  height="stretch"):
                st.html(f'<div class="feature-icon{" gold" if (start // 4 + i) % 2 else ""}">'
                        f'<span class="ms">{icon}</span></div>')
                st.markdown(f"**{title}**")
                st.markdown(f"`{formula}`")
                st.caption(text)

    if ctx.report is not None:
        st.html('<div class="section-title">Ngưỡng cảnh báo và cơ sở</div>')
        frame = ctx.report.checks_frame()
        with st.container(key=card_key("thresholds", "p")):
            st.table(pd.DataFrame({"Nhóm": frame["group"], "Tiêu chí": frame["name"],
                                   "Ngưỡng": frame["threshold"].replace("", "không có"), "Cơ sở": frame["source"]}),
                     hide_index=True, border="horizontal")

    if ctx.report is not None and ctx.report.backtest is not None and ctx.report.backtest.observations:
        bt = ctx.report.backtest
        st.html('<div class="section-title">Kiểm định mô hình VaR</div>')
        st.caption("Câu hỏi: con số VaR 95% có dự báo đúng không? Cách làm: tính lại VaR cho từng ngày trong quá khứ, "
                   "mỗi ngày chỉ dùng 250 phiên trước đó, rồi đếm số ngày lỗ thực tế vượt VaR. Mô hình đúng thì "
                   "khoảng 5% số ngày vượt, và các lần vượt không dồn cục.")
        k1, k2, k3, k4 = st.columns(4)
        kpi_card(k1, "Số ngày kiểm định", f"{bt.observations} ngày",
                 f"Từ {format_date(str(bt.series.index.min()))} đến {format_date(str(bt.series.index.max()))}.", tone="p")
        kpi_card(k2, "Số lần lỗ vượt VaR", f"{bt.exceptions} lần",
                 f"Tỷ lệ {pct(bt.exception_rate, 1)}; kỳ vọng {pct(bt.expected_rate, 0)} ≈ {bt.expected_exceptions:.0f} lần.",
                 tone="g")
        if bt.passes_pof:
            pof_note, pof_status = "p ≥ 0,05: tỷ lệ vượt phù hợp với 5%.", GOOD
        elif bt.too_few_exceptions:
            pof_note, pof_status = "Vượt ít hơn kỳ vọng: VaR đang thận trọng (ước lượng lỗ cao hơn thực tế).", INFO
        else:
            pof_note, pof_status = "Vượt nhiều hơn kỳ vọng: VaR đang đánh giá thấp rủi ro.", WARNING
        kpi_card(k3, "Kupiec: tỷ lệ vượt", f"p = {num(bt.p_pof, 2)}", pof_note, pof_status, tone="p")
        kpi_card(k4, "Christoffersen: độc lập", f"p = {num(bt.p_ind, 2)}",
                 "p ≥ 0,05: các lần vượt không dồn cục." if bt.passes_independence else
                 "p < 0,05: các lần vượt dồn vào cùng giai đoạn, VaR phản ứng chậm khi thị trường xấu đi.",
                 GOOD if bt.passes_independence else WARNING, tone="g")
        chart_card(charts.backtest_chart(bt.series),
                   "cột tím là lãi/lỗ từng ngày của danh mục (tỷ trọng hiện tại), đường vàng là mức lỗ VaR đã dự báo "
                   "từ hôm trước. Cột đỏ có dấu X là ngày lỗ vượt dự báo. Nhiều cột đỏ hơn kỳ vọng nghĩa là VaR đang "
                   f"đánh giá thấp rủi ro. {HOW_TO_INTERACT}")

    st.html('<div class="section-title">Chất lượng và truy vết dữ liệu</div>')
    coverage = ctx.store_info.get("coverage", pd.DataFrame())
    log = ctx.store_info.get("fetch_log", pd.DataFrame())
    if coverage.empty:
        st.info("Chưa có dữ liệu trong kho.")
    else:
        data_quality_section(ctx, coverage, log)
    limits_section()


def limits_section() -> None:
    st.html('<div class="section-title">Giới hạn của sản phẩm</div>')
    left, right = st.columns(2)
    for i, (icon, text) in enumerate(LIMITS):
        with (left if i % 2 == 0 else right).container(key=card_key("limit" + text[:20], "g" if i % 2 else "p")):
            st.markdown(f":violet[:material/{icon}:] {text}")
    st.caption(f":material/gavel: {DISCLAIMER}")


def data_quality_section(ctx: AppContext, coverage: pd.DataFrame, log: pd.DataFrame) -> None:
    stock_log = log[log["dataset"] == "stock_daily"].drop_duplicates("symbol") if not log.empty else log
    missing = int(stock_log["missing_sessions"].fillna(0).sum()) if not stock_log.empty else 0
    stocks = coverage[coverage["kind"] == "stock"]
    q1, q2, q3, q4 = st.columns(4)
    kpi_card(q1, "Số mã trong kho", f"{len(stocks)} mã", "Cộng thêm chỉ số VN-Index.", tone="p")
    kpi_card(q2, "Số phiên đã tự thu thập", f"{int(stocks['sessions'].max()) if not stocks.empty else 0} phiên",
             f"Mỗi mã, tự tải từ SSI: từ {format_date(stocks['first'].min())} đến "
             f"{format_date(stocks['last'].max())}." if not stocks.empty else "Chưa có.", tone="g")
    kpi_card(q3, "Phiên thiếu", f"{missing} phiên", "So với lịch giao dịch của VN-Index, ở lần tải gần nhất.",
             GOOD if missing == 0 else WARNING, tone="p")
    collection = ctx.store_info.get("collection", pd.DataFrame())
    sessions = sessions_collected(collection)
    kpi_card(q4, "Số phiên đã chạy cập nhật", f"{len(sessions)} phiên",
             f"Lần tải gần nhất: {format_time(log['started_at'].iloc[0])}." if not log.empty else "Chưa tải lần nào.",
             tone="g")
    quality = ctx.store_info.get("quality", pd.DataFrame())
    if not quality.empty and "cross_checked" in quality and quality["cross_checked"].fillna(0).sum() > 0:
        st.markdown(f"Đối chiếu lợi suất tự tính từ giá đóng cửa với % thay đổi do SSI công bố trên "
                    f"**{int(quality['cross_checked'].fillna(0).sum()):,} phiên**".replace(",", ".")
                    + f": **{int(quality['cross_mismatch'].fillna(0).sum())} phiên** lệch quá 1 điểm %.")
    if not collection.empty:
        with st.container(key=card_key("collection", "p")):
            st.markdown(f"**Nhật ký thu thập theo phiên** · ứng dụng đã chạy cập nhật vào {len(sessions)} phiên: "
                        + ", ".join(format_date(s_) for s_ in sessions))
            st.dataframe(pd.DataFrame({
                "Lúc tải (giờ VN)": collection["started_at"].map(format_time),
                "Phiên": collection["session"].map(format_date),
                "Tải đúng ngày": collection["on_time"].map({True: "Có", False: "Tải bù"}),
                "Số chuỗi": collection["series"],
                "Thành công": collection["ok"],
                "Lỗi": collection["error"],
                "Mã lỗi": collection["failed_symbols"],
            }), hide_index=True, width="stretch")
            st.caption("Mỗi dòng là một lần cập nhật. \"Phiên\" là phiên mới nhất lẽ ra đã có dữ liệu tại lúc tải; "
                       "\"Tải bù\" là phiên được tải vào hôm sau (dữ liệu vẫn đầy đủ nhờ mỗi lần tải lại 14 ngày gần nhất).")
    if not quality.empty and "missing" in quality:
        with st.expander("Bảng chất lượng dữ liệu từng mã", icon=":material/fact_check:"):
            st.dataframe(pd.DataFrame({
                "Mã": quality["symbol"], "Số phiên": quality["sessions"],
                "Phiên thiếu": quality["missing"], "Dòng bị gắn cờ": quality["flagged"],
                "Phiên có giá đã điều chỉnh": quality["adjusted"], "Phiên đối chiếu": quality["cross_checked"],
                "Lệch > 1 điểm %": quality["cross_mismatch"],
            }), hide_index=True, width="stretch")
    with st.expander("Bảng độ phủ dữ liệu từng mã", icon=":material/table:"):
        st.dataframe(pd.DataFrame({
            "Loại": coverage["kind"].map(KIND_LABELS),
            "Mã": coverage["symbol"],
            "Số phiên": coverage["sessions"],
            "Từ ngày": coverage["first"].map(format_date),
            "Đến ngày": coverage["last"].map(format_date),
        }), hide_index=True, width="stretch")
    if not log.empty:
        with st.expander("Nhật ký tải dữ liệu từ SSI (mới nhất ở trên)", icon=":material/history:"):
            st.dataframe(pd.DataFrame({
                "Thời điểm": log["started_at"].map(format_time),
                "Dữ liệu": log["dataset"].map(lambda d: DATASET_LABELS.get(d, d)),
                "Mã": log["symbol"],
                "Cách tải": log["mode"].map(lambda d: MODE_LABELS.get(d, d)),
                "Số phiên nhận": log["rows_kept"],
                "Kết quả": log["status"].map(lambda d: RESULT_LABELS.get(d, d)),
                "Ghi chú": log["message"].fillna(""),
            }), hide_index=True, width="stretch")
