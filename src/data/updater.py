"""
Cập nhật kho dữ liệu từ SSI: tải lần đầu, cập nhật phần mới, phát hiện giá lịch sử bị điều chỉnh.

Quy trình cho mỗi mã (cổ phiếu hoặc chỉ số):
    1. Chưa có dữ liệu      -> tải đủ HISTORY_YEARS năm               (mode = "full")
    2. Đã có dữ liệu        -> tải lại từ (phiên cuối - OVERLAP_DAYS)  (mode = "incremental")
    3. So sánh giá đóng cửa ở phần trùng giữa dữ liệu đã lưu và dữ liệu mới tải.
       SSI trả giá ĐÃ ĐIỀU CHỈNH; khi có cổ tức/cổ phiếu thưởng mới, SSI điều chỉnh lại toàn bộ
       lịch sử. Nếu chỉ ghép phần mới vào phần cũ, chuỗi giá sẽ có một bước nhảy giả.
       Vì vậy nếu phần trùng lệch quá PRICE_ADJUST_TOLERANCE thì xóa và tải lại toàn bộ (mode = "refresh").
    4. Ghi vào kho, đếm phiên thiếu so với lịch giao dịch, ghi nhật ký fetch_log.

Lỗi của một mã không làm dừng các mã khác: lỗi được ghi vào nhật ký với status = "error".
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable

import pandas as pd

from src import config
from src.data.normalize import (
    QualityReport,
    find_missing_sessions,
    normalize_index_daily,
    normalize_stock_daily,
)
from src.data.storage import Storage, now_vn
from src.ssi_api.client import SSIClient, SSIError

logger = logging.getLogger(__name__)

FetchFn = Callable[[str, date, date], list[dict[str, Any]]]
NormalizeFn = Callable[[list[dict[str, Any]], str], tuple[pd.DataFrame, QualityReport]]


@dataclass
class UpdateResult:
    """Kết quả cập nhật một mã - cũng chính là một dòng trong bảng fetch_log."""

    symbol: str
    dataset: str                 # "stock_daily" hoặc "index_daily"
    mode: str = ""               # full / incremental / refresh
    date_from: str = ""
    date_to: str = ""
    rows_received: int = 0
    rows_kept: int = 0
    rows_flagged: int = 0
    missing_sessions: int = 0
    status: str = "ok"           # ok / empty / error
    message: str = ""


def history_was_adjusted(stored: pd.DataFrame, fresh: pd.DataFrame, tolerance: float) -> bool:
    """True nếu giá đóng cửa ở các phiên trùng nhau lệch quá `tolerance` (tính theo tỷ lệ).

    Bỏ qua phiên trùng mới nhất: nếu lần trước cập nhật trong giờ giao dịch thì giá phiên đó
    chưa phải giá đóng cửa cuối cùng, lệch là bình thường.
    """
    if stored.empty or fresh.empty:
        return False
    merged = stored[["trading_date", "close"]].merge(
        fresh[["trading_date", "close"]], on="trading_date", suffixes=("_stored", "_fresh")
    )
    merged = merged[merged["trading_date"] < stored["trading_date"].max()]
    if merged.empty:
        return False
    relative_gap = (merged["close_fresh"] / merged["close_stored"] - 1).abs()
    return bool((relative_gap > tolerance).any())


class DataUpdater:
    """Điều phối việc tải dữ liệu từ SSI và ghi vào kho."""

    def __init__(
        self,
        client: SSIClient,
        storage: Storage,
        history_years: int = config.HISTORY_YEARS,
        overlap_days: int = config.OVERLAP_DAYS,
        today: date | None = None,
    ) -> None:
        self.client = client
        self.storage = storage
        self.history_years = history_years
        self.overlap_days = overlap_days
        self.today = today or datetime.now(config.VN_TZ).date()
        self.run_id = uuid.uuid4().hex[:8]

    @property
    def full_start(self) -> date:
        return self.today - timedelta(days=365 * self.history_years)

    # ------------------------------------------------------------------ một chuỗi dữ liệu

    def _update_series(
        self, symbol: str, table: str, fetch: FetchFn, normalize: NormalizeFn, calendar: list[str] | None
    ) -> UpdateResult:
        result = UpdateResult(symbol=symbol, dataset=table)
        started_at = now_vn()
        try:
            last = self.storage.last_trading_date(table, symbol)
            if last is None:
                result.mode, start = "full", self.full_start
            else:
                result.mode = "incremental"
                start = max(self.full_start, date.fromisoformat(last) - timedelta(days=self.overlap_days))

            frame, report = normalize(fetch(symbol, start, self.today), symbol)

            if result.mode == "incremental" and last is not None:
                stored = self.storage.load_daily(table, symbol, start=start.isoformat(), end=last)
                if history_was_adjusted(stored, frame, config.PRICE_ADJUST_TOLERANCE):
                    logger.info("%s: giá lịch sử đã được SSI điều chỉnh lại, tải lại toàn bộ", symbol)
                    result.mode, start = "refresh", self.full_start
                    frame, report = normalize(fetch(symbol, start, self.today), symbol)
                    self.storage.delete_symbol(table, symbol)

            result.date_from, result.date_to = start.isoformat(), self.today.isoformat()
            result.rows_received, result.rows_kept, result.rows_flagged = report.total, report.kept, report.flagged
            if frame.empty:
                result.status, result.message = "empty", "SSI không trả dữ liệu (mã sai hoặc chưa có giao dịch)"
            else:
                self.storage.upsert_daily(table, frame, fetched_at=now_vn())
                if calendar:
                    stored_all = self.storage.load_daily(table, symbol)
                    result.missing_sessions = len(find_missing_sessions(stored_all, calendar))
                result.message = "; ".join(report.notes)
        except SSIError as exc:
            result.status, result.message = "error", str(exc)
            logger.error("Cập nhật %s thất bại: %s", symbol, exc)

        self.storage.log_fetch({**asdict(result), "run_id": self.run_id, "started_at": started_at,
                                "finished_at": now_vn()})
        return result

    # ------------------------------------------------------------------ dùng bên ngoài

    def update_index(self, index_code: str = config.MARKET_INDEX) -> UpdateResult:
        return self._update_series(index_code, "index_daily", self.client.get_index_daily,
                                   normalize_index_daily, calendar=None)

    def update_stock(self, symbol: str, calendar: list[str]) -> UpdateResult:
        return self._update_series(symbol, "stock_daily", self.client.get_stock_daily,
                                   normalize_stock_daily, calendar=calendar)

    def update_securities(self, max_age_days: int = config.SECURITIES_MAX_AGE_DAYS) -> int:
        """Làm mới danh sách mã nếu chưa có hoặc đã cũ hơn `max_age_days` ngày. Trả về số mã đã ghi."""
        updated_at = self.storage.securities_updated_at()
        if updated_at and datetime.fromisoformat(updated_at).date() > self.today - timedelta(days=max_age_days):
            return 0
        total = 0
        for board in config.BOARDS:
            try:
                total += self.storage.upsert_securities(self.client.get_securities(board), updated_at=now_vn())
            except SSIError as exc:
                logger.error("Không tải được danh sách mã sàn %s: %s", board, exc)
        return total

    def update_market_summary(self, board: str = "HOSE") -> bool:
        """Lưu tổng hợp thị trường của ngày hôm nay (độ rộng, khối ngoại toàn sàn)."""
        try:
            record = self.client.get_market_summary(board)
        except SSIError as exc:
            logger.error("Không tải được tổng hợp thị trường %s: %s", board, exc)
            return False
        if not record:
            return False
        trading_date = (pd.to_datetime(record.get("tradingDate"), format="%Y/%m/%d", errors="coerce"))
        day = trading_date.date().isoformat() if pd.notna(trading_date) else self.today.isoformat()
        self.storage.save_market_summary(board, record, trading_date=day, fetched_at=now_vn())
        return True

    def run(self, symbols: list[str], index_code: str = config.MARKET_INDEX,
            with_market_summary: bool = True) -> list[UpdateResult]:
        """Cập nhật toàn bộ: danh sách mã -> chỉ số (lịch giao dịch) -> từng cổ phiếu -> tổng hợp thị trường."""
        securities_count = self.update_securities()
        if securities_count:
            logger.info("Đã làm mới danh sách %d mã", securities_count)

        results = [self.update_index(index_code)]
        calendar = self.storage.trading_calendar(index_code)
        for symbol in symbols:
            results.append(self.update_stock(symbol.upper().strip(), calendar))

        if with_market_summary:
            self.update_market_summary("HOSE")
        return results
