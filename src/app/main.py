"""
Ứng dụng Streamlit "Khám Sức Khỏe Danh Mục".

Cách chạy (trong thư mục gốc của repo, đã kích hoạt .venv):
    streamlit run src/app/main.py

Hai nguồn dữ liệu:
    - "Dữ liệu trực tiếp (SSI)": đọc kho data/portfolio.db, có nút cập nhật từ SSI (cần API key trong .env);
    - "Dữ liệu mẫu": đọc data_sample/sample.db - dữ liệu THẬT đã tải từ SSI và chốt ở một ngày,
      để người chấm chạy được ngay mà không cần API key.

Ứng dụng chỉ đọc dữ liệu thị trường; không đặt lệnh, không đọc tài khoản chứng khoán.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # để import được src.*

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src import config  # noqa: E402
from src.app import charts  # noqa: E402
from src.data.storage import Storage  # noqa: E402
from src.data.updater import DataUpdater  # noqa: E402
from src.finance.health import (  # noqa: E402
    DANGER, DISCLAIMER, GOOD, INFO, WARNING, build_health_report, num, pct, vnd, vnd_short,
)
from src.finance.market_data import MarketData, load_market_data  # noqa: E402
from src.finance.portfolio import CASH_SYMBOL, PortfolioError, build_portfolio  # noqa: E402
from src.ssi_api.client import SSIClient, SSIError  # noqa: E402

SOURCE_LIVE = "Dữ liệu trực tiếp (SSI)"
SOURCE_SAMPLE = "Dữ liệu mẫu (không cần API key)"
STATUS_ICON = {DANGER: "⛔", WARNING: "⚠️", GOOD: "✅", INFO: "ℹ️"}
PERIODS = {"1 năm": 250, "2 năm": 500, "3 năm": 750}

st.set_page_config(page_title=config.APP_NAME, page_icon="🩺", layout="wide")


# ====================================================================== đọc dữ liệu

def db_path_for(source: str) -> Path:
    return config.DB_PATH if source == SOURCE_LIVE else config.SAMPLE_DB_PATH


@st.cache_data(show_spinner=False)
def cached_market_data(db_path: str, db_mtime: float, symbols: tuple[str, ...]) -> MarketData:
    """Đọc dữ liệu từ kho; db_mtime nằm trong khóa cache để tự đọc lại khi kho vừa được cập nhật."""
    with Storage(db_path) as storage:
        return load_market_data(storage, list(symbols))


@st.cache_data(show_spinner=False)
def cached_store_info(db_path: str, db_mtime: float) -> dict[str, pd.DataFrame]:
    with Storage(db_path) as storage:
        return {
            "coverage": storage.coverage(),
            "fetch_log": storage.load_fetch_log(limit=30),
            "market_summary": storage.load_market_summary("HOSE"),
        }


def default_portfolio_rows() -> tuple[pd.DataFrame, float]:
    """Danh mục minh họa ban đầu (từ data_sample/demo_portfolio.csv)."""
    try:
        rows = pd.read_csv(config.DEMO_PORTFOLIO_PATH, dtype={"symbol": str})
    except FileNotFoundError:
        rows = pd.DataFrame({"symbol": config.DEFAULT_SYMBOLS, "quantity": [1000] * 6, "avg_cost": [None] * 6})
    is_cash = rows["symbol"].str.upper() == CASH_SYMBOL
    cash = float(rows.loc[is_cash, "quantity"].sum())
    return rows.loc[~is_cash, ["symbol", "quantity", "avg_cost"]].reset_index(drop=True), cash


def format_time(iso_text: str | None) -> str:
    """'2026-11-17T15:05:12+07:00' -> '17/11/2026 15:05' (giờ Việt Nam)."""
    if not iso_text:
        return "chưa có"
    try:
        return datetime.fromisoformat(iso_text).astimezone(config.VN_TZ).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso_text


def format_date(iso_date: str | None) -> str:
    if not iso_date:
        return "chưa có"
    return datetime.fromisoformat(iso_date).strftime("%d/%m/%Y")


# ====================================================================== thao tác với SSI

def check_ssi_connection() -> None:
    try:
        SSIClient.from_env().check_connection()
        st.session_state.ssi_status = ("ok", datetime.now(config.VN_TZ).strftime("%H:%M %d/%m"))
    except SSIError as exc:
        st.session_state.ssi_status = ("error", str(exc))


def run_update(symbols: list[str]) -> None:
    """Cập nhật kho từ SSI cho các mã trong danh mục (chỉ tải phần mới)."""
    try:
        client = SSIClient.from_env()
    except SSIError as exc:
        st.session_state.ssi_status = ("error", str(exc))  # thông báo lỗi kết nối hiện ở đầu trang
        return
    with st.spinner("Đang tải dữ liệu từ SSI (khoảng 1 giây cho mỗi yêu cầu)..."):
        with Storage(config.DB_PATH) as storage:
            client.raw_hook = storage.save_raw
            results = DataUpdater(client, storage).run(symbols)
    failed = [r for r in results if r.status != "ok"]
    if failed and len(failed) == len(results):
        st.session_state.ssi_status = ("error", failed[0].message)
    else:
        st.session_state.ssi_status = ("ok", datetime.now(config.VN_TZ).strftime("%H:%M %d/%m"))
    if failed:
        detail = "; ".join(f"{r.symbol}: {r.message}" for r in failed)
        st.session_state.update_message = ("warning", f"Cập nhật xong nhưng có {len(failed)} chuỗi lỗi - {detail}")
    else:
        st.session_state.update_message = ("success", f"Đã cập nhật {len(results)} chuỗi dữ liệu, "
                                                      f"{client.request_count} yêu cầu tới SSI.")
    cached_market_data.clear()
    cached_store_info.clear()


# ====================================================================== thanh bên: thiết lập

if "portfolio_rows" not in st.session_state:
    st.session_state.portfolio_rows, st.session_state.cash = default_portfolio_rows()
    st.session_state.ssi_status = ("unknown", "")

with st.sidebar:
    st.header("Thiết lập")
    live_available = config.DB_PATH.exists()
    source = st.radio(
        "Nguồn dữ liệu", [SOURCE_LIVE, SOURCE_SAMPLE], index=0 if live_available else 1,
        help="Dữ liệu mẫu là dữ liệu thật tải từ SSI và chốt ở một ngày, dùng khi không có API key.",
    )

    st.subheader("Danh mục của bạn")
    uploaded = st.file_uploader("Tải lên file CSV (symbol, quantity, avg_cost)", type="csv")
    if uploaded is not None and st.session_state.get("uploaded_name") != uploaded.name:
        try:
            frame = pd.read_csv(uploaded, dtype={"symbol": str})
            parsed = build_portfolio(frame)
            st.session_state.portfolio_rows = parsed.holdings
            st.session_state.cash = parsed.cash
            st.session_state.uploaded_name = uploaded.name
            st.session_state.pop("editor", None)
        except (PortfolioError, ValueError) as exc:
            st.error(f"File danh mục không hợp lệ: {exc}")

    edited_rows = st.data_editor(
        st.session_state.portfolio_rows, key="editor", num_rows="dynamic", hide_index=True,
        column_config={
            "symbol": st.column_config.TextColumn("Mã", required=True, max_chars=10, width="small"),
            "quantity": st.column_config.NumberColumn("Số lượng", min_value=0, step=100, format="%d"),
            "avg_cost": st.column_config.NumberColumn("Giá vốn (đ)", min_value=0, step=50, format="%d"),
        },
    )
    cash = st.number_input("Tiền mặt (đ)", min_value=0.0, value=float(st.session_state.cash), step=1_000_000.0,
                           format="%.0f")
    if st.button("Khôi phục danh mục minh họa"):
        st.session_state.portfolio_rows, st.session_state.cash = default_portfolio_rows()
        st.session_state.pop("editor", None)
        st.rerun()

    st.subheader("Giả định phân tích")
    participation = st.slider(
        "Tỷ lệ tối đa khối lượng thị trường bán mỗi phiên", min_value=5, max_value=50, value=20, step=5,
        format="%d%%", help="Bán quá nhiều so với khối lượng giao dịch thường ngày sẽ tự đẩy giá xuống.",
    ) / 100
    period_label = st.segmented_control("Khoảng thời gian biểu đồ", list(PERIODS), default="1 năm") or "1 năm"

    if source == SOURCE_LIVE:
        st.subheader("Kết nối SSI")
        col_a, col_b = st.columns(2)
        if col_a.button("Kiểm tra kết nối", width="stretch"):
            check_ssi_connection()
        update_clicked = col_b.button("Cập nhật dữ liệu", type="primary", width="stretch")
    else:
        update_clicked = False


# ====================================================================== phần đầu trang

st.title(f"🩺 {config.APP_NAME}")
st.markdown(f"**Mục tiêu:** {config.APP_GOAL}.  \n**Dành cho:** {config.APP_USERS}.")
st.caption(f"⚠️ {DISCLAIMER} Sản phẩm chỉ đọc dữ liệu thị trường từ SSI FastConnect API, không đặt lệnh "
           "và không đọc tài khoản chứng khoán của bạn.")

# Kiểm tra danh mục người dùng nhập
try:
    rows = pd.concat([edited_rows, pd.DataFrame({"symbol": [CASH_SYMBOL], "quantity": [cash]})], ignore_index=True)
    portfolio = build_portfolio(rows.dropna(subset=["symbol"]))
except PortfolioError as exc:
    st.error(f"Danh mục chưa hợp lệ: {exc}. Hãy sửa ở thanh bên trái.")
    st.stop()

if update_clicked:
    run_update(portfolio.symbols)

db_path = db_path_for(source)
if not db_path.exists():
    if source == SOURCE_LIVE:
        st.error("Chưa có kho dữ liệu trực tiếp (data/portfolio.db). Bấm **Cập nhật dữ liệu** ở thanh bên "
                 "(cần API key SSI trong file .env), hoặc chọn **Dữ liệu mẫu**.")
    else:
        st.error("Không tìm thấy dữ liệu mẫu data_sample/sample.db. Hãy chạy: `python scripts/export_sample.py`.")
    st.stop()

db_mtime = db_path.stat().st_mtime
market = cached_market_data(str(db_path), db_mtime, tuple(portfolio.symbols))
store_info = cached_store_info(str(db_path), db_mtime)

# Thanh trạng thái dữ liệu
status_kind, status_text = st.session_state.ssi_status
if source == SOURCE_SAMPLE:
    connection = "Không dùng (dữ liệu mẫu)"
elif status_kind == "ok":
    connection = f"🟢 Đã kết nối ({status_text})"
elif status_kind == "error":
    connection = "🔴 Lỗi kết nối"
else:
    connection = "⚪ Chưa kiểm tra"
status_items = {
    "Nguồn dữ liệu": "SSI FastConnect - trực tiếp" if source == SOURCE_LIVE else "SSI FastConnect - bản mẫu",
    "Phiên mới nhất": format_date(market.last_trading_date),
    "Cập nhật lúc (giờ VN)": format_time(market.last_fetched_at),
    "Kết nối SSI": connection,
}
for column, (label, value) in zip(st.columns(4), status_items.items()):
    column.caption(label)
    column.markdown(f"**{value}**")

if "update_message" in st.session_state:
    kind, message = st.session_state.pop("update_message")
    getattr(st, kind)(message)
if source == SOURCE_LIVE and status_kind == "error":
    st.error(f"Không kết nối được SSI: {status_text}. Ứng dụng tiếp tục dùng dữ liệu đã lưu trong kho.")
if source == SOURCE_SAMPLE:
    st.info(f"Đang dùng **dữ liệu mẫu**: dữ liệu thật tải từ SSI, chốt đến phiên "
            f"{format_date(market.last_trading_date)}. Không phải dữ liệu thời gian thực.")
elif market.last_trading_date:
    age = (datetime.now(config.VN_TZ).date() - datetime.fromisoformat(market.last_trading_date).date()).days
    if age > 4:
        st.warning(f"Dữ liệu đã cũ {age} ngày. Bấm **Cập nhật dữ liệu** ở thanh bên để lấy phiên mới nhất.")

if market.missing_symbols:
    hint = ("Bấm **Cập nhật dữ liệu** để tải các mã này từ SSI." if source == SOURCE_LIVE
            else "Dữ liệu mẫu chỉ có các mã của danh mục minh họa.")
    st.warning(f"Chưa có dữ liệu cho: **{', '.join(market.missing_symbols)}**. Các mã này tạm bị loại khỏi phân tích. {hint}")
if len(market.missing_symbols) == len(portfolio.symbols) or market.index_close.empty:
    st.error("Không đủ dữ liệu để phân tích danh mục này.")
    st.stop()

report = build_health_report(portfolio, market, participation=participation)
m, totals = report.metrics, report.totals
sessions = PERIODS[period_label]

# ====================================================================== chỉ số tổng hợp

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Tổng tài sản", vnd_short(totals["total_value"]), delta=f"{vnd_short(totals['pnl'])} lãi/lỗ", delta_color="normal",
          help="Giá trị cổ phiếu theo giá đóng cửa gần nhất cộng tiền mặt. Phần chênh lệch là lãi/lỗ chưa thực hiện.")
k2.metric("VaR 95% (1 ngày)", vnd_short(m["var_amount"]), help="95% số phiên trong 250 phiên gần nhất, danh mục "
          "(với tỷ trọng hiện tại) không lỗ quá mức này.")
k3.metric("Beta so với VN-Index", num(m["beta"]), help="VN-Index thay đổi 1% thì danh mục thay đổi khoảng beta %.")
n_eff_check = next((c for c in report.checks if c.name.startswith("Số mã hiệu dụng")), None)
k4.metric("Số mã hiệu dụng", n_eff_check.value if n_eff_check else "-",
          help="Danh mục tương đương bao nhiêu mã có tỷ trọng bằng nhau. Từ 10 trở lên là đa dạng hóa tốt.")
k5.metric("Giảm sàn 1 phiên", vnd_short(m["floor_loss_1"]),
          help="Tổn thất nếu mọi mã cùng giảm sàn 1 phiên. Kịch bản cực đoan, không phải dự báo.")

# ====================================================================== các thẻ phân tích

tab_alert, tab_alloc, tab_risk, tab_liq, tab_market, tab_method = st.tabs(
    ["Cảnh báo & giải thích", "Phân bổ", "Rủi ro", "Thanh khoản & kịch bản", "Thị trường", "Dữ liệu & phương pháp"]
)

with tab_alert:
    counts = pd.Series([c.status for c in report.checks]).value_counts()
    st.markdown(" · ".join(f"{STATUS_ICON[s]} **{counts.get(s, 0)}** {s.lower()}" for s in (DANGER, WARNING, GOOD, INFO)))
    for group in dict.fromkeys(c.group for c in report.checks):
        st.subheader(group)
        for check in (c for c in report.checks if c.group == group):
            with st.container(border=True):
                left, right = st.columns([3, 1])
                left.markdown(f"{STATUS_ICON[check.status]} **{check.name}**: {check.value}  \n{check.explanation}")
                right.markdown(f"**{check.status}**")
                right.caption(f"Ngưỡng: {check.threshold or '—'}")
                if check.source:
                    left.caption(f"Cơ sở: {check.source}")

with tab_alloc:
    col1, col2 = st.columns(2)
    col1.plotly_chart(charts.weights_bar(report.valuation, totals["cash_weight"]), width="stretch")
    col2.plotly_chart(charts.sector_bar(report.sectors), width="stretch")
    table = report.valuation[["symbol", "quantity", "avg_cost", "price", "market_value", "weight_total", "pnl", "pnl_pct"]]
    st.dataframe(
        table, hide_index=True, width="stretch",
        column_config={
            "symbol": "Mã", "quantity": st.column_config.NumberColumn("Số lượng", format="localized"),
            "avg_cost": st.column_config.NumberColumn("Giá vốn", format="localized"),
            "price": st.column_config.NumberColumn("Giá gần nhất", format="localized"),
            "market_value": st.column_config.NumberColumn("Giá trị (đ)", format="localized"),
            "weight_total": st.column_config.NumberColumn("Tỷ trọng", format="percent"),
            "pnl": st.column_config.NumberColumn("Lãi/lỗ (đ)", format="localized"),
            "pnl_pct": st.column_config.NumberColumn("Lãi/lỗ (%)", format="percent"),
        },
    )
    st.caption("Giá gần nhất là giá đóng cửa của phiên mới nhất trong kho. Giá vốn do người dùng nhập.")

with tab_risk:
    available = [s for s in portfolio.symbols if s in market.close.columns]
    compare = st.multiselect("So sánh thêm với từng mã (tối đa 3)", available, max_selections=3,
                             placeholder="Chọn mã để vẽ thêm đường lợi suất")
    stock_returns = market.close.pct_change(fill_method=None)
    extra = {symbol: stock_returns[symbol] for symbol in compare}
    st.plotly_chart(charts.growth_chart(report.portfolio_returns, report.market_returns, extra, sessions),
                    width="stretch")
    st.caption("Giả định giữ nguyên tỷ trọng hiện tại trong suốt giai đoạn (tiền mặt không sinh lời). "
               "Đây là cách đo rủi ro của danh mục HIỆN TẠI, không phải lãi/lỗ bạn đã thực sự có.")
    col1, col2 = st.columns(2)
    col1.plotly_chart(charts.drawdown_chart(report.portfolio_returns, sessions), width="stretch")
    col2.plotly_chart(charts.returns_histogram(report.portfolio_returns, m["var_pct"]), width="stretch")
    r1, r2, r3 = st.columns(3)
    r1.metric("Độ biến động năm", pct(m["volatility"]), help=f"VN-Index: {pct(m['market_volatility'])}")
    r2.metric("Phần rủi ro từ thị trường (R²)", pct(m["r_squared"], 0))
    r3.metric("Sụt giảm tối đa trong 1 năm", pct(m["max_drawdown_1y"]))

with tab_liq:
    st.markdown(f"Giả định mỗi phiên chỉ bán tối đa **{pct(participation, 0)}** khối lượng khớp lệnh trung bình "
                "20 phiên, cộng **2 ngày** thanh toán T+2. Phân loại theo SEC Rule 22e-4: có tiền trong ≤ 3 ngày "
                "làm việc là thanh khoản cao, ≤ 5 ngày là trung bình, lâu hơn là thấp.")
    liq = report.liquidity[["symbol", "quantity", "adv", "position_pct_adv", "sessions_to_sell", "days_to_cash", "bucket"]].copy()
    liq["adv"] = liq["adv"].round(0)
    st.dataframe(
        liq.replace([float("inf")], float("nan")), hide_index=True, width="stretch",
        column_config={
            "symbol": "Mã", "quantity": st.column_config.NumberColumn("Số lượng", format="localized"),
            "adv": st.column_config.NumberColumn("KL TB 20 phiên", format="localized"),
            "position_pct_adv": st.column_config.NumberColumn("% KL TB đang nắm", format="percent"),
            "sessions_to_sell": st.column_config.NumberColumn("Số phiên bán", format="%d"),
            "days_to_cash": st.column_config.NumberColumn("Ngày có tiền", format="%d"),
            "bucket": "Thanh khoản",
        },
    )
    st.divider()
    st.plotly_chart(charts.stress_bar(report.stress_1, report.stress_3), width="stretch")
    s1, s3 = st.columns(2)
    s1.metric("Giảm sàn 1 phiên", vnd_short(m["floor_loss_1"]), delta=f"-{pct(m['floor_loss_1'] / totals['total_value'])} tổng tài sản",
              delta_color="off")
    s3.metric("Giảm sàn 3 phiên liên tiếp", vnd_short(m["floor_loss_3"]),
              delta=f"-{pct(m['floor_loss_3'] / totals['total_value'])} tổng tài sản", delta_color="off")
    st.caption("Giá sàn = giá tham chiếu × (1 − biên độ), làm tròn lên theo bước giá. Biên độ: HOSE 7%, HNX 10%, "
               "UPCoM 15%. Giả định giá tham chiếu phiên sau bằng giá đóng cửa gần nhất. Kịch bản cực đoan, không phải dự báo.")

with tab_market:
    summary = store_info["market_summary"]
    index = market.index_close
    if len(index) >= 2:
        change = index.iloc[-1] / index.iloc[-2] - 1
        st.metric(f"VN-Index phiên {format_date(str(index.index[-1]))}", num(index.iloc[-1]), delta=pct(change, 2))
    if summary.empty:
        st.info("Chưa có tổng hợp thị trường. Dữ liệu này được lưu mỗi lần chạy cập nhật.")
    else:
        latest = summary.iloc[-1]
        st.subheader(f"Sàn HOSE phiên {format_date(latest['trading_date'])}")
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Số mã tăng / giảm", f"{latest['advances']:.0f} / {latest['declines']:.0f}")
        b2.metric("Số mã trần / sàn", f"{latest['ceiling']:.0f} / {latest['floor']:.0f}")
        b3.metric("Giá trị khớp lệnh", vnd_short(latest["total_match_value"]))
        b4.metric("Khối ngoại mua ròng", vnd_short(latest["foreign_net_value"]))
        st.dataframe(
            summary.sort_values("trading_date", ascending=False)[
                ["trading_date", "index_value", "advances", "declines", "total_match_value", "foreign_net_value"]],
            hide_index=True, width="stretch",
            column_config={
                "trading_date": "Phiên", "index_value": st.column_config.NumberColumn("VN-Index", format="localized"),
                "advances": "Số mã tăng", "declines": "Số mã giảm",
                "total_match_value": st.column_config.NumberColumn("Giá trị khớp (đ)", format="localized"),
                "foreign_net_value": st.column_config.NumberColumn("Khối ngoại ròng (đ)", format="localized"),
            },
        )

with tab_method:
    st.subheader("Phương pháp tính")
    st.markdown(
        "- **Nguồn dữ liệu:** SSI FastConnect API v3 (dữ liệu theo phiên, giá đã điều chỉnh cho cổ tức và cổ phiếu "
        "thưởng; VN-Index; danh sách mã kèm ngành ICB). Token không kèm OTP nên chỉ có quyền đọc dữ liệu.\n"
        "- **Lợi suất ngày** = giá đóng cửa đã điều chỉnh hôm nay / phiên trước − 1. Danh mục giữ **tỷ trọng hiện tại** "
        "cố định, tiền mặt có lợi suất 0.\n"
        "- **Số mã hiệu dụng** = 1 / Σ(tỷ trọng²) (chỉ số HHI).\n"
        "- **Độ biến động năm** = độ lệch chuẩn lợi suất ngày × √252. **Beta** = Cov(r_danh mục, r_VN-Index) / Var(r_VN-Index), "
        "250 phiên. **R²** = bình phương hệ số tương quan với VN-Index.\n"
        "- **VaR lịch sử 95%, 1 ngày** = phân vị 5% của 250 lợi suất ngày gần nhất (mô phỏng lịch sử).\n"
        "- **Thanh khoản:** số phiên bán = ⌈số lượng / (tỷ lệ tham gia × KL TB 20 phiên)⌉; ngày có tiền = số phiên bán + 2.\n"
        "- **Kịch bản giảm sàn:** áp biên độ sàn liên tiếp 1 và 3 phiên, làm tròn theo bước giá."
    )
    st.subheader("Ngưỡng cảnh báo và cơ sở")
    st.dataframe(report.checks_frame()[["group", "name", "threshold", "source"]], hide_index=True, width="stretch",
                 column_config={"group": "Nhóm", "name": "Chỉ số", "threshold": "Ngưỡng", "source": "Cơ sở"})
    st.subheader("Giới hạn của sản phẩm")
    st.markdown(
        "- Dữ liệu theo **phiên** (cuối ngày), không phải thời gian thực từng giây.\n"
        "- Các chỉ số rủi ro dựa trên **quá khứ**; quá khứ không bảo đảm cho tương lai. VaR không cho biết mức lỗ trong "
        "5% phiên xấu nhất.\n"
        "- Giả định tỷ trọng cố định và tỷ lệ tham gia thanh khoản là đơn giản hóa; người dùng chỉnh được tỷ lệ tham gia.\n"
        "- Ngưỡng UCITS và SEC là **chuẩn tham chiếu** của quỹ đầu tư, không phải quy định bắt buộc với nhà đầu tư cá nhân; "
        "ngưỡng ngành 50% là quy tắc tự đặt.\n"
        "- Không tính thuế, phí giao dịch, cổ tức tiền mặt nhận được và lãi tiền gửi.\n"
        f"- {DISCLAIMER}"
    )
    st.subheader("Chất lượng và truy vết dữ liệu")
    st.dataframe(store_info["coverage"], hide_index=True, width="stretch",
                 column_config={"kind": "Loại", "symbol": "Mã", "sessions": "Số phiên", "first": "Từ ngày",
                                "last": "Đến ngày"})
    log = store_info["fetch_log"]
    if not log.empty:
        st.caption("Nhật ký cập nhật gần nhất (mỗi dòng là một lần tải một mã từ SSI):")
        st.dataframe(log[["started_at", "symbol", "mode", "rows_kept", "missing_sessions", "status", "message"]],
                     hide_index=True, width="stretch",
                     column_config={"started_at": "Thời điểm", "symbol": "Mã", "mode": "Cách tải",
                                    "rows_kept": "Số phiên", "missing_sessions": "Phiên thiếu",
                                    "status": "Trạng thái", "message": "Ghi chú"})
