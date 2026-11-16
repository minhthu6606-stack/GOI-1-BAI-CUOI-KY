"""
Chạy thử lớp lấy dữ liệu với SSI thật: tải 3 năm dữ liệu FPT và VN-Index,
chuẩn hóa, rồi in báo cáo chất lượng dữ liệu.

Cách chạy (trong thư mục gốc của repo, đã kích hoạt .venv):
    python scripts/try_fetch.py

Script chỉ in ra màn hình và ghi nhật ký vào logs/try_fetch.log, chưa lưu vào kho dữ liệu.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Thêm thư mục gốc của repo vào đường dẫn để import được các module trong src/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import VN_TZ  # noqa: E402
from src.data.normalize import find_missing_sessions, normalize_index_daily, normalize_stock_daily  # noqa: E402
from src.logging_setup import setup_logging  # noqa: E402
from src.ssi_api.client import SSIClient, SSIError  # noqa: E402

YEARS_BACK = 3
STOCK = "FPT"
INDEX = "VNINDEX"


def main() -> None:
    setup_logging("try_fetch")
    log = logging.getLogger("try_fetch")

    end = datetime.now(VN_TZ).date()
    start = end - timedelta(days=365 * YEARS_BACK)
    log.info("Tải dữ liệu %s và %s từ %s đến %s", STOCK, INDEX, start, end)

    try:
        client = SSIClient.from_env()
        stock_raw = client.get_stock_daily(STOCK, start, end)
        index_raw = client.get_index_daily(INDEX, start, end)
    except SSIError as exc:
        log.error("Không lấy được dữ liệu: %s", exc)
        sys.exit(1)

    stock, stock_report = normalize_stock_daily(stock_raw, STOCK)
    index, index_report = normalize_index_daily(index_raw, INDEX)

    show = {
        STOCK: (stock, stock_report, ["trading_date", "close", "price_change_pct", "reference_price", "volume"]),
        INDEX: (index, index_report, ["trading_date", "close", "volume"]),
    }
    for name, (frame, report, columns) in show.items():
        print(f"\n=== {name} ===")
        print(f"Chất lượng: {report.summary()}")
        for note in report.notes:
            print(f"Ghi chú: {note}")
        if frame.empty:
            print("Không có dữ liệu.")
            continue
        print(f"Khoảng ngày: {frame['trading_date'].iloc[0]} -> {frame['trading_date'].iloc[-1]} ({len(frame)} phiên)")
        print(frame[columns].head(2).to_string(index=False))
        print("...")
        print(frame[columns].tail(2).to_string(index=False, header=False))

    if stock.empty or index.empty:
        return

    # Kiểm tra 1: đủ phiên chưa? Lấy lịch giao dịch của VN-Index làm chuẩn.
    missing = find_missing_sessions(stock, list(index["trading_date"]))
    print(f"\n[Kiểm tra 1] Số phiên {STOCK} thiếu so với lịch giao dịch VN-Index: {len(missing)}")
    if missing:
        print(f"   Ví dụ: {missing[:10]}")

    # Kiểm tra 2: giá lịch sử có phải giá đã điều chỉnh không? Giá thật trên HOSE luôn là số nguyên.
    non_integer = int((stock["close"] % 1 != 0).sum())
    print(f"[Kiểm tra 2] Số phiên có giá đóng cửa lẻ thập phân (dấu hiệu giá đã điều chỉnh): "
          f"{non_integer}/{len(stock)}")

    # Kiểm tra 3: lợi suất tính từ giá đóng cửa đã điều chỉnh có khớp với phần trăm thay đổi SSI công bố không?
    close_return = stock["close"].pct_change()
    pct_return = stock["price_change_pct"] / 100
    gap = (close_return - pct_return).abs()
    events = stock.loc[gap > 0.01, ["trading_date", "close", "price_change_pct"]]
    print(f"[Kiểm tra 3] Số phiên hai cách tính lợi suất lệch nhau > 1 điểm %: {len(events)}")
    if not events.empty:
        print(events.to_string(index=False))

    print(f"\nTổng số yêu cầu đã gửi tới SSI: {client.request_count}")


if __name__ == "__main__":
    main()
