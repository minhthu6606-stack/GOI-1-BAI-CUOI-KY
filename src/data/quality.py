"""
Báo cáo chất lượng và truy vết dữ liệu (dùng cho trang Phương pháp & dữ liệu, script kiểm chứng và báo cáo Mục 7).

    collection_summary(fetch_log)       mỗi lần cập nhật một dòng: lúc nào, phiên nào, bao nhiêu chuỗi thành công/lỗi
    quality_table(storage, symbols, ...) mỗi mã một dòng: số phiên, phiên thiếu, dòng bị gắn cờ, giá đã điều chỉnh,
                                         đối chiếu lợi suất tự tính với % thay đổi SSI công bố
"""
from __future__ import annotations

import bisect
from datetime import datetime

import pandas as pd

from src import config
from src.data.normalize import find_missing_sessions
from src.data.sessions import expected_latest_session
from src.data.storage import Storage

CROSS_CHECK_TOLERANCE = 0.01   # lệch quá 1 điểm % giữa lợi suất tự tính và % thay đổi SSI thì đếm là "lệch"


def _session_at(started_vn: datetime, calendar: list[str] | None) -> str:
    """Phiên mới nhất đã chốt dữ liệu tại thời điểm tải.

    Ước lượng theo giờ (ngày làm việc, sau 15:00) rồi, nếu có lịch giao dịch thật (các phiên VN-Index đã lưu),
    lùi về phiên giao dịch thật gần nhất - để lần tải vào ngày nghỉ lễ không bị tính thành một "phiên".
    """
    session = expected_latest_session(started_vn).isoformat()
    if calendar and calendar[0] <= session < calendar[-1]:
        session = calendar[bisect.bisect_right(calendar, session) - 1]
    return session


def collection_summary(fetch_log: pd.DataFrame, calendar: list[str] | None = None) -> pd.DataFrame:
    """Gộp nhật ký theo từng lần cập nhật (run_id), mới nhất ở trên.

    Cột "session": phiên mới nhất đã có dữ liệu chốt tại thời điểm tải (lần tải trước 15:00 thì là phiên hôm
    trước). Cùng một phiên có thể có nhiều lần tải; "on_time" cho biết lần tải có diễn ra trong ngày của phiên đó.
    `calendar` (tùy chọn): lịch giao dịch thật, dùng để bỏ qua ngày nghỉ lễ.
    """
    columns = ["run_id", "started_at", "session", "on_time", "series", "ok", "empty", "error", "failed_symbols"]
    if fetch_log.empty:
        return pd.DataFrame(columns=columns)
    rows = []
    for run_id, group in fetch_log.groupby("run_id", sort=False):
        started = min(group["started_at"])
        started_vn = datetime.fromisoformat(started).astimezone(config.VN_TZ)
        session = _session_at(started_vn, calendar)
        failed = group.loc[group["status"] == "error", "symbol"].tolist()
        rows.append({
            "run_id": run_id, "started_at": started, "session": session,
            "on_time": started_vn.date().isoformat() == session,
            "series": len(group), "ok": int((group["status"] == "ok").sum()),
            "empty": int((group["status"] == "empty").sum()), "error": len(failed),
            "failed_symbols": ", ".join(failed),
        })
    return pd.DataFrame(rows, columns=columns).sort_values("started_at", ascending=False).reset_index(drop=True)


def sessions_collected(summary: pd.DataFrame) -> list[str]:
    """Các phiên mà ứng dụng đã chạy cập nhật thành công (ít nhất một chuỗi tải được), sắp tăng dần.

    Đây là bằng chứng ứng dụng vận hành qua nhiều phiên, KHÁC với số phiên dữ liệu trong kho: mỗi lần tải lấy
    về cả lịch sử giá (vd 3 năm), nên số phiên dữ liệu tự thu thập lớn hơn nhiều số lần chạy.
    """
    if summary.empty:
        return []
    good = summary[summary["ok"] > 0]
    return sorted(set(good["session"]))


def quality_table(storage: Storage, symbols: list[str], index_code: str = config.MARKET_INDEX) -> pd.DataFrame:
    """Chất lượng dữ liệu từng mã so với lịch giao dịch của VN-Index."""
    calendar = storage.trading_calendar(index_code)
    rows = []
    for symbol in symbols:
        frame = storage.load_daily("stock_daily", symbol)
        if frame.empty:
            rows.append({"symbol": symbol, "sessions": 0})
            continue
        in_range = [d for d in calendar if frame["trading_date"].min() <= d <= frame["trading_date"].max()]
        close = pd.to_numeric(frame["close"], errors="coerce")
        returns = close.pct_change()
        reported = pd.to_numeric(frame["price_change_pct"], errors="coerce") / 100
        gap = (returns - reported).abs()
        rows.append({
            "symbol": symbol,
            "sessions": len(frame),
            "first": frame["trading_date"].min(),
            "last": frame["trading_date"].max(),
            "missing": len(find_missing_sessions(frame, in_range)),
            "flagged": int((frame["quality_flag"].fillna("") != "").sum()) if "quality_flag" in frame else 0,
            "adjusted": int(((close % 1).abs() > 1e-9).sum()),
            "cross_checked": int(gap.notna().sum()),
            "cross_mismatch": int((gap > CROSS_CHECK_TOLERANCE).sum()),
        })
    return pd.DataFrame(rows)
