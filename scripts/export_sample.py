"""
Xuất bản dữ liệu SSI lưu kèm mã nguồn: chép dữ liệu THẬT đã tải từ SSI của các mã trong
danh mục mặc định và VN-Index sang data_sample/sample.db (file này được đưa lên GitHub).

Máy không có kho data/ (vd máy người chấm, không có API key) sẽ tự dùng bản này, nên ứng dụng
chạy được ngay. Đây là dữ liệu thật đã ghi lại, không phải dữ liệu giả; ứng dụng ghi rõ phiên chốt dữ liệu.

Cách chạy (sau khi đã chạy update_data.py và make_demo_portfolio.py):
    python scripts/export_sample.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config  # noqa: E402
from src.data.storage import Storage  # noqa: E402
from src.finance.portfolio import load_portfolio_csv  # noqa: E402

SAMPLE_DB = config.SAMPLE_DB_PATH
PORTFOLIO_CSV = config.DEMO_PORTFOLIO_PATH


def export_sample(source: Storage, target_path: Path, symbols: list[str], index_code: str) -> dict[str, int]:
    """Chép dữ liệu của `symbols` và `index_code` từ kho nguồn sang một kho mới. Trả về số dòng mỗi bảng."""
    if target_path.exists():
        target_path.unlink()  # luôn tạo mới để không lẫn dữ liệu cũ
    counts = {"stock_daily": 0, "index_daily": 0, "securities": 0, "market_summary": 0, "fetch_log": 0}
    with Storage(target_path) as target:
        for symbol in symbols:
            frame = source.load_daily("stock_daily", symbol)
            if not frame.empty:
                counts["stock_daily"] += _copy_daily(target, "stock_daily", frame)
        index_frame = source.load_daily("index_daily", index_code)
        counts["index_daily"] = _copy_daily(target, "index_daily", index_frame)

        securities = source.load_securities(symbols)
        if not securities.empty:
            securities.to_sql("securities", target.conn, if_exists="append", index=False)
        counts["securities"] = len(securities)

        summary = source.load_market_summary("HOSE")
        if not summary.empty:
            summary.to_sql("market_summary", target.conn, if_exists="append", index=False)
        counts["market_summary"] = len(summary)

        log = source.load_fetch_log(limit=1000).drop(columns=["id"])
        if not log.empty:
            log.iloc[::-1].to_sql("fetch_log", target.conn, if_exists="append", index=False)
        counts["fetch_log"] = len(log)
        target.conn.commit()
        target.conn.execute("VACUUM")
    return counts


def _copy_daily(target: Storage, table: str, frame) -> int:
    """Chép nguyên văn các dòng (giữ cả source và fetched_at gốc để truy vết)."""
    if frame.empty:
        return 0
    frame.to_sql(table, target.conn, if_exists="append", index=False)
    return len(frame)


def main() -> None:
    if not config.DB_PATH.exists():
        sys.exit("[LỖI] Chưa có kho dữ liệu. Hãy chạy: python scripts/update_data.py")
    symbols = load_portfolio_csv(PORTFOLIO_CSV).symbols if PORTFOLIO_CSV.exists() else config.DEFAULT_SYMBOLS
    with Storage() as source:
        counts = export_sample(source, SAMPLE_DB, symbols, config.MARKET_INDEX)
    size_kb = SAMPLE_DB.stat().st_size / 1024
    print(f"Đã xuất {SAMPLE_DB} ({size_kb:,.0f} KB)")
    for table, rows in counts.items():
        print(f"   {table}: {rows} dòng")


if __name__ == "__main__":
    main()
