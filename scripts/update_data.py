"""
Cập nhật kho dữ liệu SQLite từ SSI.

Cách chạy (trong thư mục gốc của repo, đã kích hoạt .venv):
    python scripts/update_data.py                       # các mã của danh mục mặc định
    python scripts/update_data.py --symbols FPT ACB     # chỉ định mã khác
    python scripts/update_data.py --status              # chỉ xem kho đang có gì, không tải

Lần đầu: tải đủ 3 năm (khoảng 10 yêu cầu/mã). Các lần sau: chỉ tải phần mới (1 yêu cầu/mã).
Nên chạy sau 15:00 để có giá đóng cửa cuối cùng của phiên.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Thêm thư mục gốc của repo vào đường dẫn để import được các module trong src/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src import config  # noqa: E402
from src.data.storage import Storage  # noqa: E402
from src.data.updater import DataUpdater  # noqa: E402
from src.logging_setup import setup_logging  # noqa: E402
from src.ssi_api.client import SSIClient, SSIError  # noqa: E402


def print_status(storage: Storage) -> None:
    """In tóm tắt kho dữ liệu và 10 dòng nhật ký gần nhất."""
    pd.set_option("display.width", 160)
    print("\n=== KHO DỮ LIỆU ===")
    coverage = storage.coverage()
    print(coverage.to_string(index=False) if not coverage.empty else "Kho trống.")

    print(f"\nSố mã trong danh sách chứng khoán: {len(storage.load_securities())}")
    summary = storage.load_market_summary("HOSE")
    print(f"Số ngày có tổng hợp thị trường HOSE: {len(summary)}")

    print("\n=== NHẬT KÝ CẬP NHẬT GẦN NHẤT ===")
    log = storage.load_fetch_log(limit=10)
    columns = ["started_at", "symbol", "mode", "rows_kept", "missing_sessions", "status", "message"]
    print(log[columns].to_string(index=False) if not log.empty else "Chưa có nhật ký.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cập nhật kho dữ liệu từ SSI FastConnect")
    parser.add_argument("--symbols", nargs="+", default=config.DEFAULT_SYMBOLS, help="danh sách mã cổ phiếu")
    parser.add_argument("--status", action="store_true", help="chỉ in tình trạng kho, không tải dữ liệu")
    args = parser.parse_args()

    setup_logging("update_data")
    log = logging.getLogger("update_data")

    with Storage() as storage:
        if not args.status:
            try:
                client = SSIClient.from_env()
            except SSIError as exc:
                log.error("%s", exc)
                sys.exit(1)
            client.raw_hook = storage.save_raw  # lưu nguyên văn mọi response để truy vết

            updater = DataUpdater(client, storage)
            log.info("Bắt đầu cập nhật (run_id=%s): %s + %s", updater.run_id, config.MARKET_INDEX, args.symbols)
            results = updater.run(args.symbols)

            failed = [r for r in results if r.status != "ok"]
            log.info("Xong: %d chuỗi thành công, %d có vấn đề, %d yêu cầu tới SSI",
                     len(results) - len(failed), len(failed), client.request_count)
            for r in failed:
                log.warning("%s: %s - %s", r.symbol, r.status, r.message)

        print_status(storage)


if __name__ == "__main__":
    main()
