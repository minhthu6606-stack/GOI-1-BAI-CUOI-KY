"""
Ứng dụng Streamlit "Vốn Ổn" - khám sức khỏe danh mục cổ phiếu ("Khám vốn mỗi phiên, đầu tư an yên.").

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
from src.data.quality import collection_summary, quality_table  # noqa: E402
from src.data.storage import Storage  # noqa: E402
from src.data.updater import DataUpdater  # noqa: E402
from src.finance.examples import DEFAULT_EXAMPLE, build_example, example_symbols  # noqa: E402
from src.finance.health import RiskProfile, build_health_report  # noqa: E402
from src.finance.market_data import MarketData, load_market_data  # noqa: E402
from src.finance.portfolio import CASH_SYMBOL, PortfolioError, build_portfolio  # noqa: E402
from src.ssi_api.client import SSIClient, SSIError  # noqa: E402

ASSETS = Path(__file__).resolve().parent / "assets"
st.set_page_config(page_title=f"{config.APP_NAME} · {config.APP_DESCRIPTOR}", page_icon=str(ASSETS / "logo_icon.svg"), layout="wide")
DARK = bool(st.session_state.get("dark_mode", False))   # chọn ở mục "Cài đặt" cuối thanh bên; mặc định: sáng
st.logo(str(ASSETS / ("logo_dark.svg" if DARK else "logo_light.svg")), size="large",
        icon_image=str(ASSETS / "logo_icon.svg"))
st.html(style.theme_css(DARK))
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
        coverage = storage.coverage()
        full_log = storage.load_fetch_log(limit=100_000)
        stocks = coverage.loc[coverage["kind"] == "stock", "symbol"].tolist() if not coverage.empty else []
        return {
            "coverage": coverage,
            "fetch_log": full_log.head(30),
            "collection": collection_summary(full_log, storage.trading_calendar(config.MARKET_INDEX)),
            "quality": quality_table(storage, stocks) if stocks else pd.DataFrame(),
            "market_summary": storage.load_market_summary("HOSE").tail(config.MARKET_SUMMARY_SESSIONS),
        }


@st.cache_data(show_spinner=False)
def cached_ticker_quotes(db_path: str, db_mtime: float, symbols: tuple[str, ...]) -> list[tuple[str, float, float]]:
    """Giá đóng cửa phiên mới nhất và % thay đổi so với phiên trước của các mã trên dải giá chạy ngang."""
    quotes = []
    with Storage(db_path) as storage:
        for symbol in symbols:
            frame = storage.load_daily("stock_daily", symbol).tail(2)
            if frame.empty or pd.isna(frame["close"].iloc[-1]):
                continue
            change = pd.to_numeric(frame["price_change_pct"].iloc[-1], errors="coerce") / 100
            if pd.isna(change) and len(frame) == 2:  # thiếu % thay đổi: tính từ 2 phiên gần nhất
                change = frame["close"].iloc[-1] / frame["close"].iloc[-2] - 1
            quotes.append((symbol, float(frame["close"].iloc[-1]), float(change)))
    return quotes


@st.cache_resource
def auto_update_attempts() -> set[str]:
    """Các phiên đã tự cập nhật trong lần chạy máy chủ này (dùng chung mọi người xem) - mỗi phiên tối đa 1 lần."""
    return set()


@st.cache_data(show_spinner=False)
def cached_latest_prices(db_path: str, db_mtime: float) -> pd.Series:
    """Giá đóng cửa phiên mới nhất của MỌI mã trong kho (để xem trước giá trị khi nhập và tạo danh mục ví dụ)."""
    with Storage(db_path) as storage:
        frame = pd.read_sql_query(
            "SELECT s.symbol, s.close FROM stock_daily s JOIN (SELECT symbol, MAX(trading_date) AS d FROM stock_daily "
            "GROUP BY symbol) m ON s.symbol = m.symbol AND s.trading_date = m.d", storage.conn)
    return frame.set_index("symbol")["close"].astype(float)


@st.cache_data(show_spinner=False)
def cached_symbol_names(db_path: str, db_mtime: float) -> dict[str, str]:
    """Mã -> tên công ty, từ danh sách chứng khoán SSI trong kho (dùng cho ô chọn mã)."""
    with Storage(db_path) as storage:
        securities = storage.load_securities()
    if securities.empty:
        return {}
    return dict(zip(securities["symbol"], securities["name_vi"].fillna("")))


def current_db_path() -> Path:
    return config.DB_PATH if config.DB_PATH.exists() else config.SAMPLE_DB_PATH


def latest_prices() -> pd.Series:
    path = current_db_path()
    return cached_latest_prices(str(path), path.stat().st_mtime) if path.exists() else pd.Series(dtype=float)


def example_rows(key: str) -> tuple[pd.DataFrame, float]:
    """Danh mục ví dụ tính theo giá mới nhất trong kho; không có kho thì đọc file CSV dự phòng."""
    prices = latest_prices()
    if not prices.empty:
        rows, cash = build_example(key, prices)
        if not rows.empty:
            return rows, cash
    rows = pd.read_csv(config.DEMO_PORTFOLIO_PATH, dtype={"symbol": str})
    is_cash = rows["symbol"].str.upper() == CASH_SYMBOL
    return rows.loc[~is_cash, ["symbol", "quantity", "avg_cost"]].reset_index(drop=True), \
        float(rows.loc[is_cash, "quantity"].sum())


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


def update_symbols(portfolio_symbols: list[str]) -> list[str]:
    """Các mã cần cập nhật: mã trong danh mục + các mã của danh mục ví dụ và dải giá chạy ngang."""
    return list(dict.fromkeys(portfolio_symbols + config.TRACKED_SYMBOLS + example_symbols()))


def run_update(symbols: list[str], reason: str = "") -> None:
    """Cập nhật kho data/portfolio.db từ SSI (chỉ tải phần mới; mã chưa có thì tải đủ lịch sử)."""
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
    state.portfolio_rows, state.cash = example_rows(DEFAULT_EXAMPLE)
    state.active_example = DEFAULT_EXAMPLE
    state.editor_version = 0
    state.ssi_status = ("unknown", "")
    state.participation_pct = 20
    state.period = "1 năm"
    state.profile_on, state.max_daily_loss, state.max_drawdown = False, 3.0, 20   # mức chịu lỗ tự khai: mặc định tắt


def save_portfolio(rows: pd.DataFrame, cash: float, example: str | None = None, go: bool = False) -> None:
    """Lưu danh mục (trang Nhập danh mục, file CSV hoặc trang Thử điều chỉnh). `example`: khóa danh mục ví dụ."""
    rows = rows.dropna(how="all")
    try:
        parsed = build_portfolio(pd.concat([rows, pd.DataFrame({"symbol": [CASH_SYMBOL], "quantity": [cash]})],
                                           ignore_index=True).dropna(subset=["symbol"]))
    except PortfolioError as exc:
        st.error(f"Chưa lưu được danh mục: {exc}")
        return
    state.portfolio_rows, state.cash = parsed.holdings, parsed.cash
    state.active_example = example
    state.editor_version += 1
    state.flash = "Đã lưu danh mục. Các trang kết quả đã tính lại theo danh mục mới."
    state.go_overview = go          # True: chuyển sang trang Tổng quan sau khi lưu
    st.rerun()


def load_example(key: str) -> None:
    rows, cash = example_rows(key)
    save_portfolio(rows, cash, example=key)


def reset_portfolio() -> None:
    load_example(DEFAULT_EXAMPLE)


# ====================================================================== tính toán dùng chung cho mọi trang

def build_context() -> views.AppContext:
    has_key = api_key_available()
    ctx = views.AppContext(live=config.DB_PATH.exists(), has_key=has_key, up_to_date=False, dark=DARK,
                           save_portfolio=save_portfolio, reset_portfolio=reset_portfolio, load_example=load_example,
                           active_example=state.active_example, participation=state.participation_pct / 100)
    if state.profile_on:
        ctx.profile = RiskProfile(max_daily_loss=state.max_daily_loss / 100, max_drawdown=state.max_drawdown / 100)
    try:
        rows = pd.concat([state.portfolio_rows, pd.DataFrame({"symbol": [CASH_SYMBOL], "quantity": [state.cash]})],
                         ignore_index=True)
        ctx.portfolio = build_portfolio(rows.dropna(subset=["symbol"]))
    except PortfolioError as exc:
        ctx.portfolio_error = str(exc)
    symbols = ctx.portfolio.symbols if ctx.portfolio else example_symbols()

    # Tự tải phiên mới khi mở ứng dụng: có API key, có kho trên máy, dữ liệu chưa mới, phiên này chưa thử
    if ctx.live and has_key and config.AUTO_UPDATE_ON_OPEN:
        mtime = config.DB_PATH.stat().st_mtime
        last_fetched = cached_market_data(str(config.DB_PATH), mtime, tuple(symbols)).last_fetched_at
        session = expected_latest_session(now_vn()).isoformat()
        attempts = auto_update_attempts()
        if not is_up_to_date(last_fetched, now_vn()) and session not in attempts:
            attempts.add(session)
            run_update(update_symbols(symbols), reason="Có phiên mới. ")

    db_path = config.DB_PATH if ctx.live else config.SAMPLE_DB_PATH
    if not db_path.exists():
        ctx.data_error = ("Chưa có dữ liệu trên máy này. Thêm API key SSI vào file .env (xem .env.example) rồi bấm "
                          "**Cập nhật dữ liệu** ở thanh bên, hoặc chạy `python scripts/export_sample.py` trên máy đã "
                          "có dữ liệu.")
        return ctx
    mtime = db_path.stat().st_mtime
    ctx.market = cached_market_data(str(db_path), mtime, tuple(symbols))
    ctx.store_info = cached_store_info(str(db_path), mtime)
    ctx.latest_prices = cached_latest_prices(str(db_path), mtime)
    ctx.symbol_names = cached_symbol_names(str(db_path), mtime)
    ctx.up_to_date = ctx.live and is_up_to_date(ctx.market.last_fetched_at, now_vn())
    if ctx.portfolio is None:
        return ctx
    if ctx.market.index_close.empty or len(ctx.market.missing_symbols) == len(ctx.portfolio.symbols):
        ctx.data_error = "Không đủ dữ liệu để phân tích danh mục này (chưa có giá của các mã hoặc của VN-Index)."
        return ctx
    ctx.report = build_health_report(ctx.portfolio, ctx.market, participation=ctx.participation, profile=ctx.profile)
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
    "whatif": _page(views.whatif, "Thử điều chỉnh", "whatif", "thu-dieu-chinh"),
    "alerts": _page(views.alerts, "Cảnh báo", "alerts", "canh-bao"),
    "allocation": _page(views.allocation, "Phân bổ", "allocation", "phan-bo"),
    "risk": _page(views.risk, "Rủi ro", "risk", "rui-ro"),
    "liquidity": _page(views.liquidity, "Thanh khoản & giảm sàn", "liquidity", "thanh-khoan"),
    "market": _page(views.market, "Thị trường", "market", "thi-truong"),
    "method": _page(views.method, "Phương pháp & dữ liệu", "method", "phuong-phap"),
}
p = ctx.pages
navigation = st.navigation({   # nhóm menu theo quy trình 3 bước
    "": [p["home"]],
    "1 · Hồ sơ danh mục": [p["portfolio"]],
    "2 · Xem kết quả": [p["overview"], p["alerts"], p["allocation"], p["risk"], p["liquidity"]],
    "3 · Phương án cải thiện": [p["whatif"]],
    "Tham khảo": [p["market"], p["method"]],
})
current_key = next((k for k, page in p.items() if page.title == navigation.title), "home")
if state.pop("go_overview", False):
    st.switch_page(p["overview"])


# ====================================================================== khung "Dữ liệu" ở thanh bên

def data_panel() -> None:
    """Khung "Dữ liệu" gọn: nguồn, phiên mới nhất, kết nối (chấm màu) + 2 nút; mục "Cài đặt" chọn sáng/tối."""
    market, (status_kind, status_text) = ctx.market, state.ssi_status
    last_session = format_date(market.last_trading_date) if market else "chưa có"
    if not market:
        rows = [("red", "Chưa có dữ liệu trên máy này")]
    elif ctx.live:
        rows = [("violet", "SSI FastConnect API"),
                ("green", f"Phiên {last_session} · mới nhất") if ctx.up_to_date
                else ("orange", f"Phiên {last_session} · có thể có phiên mới")]
    else:
        rows = [("violet", "Bản dữ liệu SSI lưu kèm mã nguồn"), ("gray", f"Chốt đến phiên {last_session}")]
    if status_kind == "ok":
        rows.append(("green", f"Kết nối SSI tốt · {status_text}"))
    elif status_kind == "error":
        rows.append(("red", "Lỗi kết nối SSI (xem thông báo)"))
    elif ctx.has_key:
        rows.append(("gray", "Chưa kiểm tra kết nối"))
    else:
        rows.append(("gray", "Máy này chưa có API key SSI"))
    note = f"Tải từ SSI lúc {format_time(market.last_fetched_at)} (giờ VN)" if market else "Chưa tải lần nào"
    st.html(style.data_panel_html(rows, note))

    col_a, col_b = st.columns(2)
    if col_a.button("Kiểm tra", icon=ICONS["check"], width="stretch", help="Kiểm tra kết nối tới SSI"):
        check_ssi_connection()
        st.rerun()
    if col_b.button("Cập nhật", icon=ICONS["update"], type="primary", width="stretch",
                    help="Tải phiên mới nhất từ SSI (cần API key)"):
        run_update(update_symbols(ctx.portfolio.symbols if ctx.portfolio else []))
        st.rerun()

    st.markdown("**Cài đặt**")
    st.toggle("Giao diện tối", key="dark_mode", help="Mặc định là giao diện sáng; lựa chọn giữ nguyên khi chuyển trang.")
    st.html(style.theme_sync_script(DARK), unsafe_allow_javascript=True)


with st.sidebar:
    data_panel()

# Dải giá chạy ngang ở đầu mọi trang: VN-Index và các mã trong danh mục, phiên mới nhất trong kho
def ticker_items() -> list[tuple[str, float, float]]:
    """VN-Index, các mã trong danh mục, rồi các mã vốn hóa lớn (TICKER_SYMBOLS) - đúng số liệu phiên mới nhất."""
    market = ctx.market
    if market is None or market.index_close.empty:
        return []
    index = market.index_close
    items = [("VN-Index", float(index.iloc[-1]),
              float(index.iloc[-1] / index.iloc[-2] - 1) if len(index) >= 2 else float("nan"))]
    db_path = config.DB_PATH if ctx.live else config.SAMPLE_DB_PATH
    symbols = list(dict.fromkeys((ctx.portfolio.symbols if ctx.portfolio else []) + config.TICKER_SYMBOLS))
    items += cached_ticker_quotes(str(db_path), db_path.stat().st_mtime, tuple(symbols))
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
views.page_footer(ctx, current_key)   # nút Trước/Tiếp ở cuối mọi trang
