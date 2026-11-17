"""
Đọc dữ liệu thị trường từ kho SQLite thành các bảng mà lớp tài chính cần.

Tách riêng việc đọc dữ liệu khỏi các công thức tài chính: các công thức chỉ nhận DataFrame,
nên kiểm thử được bằng dữ liệu tự tạo mà không cần kho hay mạng.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src import config
from src.data.storage import Storage


@dataclass
class MarketData:
    close: pd.DataFrame              # dòng = ngày giao dịch, cột = mã; giá đóng cửa đã điều chỉnh
    volume: pd.DataFrame             # khối lượng khớp lệnh
    index_close: pd.Series           # giá đóng cửa VN-Index
    latest: pd.DataFrame             # bản ghi mới nhất mỗi mã (giá, room ngoại...), index = mã
    securities: pd.DataFrame         # danh sách mã: sàn, ngành, tên
    last_trading_date: str | None    # phiên mới nhất có trong kho
    last_fetched_at: str | None      # thời điểm cập nhật dữ liệu gần nhất (giờ Việt Nam)
    missing_symbols: list[str] = field(default_factory=list)  # mã chưa có dữ liệu trong kho


def load_market_data(storage: Storage, symbols: list[str], index_code: str = config.MARKET_INDEX) -> MarketData:
    """Đọc dữ liệu của các mã trong danh mục và chỉ số thị trường từ kho."""
    closes, volumes, latest_rows, missing, fetched = {}, {}, [], [], []
    for symbol in symbols:
        frame = storage.load_daily("stock_daily", symbol)
        if frame.empty:
            missing.append(symbol)
            continue
        series = frame.set_index("trading_date")
        closes[symbol] = series["close"]
        volumes[symbol] = series["volume"]
        latest_rows.append(frame.iloc[-1])
        fetched.append(frame["fetched_at"].max())

    index_frame = storage.load_daily("index_daily", index_code)
    index_close = index_frame.set_index("trading_date")["close"] if not index_frame.empty else pd.Series(dtype=float)
    if not index_frame.empty:
        fetched.append(index_frame["fetched_at"].max())

    close = pd.DataFrame(closes).sort_index()
    latest = pd.DataFrame(latest_rows).set_index("symbol") if latest_rows else pd.DataFrame()
    last_date = max([str(d) for d in close.index] + [str(d) for d in index_close.index], default=None)
    return MarketData(
        close=close,
        volume=pd.DataFrame(volumes).sort_index(),
        index_close=index_close.sort_index(),
        latest=latest,
        securities=storage.load_securities(symbols),
        last_trading_date=last_date,
        last_fetched_at=max([f for f in fetched if isinstance(f, str)], default=None),
        missing_symbols=missing,
    )
