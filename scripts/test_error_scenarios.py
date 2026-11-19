"""
Thử các tình huống lỗi THẬT (có gọi mạng) và ghi kết quả ra docs/kiem_chung/thu_loi.md để đưa vào Mục 7.

Các tình huống:
    1. Thiếu API key trong .env                 -> báo lỗi rõ ràng, không gọi mạng
    2. API key sai                              -> SSI từ chối, báo "Xác thực thất bại"
    3. Không tới được máy chủ (mất mạng)        -> báo "Không kết nối được máy chủ SSI"
    4. Mã chứng khoán không tồn tại             -> SSI trả rỗng / lỗi, không làm dừng chương trình
    5. Giới hạn tần suất                        -> đo khoảng cách thực tế giữa các yêu cầu (≥ 1,1 giây)
    6. Danh mục nhập sai                        -> báo lỗi tiếng Việt, không tính toán
    7. Dữ liệu bẩn (trùng, thiếu, giá ≤ 0)      -> bị loại, có thống kê
    8. Nghỉ nhiều phiên rồi mới mở lại (vd ngày thi) -> lần sau tự tải bù, không thiếu phiên, không trùng dòng
    9. Dữ liệu đến muộn (tải trong giờ giao dịch)    -> giá tạm trong phiên được thay bằng giá đóng cửa ở lần sau

Tình huống 4–5 cần API key thật trong .env (nếu không có thì ghi "bỏ qua"). Tình huống 8–9 là mô phỏng ngoại tuyến:
dùng một client giả trả dữ liệu theo lịch ngày làm việc và một kho SQLite tạm, để thử đúng quy trình cập nhật thật
(DataUpdater) mà không phải chờ nhiều ngày; số liệu của hai tình huống này KHÔNG phải dữ liệu thị trường.
Script KHÔNG ghi gì vào kho dữ liệu thật và KHÔNG in key ra màn hình.

Cách chạy:
    python scripts/test_error_scenarios.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src import config  # noqa: E402
from src.data.normalize import find_missing_sessions, normalize_stock_daily  # noqa: E402
from src.data.sessions import expected_latest_session, is_up_to_date  # noqa: E402
from src.data.storage import Storage  # noqa: E402
from src.data.updater import DataUpdater  # noqa: E402
from src.finance.portfolio import PortfolioError, build_portfolio  # noqa: E402
from src.ssi_api.client import SSIClient, SSIError  # noqa: E402

OUT_FILE = config.PROJECT_ROOT / "docs" / "kiem_chung" / "thu_loi.md"
RESULTS: list[dict[str, str]] = []


def record(case: str, how: str, expected: str, actual: str, passed: bool | None) -> None:
    status = "Đạt" if passed else ("Bỏ qua" if passed is None else "KHÔNG ĐẠT")
    RESULTS.append({"Tình huống": case, "Cách thử": how, "Kết quả mong đợi": expected,
                    "Kết quả thực tế": actual.replace("|", "/").replace("\n", " ")[:160], "Đánh giá": status})
    print(f"[{status}] {case}: {actual[:120]}")


def real_client() -> SSIClient | None:
    try:
        return SSIClient.from_env()
    except SSIError:
        return None


def case_missing_key() -> None:
    saved = {k: os.environ.get(k) for k in ("SSI_API_KEY", "SSI_API_SECRET")}
    os.environ["SSI_API_KEY"], os.environ["SSI_API_SECRET"] = "", ""   # load_dotenv không ghi đè biến đã có
    try:
        SSIClient.from_env()
        record("Thiếu API key", "Để trống SSI_API_KEY/SSI_API_SECRET", "Báo lỗi, không gọi mạng",
               "Không báo lỗi", False)
    except SSIError as exc:
        record("Thiếu API key", "Để trống SSI_API_KEY/SSI_API_SECRET", "Báo lỗi, không gọi mạng", str(exc), True)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def case_wrong_key() -> None:
    client = SSIClient("khoa-thu-sai", "bi-mat-thu-sai")
    try:
        client.check_connection()
        record("API key sai", "Dùng key giả", "SSI từ chối xác thực", "SSI vẫn cấp token (bất thường)", False)
    except SSIError as exc:
        message = str(exc)
        if "Không kết nối được" in message:   # không có mạng thì chưa thử được tình huống này
            record("API key sai", "Dùng key giả", "SSI từ chối xác thực", f"Không có mạng: {message}", None)
        else:
            record("API key sai", "Dùng key giả", "SSI từ chối xác thực", message, True)


def case_unreachable() -> None:
    client = SSIClient("khoa", "bi-mat", base_url="https://may-chu-khong-ton-tai.invalid/api/v3")
    started = time.perf_counter()
    try:
        client.check_connection()
        record("Mất kết nối", "Trỏ tới máy chủ không tồn tại", "Báo không kết nối được", "Không báo lỗi", False)
    except SSIError as exc:
        elapsed = time.perf_counter() - started
        record("Mất kết nối", "Trỏ tới máy chủ không tồn tại", "Báo không kết nối được, không treo",
               f"{str(exc)[:90]}... (sau {elapsed:.1f} giây)", True)


def case_unknown_symbol(client: SSIClient | None) -> None:
    how = "Hỏi giá 10 ngày của mã ZZZ9 (không tồn tại)"
    if client is None:
        record("Mã không tồn tại", how, "Trả rỗng hoặc báo lỗi, không dừng", "Không có API key", None)
        return
    today = datetime.now(config.VN_TZ).date()
    try:
        records = client.get_stock_daily("ZZZ9", today - timedelta(days=10), today)
        frame, _ = normalize_stock_daily(records, "ZZZ9")
        record("Mã không tồn tại", how, "Trả rỗng hoặc báo lỗi, không dừng",
               f"SSI trả {len(records)} bản ghi, giữ lại {len(frame)} -> ứng dụng ghi 'Không có dữ liệu'", len(frame) == 0)
    except SSIError as exc:
        record("Mã không tồn tại", how, "Trả rỗng hoặc báo lỗi, không dừng", f"Báo lỗi: {exc}", True)


def case_rate_limit(client: SSIClient | None) -> None:
    how = "Gửi liên tiếp 4 yêu cầu tổng hợp thị trường, đo khoảng cách"
    if client is None:
        record("Giới hạn tần suất", how, "Mỗi yêu cầu cách nhau ≥ 1,100 giây", "Không có API key", None)
        return
    times = []
    original = client._wait_for_rate_limit

    def timed_wait() -> None:
        original()
        times.append(time.perf_counter())

    client._wait_for_rate_limit = timed_wait  # ghi lại thời điểm gửi từng yêu cầu
    try:
        for _ in range(4):
            client.get_market_summary("HOSE")
    except SSIError as exc:
        record("Giới hạn tần suất", how, "Mỗi yêu cầu cách nhau ≥ 1,100 giây", f"Lỗi khi gọi: {exc}", False)
        return
    gaps = [b - a for a, b in zip(times, times[1:])]
    smallest = min(gaps) if gaps else float("nan")
    record("Giới hạn tần suất", how, "Mỗi yêu cầu cách nhau ≥ 1,100 giây",
           f"{len(times)} yêu cầu, khoảng cách nhỏ nhất {smallest:.3f} giây", smallest >= config.SSI_MIN_INTERVAL_SECONDS)


def case_bad_portfolio() -> None:
    bad = pd.DataFrame({"symbol": ["FPT", "AB!"], "quantity": [-100, 100], "avg_cost": [50000, 10000]})
    try:
        build_portfolio(bad)
        record("Danh mục nhập sai", "Số lượng âm và mã sai định dạng", "Báo lỗi, không tính toán", "Không báo lỗi", False)
    except PortfolioError as exc:
        record("Danh mục nhập sai", "Số lượng âm và mã sai định dạng", "Báo lỗi, không tính toán", str(exc), True)


def case_dirty_data() -> None:
    rows = [
        {"tradingDate": "2026/11/17", "close": "50000", "priceChangePercentage": "1"},
        {"tradingDate": "2026/11/17", "close": "50100", "priceChangePercentage": "1.2"},   # trùng ngày
        {"tradingDate": "2026/11/18", "close": None},                                     # thiếu giá
        {"tradingDate": "2026/11/19", "close": "0"},                                      # giá ≤ 0
        {"tradingDate": "2026/11/20", "close": "51000", "priceChangePercentage": "1.8"},
    ]
    frame, report = normalize_stock_daily(rows, "TEST")
    actual = (f"Nhận {report.total}, giữ {report.kept}; loại trùng {report.dropped_duplicate}, thiếu "
              f"{report.dropped_missing}, giá ≤ 0 {report.dropped_invalid}")
    record("Dữ liệu bẩn", "5 bản ghi: 1 trùng ngày, 1 thiếu giá, 1 giá bằng 0", "Giữ 2, loại 3 và thống kê lý do",
           actual, report.kept == 2)


class SimulatedClient:
    """Client giả cho tình huống 8–9: trả dữ liệu cho mọi ngày làm việc trong khoảng được hỏi."""

    def __init__(self) -> None:
        self.prices: dict[date, float] = {}   # giá đóng cửa riêng cho một số ngày (mặc định 50.000)
        self.stock_calls = 0

    @staticmethod
    def _days(start: date, end: date) -> list[date]:
        return [start + timedelta(days=i) for i in range((end - start).days + 1)
                if (start + timedelta(days=i)).weekday() < 5]

    def get_index_daily(self, symbol, start, end):
        return [{"tradingDate": d.strftime("%Y/%m/%d"), "open": "1700", "high": "1710", "low": "1690",
                 "close": "1700", "volume": "1"} for d in self._days(start, end)]

    def get_stock_daily(self, symbol, start, end):
        self.stock_calls += 1
        rows = []
        for d in self._days(start, end):
            price = str(self.prices.get(d, 50000.0))
            rows.append({"tradingDate": d.strftime("%Y/%m/%d"), "open": price, "high": price, "low": price,
                         "close": price, "priceChangePercentage": "0", "totalMatch": "1000"})
        return rows

    def get_securities(self, board):
        return [{"symbol": "FPT", "board": board, "icbName": "Công nghệ"}]


def case_long_gap() -> None:
    how = "Mô phỏng: cập nhật thứ Hai 09/11, nghỉ 8 phiên (ngày thi), mở lại thứ Sáu 20/11"
    expected = "Một lần tải bù đủ các phiên còn thiếu; 0 phiên thiếu, 0 dòng trùng"
    client = SimulatedClient()
    with tempfile.TemporaryDirectory() as folder, Storage(Path(folder) / "thu.db") as storage:
        DataUpdater(client, storage, history_years=1, today=date(2026, 11, 9)).run(["FPT"], with_market_summary=False)
        before = storage.last_trading_date("stock_daily", "FPT")
        calls_before = client.stock_calls
        results = DataUpdater(client, storage, history_years=1, today=date(2026, 11, 20)).run(
            ["FPT"], with_market_summary=False)
        stock = next(r for r in results if r.symbol == "FPT")
        frame = storage.load_daily("stock_daily", "FPT")
        calendar = storage.trading_calendar(config.MARKET_INDEX)
        missing = len(find_missing_sessions(frame, calendar))
        duplicates = int(frame["trading_date"].duplicated().sum())
        added = int((frame["trading_date"] > before).sum())
    calls = client.stock_calls - calls_before
    actual = (f"Phiên cuối trước khi nghỉ {before}; lần mở lại tải {calls} yêu cầu, cách tải '{stock.mode}', thêm "
              f"{added} phiên mới (đến {frame['trading_date'].max()}); phiên thiếu {missing}, dòng trùng {duplicates}")
    record("Nghỉ nhiều phiên rồi mở lại", how, expected, actual,
           stock.mode == "incremental" and added == 9 and missing == 0 and duplicates == 0)


def case_late_data() -> None:
    how = "Mô phỏng: tải lúc 10:00 ngày 19/11 (giá tạm 50.500), tải lại sau 15:00 (giá đóng cửa 51.000)"
    expected = "Trước 15:00 không coi phiên 19/11 là đã chốt; lần tải sau thay giá tạm, không tải lại toàn bộ"
    tz = config.VN_TZ
    morning = datetime(2026, 11, 19, 10, 0, tzinfo=tz)
    afternoon = datetime(2026, 11, 19, 15, 30, tzinfo=tz)
    session_morning = expected_latest_session(morning)
    needs_update = not is_up_to_date(morning.isoformat(), afternoon)
    client = SimulatedClient()
    with tempfile.TemporaryDirectory() as folder, Storage(Path(folder) / "thu.db") as storage:
        client.prices[date(2026, 11, 19)] = 50500.0
        DataUpdater(client, storage, history_years=1, today=date(2026, 11, 19)).run(["FPT"], with_market_summary=False)
        client.prices[date(2026, 11, 19)] = 51000.0
        results = DataUpdater(client, storage, history_years=1, today=date(2026, 11, 19)).run(
            ["FPT"], with_market_summary=False)
        stock = next(r for r in results if r.symbol == "FPT")
        final = storage.load_daily("stock_daily", "FPT", start="2026-11-19")["close"].iloc[0]
    actual = (f"Lúc 10:00 phiên đã chốt gần nhất là {session_morning.isoformat()}; sau 15:00 ứng dụng "
              f"{'tự cập nhật lại' if needs_update else 'KHÔNG cập nhật lại'}; giá lưu cho 19/11 = "
              f"{f'{final:,.0f}'.replace(',', '.')}, cách tải '{stock.mode}'")
    record("Dữ liệu đến muộn", how, expected, actual,
           session_morning == date(2026, 11, 18) and needs_update and final == 51000 and stock.mode == "incremental")


def main() -> None:
    print("Đang thử các tình huống lỗi (có gọi mạng, khoảng 15–30 giây)...\n")
    case_missing_key()
    case_wrong_key()
    case_unreachable()
    client = real_client()
    case_unknown_symbol(client)
    case_rate_limit(client)
    case_bad_portfolio()
    case_dirty_data()
    case_long_gap()
    case_late_data()

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(RESULTS)
    header = "| " + " | ".join(frame.columns) + " |\n| " + " | ".join("---" for _ in frame.columns) + " |\n"
    body = "\n".join("| " + " | ".join(row) + " |" for row in frame.astype(str).itertuples(index=False))
    now = datetime.now(config.VN_TZ).strftime("%d/%m/%Y %H:%M")
    OUT_FILE.write_text(f"# Thử các tình huống lỗi\n\nChạy lúc {now} (giờ Việt Nam) bằng "
                        f"`python scripts/test_error_scenarios.py`.\n\n{header}{body}\n", encoding="utf-8")
    count = {label: sum(r["Đánh giá"] == label for r in RESULTS) for label in ("Đạt", "KHÔNG ĐẠT", "Bỏ qua")}
    print(f"\n{len(RESULTS)} tình huống: {count['Đạt']} đạt, {count['KHÔNG ĐẠT']} không đạt, {count['Bỏ qua']} bỏ qua "
          f"(thiếu mạng hoặc API key). Đã ghi {OUT_FILE}")


if __name__ == "__main__":
    main()
