"""
Lớp gọi SSI FastConnect API v3 (chỉ dữ liệu thị trường).

Lớp này chỉ lo "nói chuyện" với SSI:
    - xác thực bằng apiKey/apiSecret, KHÔNG gửi OTP -> token chỉ có quyền đọc dữ liệu,
      không thể đặt lệnh giao dịch (đáp ứng Mục 8 của đề);
    - tự giới hạn tần suất ~1 yêu cầu/giây;
    - tự xác thực lại khi token hết hạn, tự thử lại khi mất mạng hoặc máy chủ bận;
    - tự lật trang và chia khoảng thời gian dài thành nhiều đoạn.

Lớp này KHÔNG xử lý hay lưu dữ liệu; việc đó thuộc về src/data/.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime, timedelta
from datetime import time as dt_time
from typing import Any, Callable

import requests
from dotenv import load_dotenv

from src import config

logger = logging.getLogger(__name__)

# Hàm nhận (đường dẫn endpoint, tham số, nội dung JSON) mỗi khi gọi thành công - dùng để lưu dữ liệu thô
RawHook = Callable[[str, dict[str, Any], Any], None]


class SSIError(Exception):
    """Lỗi khi gọi SSI API mà không tự khắc phục được."""


def date_chunks(start: date, end: date, max_days: int) -> list[tuple[date, date]]:
    """Chia khoảng [start, end] thành các đoạn liên tiếp, mỗi đoạn dài tối đa `max_days` ngày."""
    if start > end:
        raise ValueError("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc")
    chunks = []
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=max_days - 1), end)
        chunks.append((chunk_start, chunk_end))
        chunk_start = chunk_end + timedelta(days=1)
    return chunks


class SSIClient:
    """Client đọc dữ liệu thị trường từ SSI FastConnect API v3."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = config.SSI_BASE_URL,
        min_interval: float = config.SSI_MIN_INTERVAL_SECONDS,
        session: requests.Session | None = None,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self.base_url = base_url
        self.min_interval = min_interval
        self.session = session or requests.Session()
        self.raw_hook: RawHook | None = None   # gắn hàm lưu dữ liệu thô ở bên ngoài nếu cần
        self.request_count = 0                  # đếm số yêu cầu đã gửi (để báo cáo)
        self._token: str | None = None
        self._token_expires_at = 0.0            # thời điểm hết hạn, tính bằng giây (epoch)
        self._last_request_at = 0.0

    @classmethod
    def from_env(cls) -> "SSIClient":
        """Tạo client từ biến môi trường trong file .env (không bao giờ viết key vào code)."""
        load_dotenv(config.PROJECT_ROOT / ".env")
        api_key = os.getenv("SSI_API_KEY")
        api_secret = os.getenv("SSI_API_SECRET")
        if not api_key or not api_secret:
            raise SSIError("Thiếu SSI_API_KEY hoặc SSI_API_SECRET trong file .env (xem .env.example)")
        return cls(api_key, api_secret)

    # ------------------------------------------------------------------ nội bộ

    def _wait_for_rate_limit(self) -> None:
        """Chờ đủ khoảng cách tối thiểu kể từ yêu cầu trước (tự giới hạn tần suất)."""
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_at = time.monotonic()
        self.request_count += 1

    def _authenticate(self) -> None:
        """Lấy access token mới, không kèm OTP."""
        self._wait_for_rate_limit()
        try:
            resp = self.session.post(
                f"{self.base_url}/auth/token",
                json={"apiKey": self._api_key, "apiSecret": self._api_secret},
                timeout=config.SSI_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise SSIError(f"Không kết nối được máy chủ SSI khi xác thực: {exc}") from exc
        if resp.status_code != 200:
            raise SSIError(f"Xác thực thất bại: HTTP {resp.status_code} - {resp.text[:200]}")

        body = resp.json()
        token = body.get("accessToken") or (body.get("data") or {}).get("accessToken")
        if not token:
            raise SSIError(f"Không thấy accessToken trong response, các khóa: {list(body)}")
        self._token = token
        # Nếu SSI không trả thời điểm hết hạn, coi như token dùng được 10 phút
        self._token_expires_at = float(body.get("expiresAt") or time.time() + 600)
        logger.info("Đã lấy access token SSI (quyền đọc dữ liệu, không OTP)")

    def _ensure_token(self) -> None:
        """Lấy token nếu chưa có hoặc sắp hết hạn (còn dưới 60 giây)."""
        if self._token is None or time.time() > self._token_expires_at - 60:
            self._authenticate()

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        """Gọi một endpoint GET, có thử lại khi lỗi tạm thời. Trả về nội dung JSON."""
        for attempt in range(1, config.SSI_MAX_RETRIES + 1):
            self._ensure_token()
            self._wait_for_rate_limit()
            headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}
            try:
                resp = self.session.get(
                    f"{self.base_url}/{path}", headers=headers, params=params,
                    timeout=config.SSI_TIMEOUT_SECONDS,
                )
            except requests.RequestException as exc:
                logger.warning("Lỗi mạng khi gọi /%s (lần %d): %s", path, attempt, exc)
                time.sleep(2 ** attempt)  # chờ tăng dần: 2s, 4s, 8s
                continue

            if resp.status_code == 200:
                body = resp.json()
                if self.raw_hook is not None:
                    self.raw_hook(path, params, body)
                return body
            if resp.status_code == 401:
                logger.info("Token hết hạn hoặc bị từ chối, xác thực lại")
                self._token = None
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                logger.warning("SSI trả HTTP %d cho /%s (lần %d), chờ rồi thử lại", resp.status_code, path, attempt)
                time.sleep(2 ** attempt)
                continue
            # Các lỗi 4xx còn lại (sai tham số...) thử lại cũng vô ích
            raise SSIError(f"HTTP {resp.status_code} khi gọi /{path}: {resp.text[:200]}")

        raise SSIError(f"Gọi /{path} thất bại sau {config.SSI_MAX_RETRIES} lần thử")

    def _get_all_pages(self, path: str, params: dict[str, Any], page_key: str) -> list[dict[str, Any]]:
        """Lật lần lượt từng trang cho tới khi một trang trả về ít hơn kích thước trang."""
        records: list[dict[str, Any]] = []
        previous_first: dict[str, Any] | None = None
        for page in range(1, config.SSI_MAX_PAGES + 1):
            body = self._get(path, {**params, page_key: page, "pageSize": config.SSI_PAGE_SIZE})
            data = body.get("data") if isinstance(body, dict) else body
            if data is None:
                data = []
            if not isinstance(data, list):
                raise SSIError(f"/{path} trả về dữ liệu không phải danh sách: {type(data)}")
            if data and data[0] == previous_first:
                logger.warning(
                    "/%s trả lại trang trùng ở trang %d, dừng lật trang - CÓ THỂ THIẾU DỮ LIỆU, "
                    "hãy giảm độ dài đoạn ngày", path, page,
                )
                break
            records.extend(data)
            if len(data) < config.SSI_PAGE_SIZE:
                break
            previous_first = data[0] if data else None
        else:
            logger.warning("/%s vượt quá %d trang, có thể thiếu dữ liệu", path, config.SSI_MAX_PAGES)
        return records

    # ------------------------------------------------------------------ dùng bên ngoài

    def get_securities(self, board: str) -> list[dict[str, Any]]:
        """Danh sách chứng khoán trên một sàn (HOSE / HNX / UPCOM), kèm ngành và số cổ phiếu niêm yết."""
        body = self._get("data/securitiesByBoard", {"board": board})
        return body if isinstance(body, list) else (body.get("data") or [])

    def get_stock_daily(self, symbol: str, start: date, end: date) -> list[dict[str, Any]]:
        """Dữ liệu giao dịch theo phiên của một cổ phiếu (giá, khối lượng, khối ngoại, room).

        Chia đoạn ngắn (SSI_SUMMARY_MAX_DAYS) vì endpoint này không lật trang được.
        """
        records: list[dict[str, Any]] = []
        for chunk_start, chunk_end in date_chunks(start, end, config.SSI_SUMMARY_MAX_DAYS):
            params = {
                "symbol": symbol,
                "from": chunk_start.strftime(config.SSI_DATE_FORMAT_SUMMARY),
                "to": chunk_end.strftime(config.SSI_DATE_FORMAT_SUMMARY),
            }
            records.extend(self._get_all_pages("data/securitiesSummary", params, page_key="pageNumber"))
        return records

    def get_index_daily(self, index_code: str, start: date, end: date) -> list[dict[str, Any]]:
        """Nến ngày của một chỉ số (ví dụ VNINDEX)."""
        records: list[dict[str, Any]] = []
        for chunk_start, chunk_end in date_chunks(start, end, config.SSI_MAX_DAYS_PER_REQUEST):
            params = {
                "symbol": index_code,
                "timeFrame": "1d",
                "from": datetime.combine(chunk_start, dt_time(0, 0, 0)).strftime(config.SSI_DATE_FORMAT_OHLC),
                "to": datetime.combine(chunk_end, dt_time(23, 59, 59)).strftime(config.SSI_DATE_FORMAT_OHLC),
            }
            records.extend(self._get_all_pages("data/ohlc", params, page_key="pageIndex"))
        return records

    def get_market_summary(self, board: str, trading_date: date | None = None) -> dict[str, Any] | None:
        """Tổng hợp thị trường của một sàn trong một ngày: độ rộng, thanh khoản, khối ngoại."""
        params: dict[str, Any] = {"board": board}
        if trading_date is not None:
            params["tradingDate"] = trading_date.strftime(config.SSI_DATE_FORMAT_SUMMARY)
        body = self._get("data/indexSummary", params)
        data = body if isinstance(body, list) else (body.get("data") if isinstance(body, dict) else None)
        if isinstance(data, list):
            return data[0] if data else None
        return data
