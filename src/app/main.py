"""
Ứng dụng Streamlit "Khám Sức Khỏe Danh Mục".

Cách chạy (trong thư mục gốc của repo, đã kích hoạt .venv):
    streamlit run src/app/main.py

Cấu trúc giống một trang web: thanh bên trái là menu điều hướng giữa các trang (nội dung từng trang ở
src/app/views.py), bên dưới menu là khung "Dữ liệu" cho biết nguồn, phiên mới nhất, trạng thái kết nối
và hai nút Kiểm tra kết nối / Cập nhật dữ liệu.

Nguồn dữ liệu được chọn tự động, luôn là dữ liệu thật từ SSI FastConnect API:
    - máy đã có kho data/portfolio.db  -> đọc kho này; có API key thì tự tải phiên mới khi mở ứng dụng;
    - máy chưa có kho (vd máy người chấm, không có API key) -> đọc bản dữ liệu SSI lưu kèm mã nguồn
      data_sample/sample.db và ghi rõ phiên chốt dữ liệu.

Ứng dụng chỉ đọc dữ liệu thị trường; không đặt lệnh, không đọc tài khoản chứng khoán.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # để import được src.*

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src import config  # noqa: E402
from src.app import style, views  # noqa: E402
from src.app.ui import ICONS, expected_latest_session, format_date, format_time, is_up_to_date  # noqa: E402
from src.data.storage import Storage  # noqa: E402
from src.data.updater import DataUpdater  # noqa: E402
from src.finance.health import build_health_report  # noqa: E402
from src.finance.market_data import MarketData, load_market_data  # noqa: E402
from src.finance.portfolio import CASH_SYMBOL, PortfolioError, build_portfolio  # noqa: E402
from src.ssi_api.client import SSIClient, SSIError  # noqa: E402

ASSETS = Path(__file__).resolve().parent / "assets"
st.set_page_config(page_title=config.APP_NAME, page_icon=str(ASSETS / "logo_icon.svg"), layout="wide")
st.logo(str(ASSETS / "logo.svg"), size="large", icon_image=str(ASSETS / "logo_icon.svg"))
style.inject_css()
logger = logging.getLogger("app")


# ====================================================================== đọc dữ liệu (có cache)

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
            "market_summary": storage.load_market_summary("HOSE").tail(config.MARKET_SUMMARY_SESSIONS),
        }


@st.cache_resource
def auto_update_attempts() -> set[str]:
    """Các phiên đã tự cập nhật trong lần chạy máy chủ này (dùng chung mọi người xem) - mỗi phiên tối đa 1 lần."""
    return set()


def default_portfolio_rows() -> tuple[pd.DataFrame, float]:
    """Danh mục mặc định khi mở ứng dụng (đọc từ data_sample/demo_portfolio.csv)."""
    try:
        rows = pd.read_csv(config.DEMO_PORTFOLIO_PATH, dtype={"symbol": str})
    except FileNotFoundError:
        rows = pd.DataFrame({"symbol": config.DEFAULT_SYMBOLS, "quantity": [1000] * 6, "avg_cost": [None] * 6})
    is_cash = rows["symbol"].str.upper() == CASH_SYMBOL
    cash = float(rows.loc[is_cash, "quantity"].sum())
    return rows.loc[~is_cash, ["symbol", "quantity", "avg_cost"]].reset_index(drop=True), cash


def api_key_available() -> bool:
    """Máy có API key SSI trong .env hay không (chỉ đọc file, không gọi mạng)."""
    try:
        SSIClient.from_env()
        return True
    except SSIError:
        return False


def now_vn() -> datetime:
    return datetime.now(config.VN_TZ)


# ====================================================================== thao tác với SSI

def check_ssi_connection() -> None:
    try:
        SSIClient.from_env().check_connection()
        st.session_state.ssi_status = ("ok", now_vn().strftime("%H:%M %d/%m"))
    except SSIError as exc:
        st.session_state.ssi_status = ("error", str(exc))


def run_update(symbols: list[str], reason: str = "") -> None:
    """Cập nhật kho data/portfolio.db từ SSI cho các mã trong danh mục (chỉ tải phần mới)."""
    try:
        client = SSIClient.from_env()
    except SSIError as exc:
        st.session_state.ssi_status = ("error", str(exc))
        return
    try:
        with st.spinner(f"{reason}Đang tải dữ liệu từ SSI (mỗi yêu cầu khoảng 1 giây)..."):
            with Storage(config.DB_PATH) as storage:
                client.raw_hook = storage.save_raw
                results = DataUpdater(client, storage).run(symbols)
    except Exception as exc:  # lỗi ngoài dự kiến: báo rõ, không để ứng dụng dừng (vẫn dùng dữ liệu đã lưu)
        logger.exception("Cập nhật dữ liệu thất bại")
        st.session_state.ssi_status = ("error", f"lỗi khi cập nhật ({type(exc).__name__}: {exc})")
        return
    failed = [r for r in results if r.status != "ok"]
    if failed and len(failed) == len(results):
        st.session_state.ssi_status = ("error", failed[0].message)
        return
    st.session_state.ssi_status = ("ok", now_vn().strftime("%H:%M %d/%m"))
    if failed:
        detail = "; ".join(f"{r.symbol}: {r.message}" for r in failed)
        st.session_state.update_message = ("warning", f"Cập nhật xong nhưng có {len(failed)} chuỗi lỗi: {detail}")
    else:
        st.session_state.update_message = ("success", f"{reason}Đã cập nhật {len(results)} chuỗi dữ liệu với "
                                                      f"{client.request_count} yêu cầu tới SSI.")
    cached_market_data.clear()
    cached_store_info.clear()


# ====================================================================== danh mục trong phiên làm việc

state = st.session_state
if "portfolio_rows" not in state:
    state.portfolio_rows, state.cash = default_portfolio_rows()
    state.editor_version = 0
    state.ssi_status = ("unknown", "")
    state.participation_pct = 20
    state.period = "1 năm"


def save_portfolio(rows: pd.DataFrame, cash: float) -> None:
    """Lưu danh mục người dùng vừa nhập (bảng trên trang Nhập danh mục hoặc file CSV)."""
    rows = rows.dropna(how="all")
    try:
        parsed = build_portfolio(pd.concat([rows, pd.DataFrame({"symbol": [CASH_SYMBOL], "quantity": [cash]})],
                                           ignore_index=True).dropna(subset=["symbol"]))
    except PortfolioError as exc:
        st.error(f"Chưa lưu được danh mục: {exc}")
        return
    state.portfolio_rows, state.cash = parsed.holdings, parsed.cash
    state.editor_version += 1
    st.rerun()


def reset_portfolio() -> None:
    state.portfolio_rows, state.cash = default_portfolio_rows()
    state.editor_version += 1
    state.pop("uploaded_name", None)
    st.rerun()


# ====================================================================== tính toán dùng chung cho mọi trang

def build_context() -> views.AppContext:
    has_key = api_key_available()
    ctx = views.AppContext(live=config.DB_PATH.exists(), has_key=has_key, up_to_date=False,
                           save_portfolio=save_portfolio, reset_portfolio=reset_portfolio)
    try:
        rows = pd.concat([state.portfolio_rows, pd.DataFrame({"symbol": [CASH_SYMBOL], "quantity": [state.cash]})],
                         ignore_index=True)
        ctx.portfolio = build_portfolio(rows.dropna(subset=["symbol"]))
    except PortfolioError as exc:
        ctx.portfolio_error = str(exc)
    symbols = ctx.portfolio.symbols if ctx.portfolio else config.DEFAULT_SYMBOLS

    # Tự tải phiên mới khi mở ứng dụng: có API key, có kho trên máy, dữ liệu chưa mới, phiên này chưa thử
    if ctx.live and has_key and config.AUTO_UPDATE_ON_OPEN:
        mtime = config.DB_PATH.stat().st_mtime
        last_fetched = cached_market_data(str(config.DB_PATH), mtime, tuple(symbols)).last_fetched_at
        session = expected_latest_session(now_vn()).isoformat()
        attempts = auto_update_attempts()
        if not is_up_to_date(last_fetched, now_vn()) and session not in attempts:
            attempts.add(session)
            run_update(symbols, reason="Có phiên mới. ")

    db_path = config.DB_PATH if ctx.live else config.SAMPLE_DB_PATH
    if not db_path.exists():
        ctx.data_error = ("Chưa có dữ liệu trên máy này. Thêm API key SSI vào file .env (xem .env.example) rồi bấm "
                          "**Cập nhật dữ liệu** ở thanh bên, hoặc chạy `python scripts/export_sample.py` trên máy đã "
                          "có dữ liệu.")
        return ctx
    mtime = db_path.stat().st_mtime
    ctx.market = cached_market_data(str(db_path), mtime, tuple(symbols))
    ctx.store_info = cached_store_info(str(db_path), mtime)
    ctx.up_to_date = ctx.live and is_up_to_date(ctx.market.last_fetched_at, now_vn())
    if ctx.portfolio is None:
        return ctx
    if ctx.market.index_close.empty or len(ctx.market.missing_symbols) == len(ctx.portfolio.symbols):
        ctx.data_error = "Không đủ dữ liệu để phân tích danh mục này (chưa có giá của các mã hoặc của VN-Index)."
        return ctx
    ctx.report = build_health_report(ctx.portfolio, ctx.market, participation=state.participation_pct / 100)
    return ctx


ctx = build_context()


# ====================================================================== các trang và menu điều hướng

def _page(render, title: str, key: str, url: str, default: bool = False) -> st.Page:
    def run() -> None:
        render(ctx)
    return st.Page(run, title=title, icon=ICONS[key], url_path=url, default=default)


ctx.pages = {
    "home": _page(views.home, "Trang chủ", "home", "trang-chu", default=True),
    "overview": _page(views.overview, "Tổng quan", "overview", "tong-quan"),
    "portfolio": _page(views.portfolio_input, "Nhập danh mục", "portfolio", "nhap-danh-muc"),
    "alerts": _page(views.alerts, "Cảnh báo", "alerts", "canh-bao"),
    "allocation": _page(views.allocation, "Phân bổ", "allocation", "phan-bo"),
    "risk": _page(views.risk, "Rủi ro", "risk", "rui-ro"),
    "liquidity": _page(views.liquidity, "Thanh khoản & giảm sàn", "liquidity", "thanh-khoan"),
    "market": _page(views.market, "Thị trường", "market", "thi-truong"),
    "method": _page(views.method, "Phương pháp & dữ liệu", "method", "phuong-phap"),
}
p = ctx.pages
navigation = st.navigation({
    "Bắt đầu": [p["home"], p["portfolio"]],
    "Kết quả kiểm tra": [p["overview"], p["alerts"], p["allocation"], p["risk"], p["liquidity"]],
    "Thị trường & dữ liệu": [p["market"], p["method"]],
})


# ====================================================================== khung "Dữ liệu" ở thanh bên

def data_panel() -> None:
    market, (status_kind, status_text) = ctx.market, state.ssi_status
    last_session = format_date(market.last_trading_date) if market else "chưa có"
    st.markdown("**Dữ liệu**")
    if ctx.live:
        st.markdown(f":blue-badge[{ICONS['source']} SSI FastConnect API]")
        if ctx.up_to_date:
            st.markdown(f":green-badge[{ICONS['session']} Phiên {last_session} · mới nhất]")
        else:
            st.markdown(f":orange-badge[{ICONS['session']} Phiên {last_session} · có thể đã có phiên mới]")
    elif market:
        st.markdown(f":gray-badge[{ICONS['source']} Bản lưu kèm mã nguồn (SSI)]")
        st.markdown(f":gray-badge[{ICONS['session']} Chốt đến phiên {last_session}]")
    else:
        st.markdown(f":red-badge[{ICONS['source']} Chưa có dữ liệu trên máy này]")
    if market:
        st.caption(f"Tải từ SSI lúc {format_time(market.last_fetched_at)} (giờ Việt Nam)")

    if status_kind == "ok":
        st.markdown(f":green-badge[{ICONS['connection']} Kết nối SSI tốt · {status_text}]")
    elif status_kind == "error":
        st.markdown(f":red-badge[{ICONS['connection']} Lỗi kết nối SSI]")
    elif ctx.has_key:
        st.markdown(f":gray-badge[{ICONS['connection']} Chưa kiểm tra kết nối]")
    else:
        st.markdown(f":gray-badge[{ICONS['connection']} Máy này chưa có API key SSI]")

    if st.button("Kiểm tra kết nối", icon=ICONS["check"], width="stretch"):
        check_ssi_connection()
        st.rerun()
    if st.button("Cập nhật dữ liệu", icon=ICONS["update"], type="primary", width="stretch"):
        run_update(ctx.portfolio.symbols if ctx.portfolio else config.DEFAULT_SYMBOLS)
        st.rerun()


with st.sidebar:
    data_panel()

# Dải giá chạy ngang ở đầu mọi trang: VN-Index và các mã trong danh mục, phiên mới nhất trong kho
def ticker_items() -> list[tuple[str, float, float]]:
    market = ctx.market
    if market is None or market.index_close.empty:
        return []
    index = market.index_close
    items = [("VN-Index", float(index.iloc[-1]),
              float(index.iloc[-1] / index.iloc[-2] - 1) if len(index) >= 2 else float("nan"))]
    if not market.latest.empty:
        for symbol, row in market.latest.iterrows():
            close = pd.to_numeric(row.get("close"), errors="coerce")
            if pd.isna(close):
                continue
            change = pd.to_numeric(row.get("price_change_pct"), errors="coerce") / 100
            if pd.isna(change) and symbol in market.close.columns:  # thiếu % thay đổi: tính từ 2 phiên gần nhất
                series = market.close[symbol].dropna()
                change = series.iloc[-1] / series.iloc[-2] - 1 if len(series) >= 2 else float("nan")
            items.append((str(symbol), float(close), float(change)))
    return items


items = ticker_items()
if items:
    st.html(style.ticker_html(items, f"Phiên {format_date(ctx.market.last_trading_date)}"))

# Thông báo chung (hiện ở đầu mọi trang)
if "update_message" in state:
    kind, message = state.pop("update_message")
    getattr(st, kind)(message)
if state.ssi_status[0] == "error":
    st.error(f"Không kết nối được SSI: {state.ssi_status[1]}. Ứng dụng tiếp tục dùng dữ liệu đã lưu.",
             icon=":material/cloud_off:")

navigation.run()
