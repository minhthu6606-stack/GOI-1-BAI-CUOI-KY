"""
Kho dữ liệu SQLite của dự án.

Vì sao chọn SQLite: có sẵn trong Python (không cần cài máy chủ cơ sở dữ liệu), toàn bộ kho
là một file duy nhất (data/portfolio.db), mở xem được bằng "DB Browser for SQLite".

Các bảng:
    securities      danh sách mã: tên, sàn, ngành, số cổ phiếu niêm yết
    stock_daily     dữ liệu theo phiên của cổ phiếu (giá đã điều chỉnh, khối lượng, khối ngoại, room)
    index_daily     dữ liệu theo phiên của chỉ số (VN-Index)
    market_summary  tổng hợp thị trường theo sàn mỗi ngày (độ rộng, khối ngoại toàn sàn)
    raw_responses   nội dung JSON gốc SSI trả về - để truy vết nguồn dữ liệu
    fetch_log       nhật ký mỗi lần cập nhật: thời điểm, số bản ghi, số phiên thiếu, lỗi nếu có

Mọi dấu thời gian (fetched_at, started_at...) lưu theo giờ Việt Nam, dạng ISO 8601 có múi giờ.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import DB_PATH, VN_TZ

SCHEMA = """
CREATE TABLE IF NOT EXISTS securities (
    symbol TEXT PRIMARY KEY,
    name_vi TEXT, name_en TEXT, board TEXT,
    icb_code TEXT, icb_name TEXT,
    listed_share REAL, lot_size REAL, stock_type TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS stock_daily (
    symbol TEXT NOT NULL, trading_date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, average REAL,
    price_change REAL, price_change_pct REAL, reference_price REAL,
    volume REAL, value REAL, deal_volume REAL, deal_value REAL,
    foreign_buy_volume REAL, foreign_buy_value REAL,
    foreign_sell_volume REAL, foreign_sell_value REAL,
    foreign_room_remaining REAL, foreign_room_total REAL,
    quality_flag TEXT, source TEXT, fetched_at TEXT,
    PRIMARY KEY (symbol, trading_date)
);
CREATE TABLE IF NOT EXISTS index_daily (
    symbol TEXT NOT NULL, trading_date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume REAL, value REAL,
    quality_flag TEXT, source TEXT, fetched_at TEXT,
    PRIMARY KEY (symbol, trading_date)
);
CREATE TABLE IF NOT EXISTS market_summary (
    board TEXT NOT NULL, trading_date TEXT NOT NULL,
    index_value REAL, index_change REAL, index_change_pct REAL,
    advances REAL, declines REAL, no_change REAL, ceiling REAL, floor REAL,
    total_match_volume REAL, total_match_value REAL,
    foreign_buy_value REAL, foreign_sell_value REAL, foreign_net_value REAL,
    source TEXT, fetched_at TEXT,
    PRIMARY KEY (board, trading_date)
);
CREATE TABLE IF NOT EXISTS raw_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fetched_at TEXT, endpoint TEXT, params TEXT, payload TEXT
);
CREATE TABLE IF NOT EXISTS fetch_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT, started_at TEXT, finished_at TEXT,
    symbol TEXT, dataset TEXT, mode TEXT,
    date_from TEXT, date_to TEXT,
    rows_received INTEGER, rows_kept INTEGER, rows_flagged INTEGER, missing_sessions INTEGER,
    status TEXT, message TEXT
);
"""

DAILY_TABLES = ("stock_daily", "index_daily")


def now_vn() -> str:
    """Thời điểm hiện tại theo giờ Việt Nam, dạng ISO 8601 (vd 2026-11-17T15:05:12+07:00)."""
    return datetime.now(VN_TZ).isoformat(timespec="seconds")


def _to_sql_value(value: Any) -> Any:
    """SQLite không có NaN: đổi giá trị thiếu (NaN/None) của pandas thành NULL."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


class Storage:
    """Đọc/ghi kho SQLite. Dùng được với lệnh `with Storage() as storage:`."""

    def __init__(self, db_path: Path | str = DB_PATH) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.executescript(SCHEMA)

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    def _columns(self, table: str) -> list[str]:
        return [row[1] for row in self.conn.execute(f"PRAGMA table_info({table})")]

    # ------------------------------------------------------------------ dữ liệu theo phiên

    def upsert_daily(self, table: str, frame: pd.DataFrame, fetched_at: str, source: str = "SSI") -> int:
        """Ghi dữ liệu theo phiên. Phiên đã có thì ghi đè (không nhân đôi). Trả về số dòng đã ghi."""
        if table not in DAILY_TABLES:
            raise ValueError(f"Bảng không hợp lệ: {table}")
        if frame.empty:
            return 0
        frame = frame.assign(source=source, fetched_at=fetched_at)
        columns = [col for col in self._columns(table) if col in frame.columns]
        rows = [tuple(_to_sql_value(v) for v in row) for row in frame[columns].itertuples(index=False)]
        placeholders = ", ".join("?" for _ in columns)
        with self.conn:
            self.conn.executemany(
                f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", rows
            )
        return len(rows)

    def delete_symbol(self, table: str, symbol: str) -> None:
        """Xóa toàn bộ dữ liệu của một mã (dùng khi phải tải lại từ đầu)."""
        if table not in DAILY_TABLES:
            raise ValueError(f"Bảng không hợp lệ: {table}")
        with self.conn:
            self.conn.execute(f"DELETE FROM {table} WHERE symbol = ?", (symbol,))

    def last_trading_date(self, table: str, symbol: str) -> str | None:
        row = self.conn.execute(f"SELECT MAX(trading_date) FROM {table} WHERE symbol = ?", (symbol,)).fetchone()
        return row[0] if row else None

    def load_daily(self, table: str, symbol: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        """Đọc dữ liệu theo phiên của một mã, sắp xếp tăng dần theo ngày."""
        query = f"SELECT * FROM {table} WHERE symbol = ?"
        params: list[Any] = [symbol]
        if start:
            query += " AND trading_date >= ?"
            params.append(start)
        if end:
            query += " AND trading_date <= ?"
            params.append(end)
        return pd.read_sql_query(query + " ORDER BY trading_date", self.conn, params=params)

    def trading_calendar(self, index_code: str) -> list[str]:
        """Danh sách ngày giao dịch, lấy theo các phiên đã lưu của chỉ số thị trường."""
        rows = self.conn.execute(
            "SELECT trading_date FROM index_daily WHERE symbol = ? ORDER BY trading_date", (index_code,)
        )
        return [row[0] for row in rows]

    def coverage(self) -> pd.DataFrame:
        """Tóm tắt kho: mỗi mã có bao nhiêu phiên, từ ngày nào đến ngày nào."""
        query = """
            SELECT 'stock' AS kind, symbol, COUNT(*) AS sessions, MIN(trading_date) AS first, MAX(trading_date) AS last
            FROM stock_daily GROUP BY symbol
            UNION ALL
            SELECT 'index', symbol, COUNT(*), MIN(trading_date), MAX(trading_date) FROM index_daily GROUP BY symbol
            ORDER BY kind, symbol
        """
        return pd.read_sql_query(query, self.conn)

    # ------------------------------------------------------------------ danh sách mã

    def upsert_securities(self, records: list[dict[str, Any]], updated_at: str) -> int:
        """Ghi danh sách mã từ endpoint securitiesByBoard."""
        rows = [
            (
                r.get("symbol"), r.get("symbolNameVi"), r.get("symbolNameEn"), r.get("board"),
                r.get("icbCode"), r.get("icbName"),
                _float_or_none(r.get("listedShare")), _float_or_none(r.get("lotSize")), r.get("stockType"),
                updated_at,
            )
            for r in records
            if r.get("symbol")
        ]
        with self.conn:
            self.conn.executemany("INSERT OR REPLACE INTO securities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
        return len(rows)

    def securities_updated_at(self) -> str | None:
        row = self.conn.execute("SELECT MAX(updated_at) FROM securities").fetchone()
        return row[0] if row else None

    def load_securities(self, symbols: list[str] | None = None) -> pd.DataFrame:
        if symbols:
            marks = ", ".join("?" for _ in symbols)
            return pd.read_sql_query(f"SELECT * FROM securities WHERE symbol IN ({marks})", self.conn, params=symbols)
        return pd.read_sql_query("SELECT * FROM securities", self.conn)

    # ------------------------------------------------------------------ tổng hợp thị trường

    def save_market_summary(self, board: str, record: dict[str, Any], trading_date: str, fetched_at: str) -> None:
        """Ghi tổng hợp thị trường của một sàn trong một ngày (endpoint indexSummary)."""
        values = (
            board, trading_date,
            _float_or_none(record.get("indexValue")), _float_or_none(record.get("indexChange")),
            _float_or_none(record.get("indexChangePercentage")),
            _float_or_none(record.get("totalAdvanceStock")), _float_or_none(record.get("totalDeclineStock")),
            _float_or_none(record.get("totalNoChangeStock")),
            _float_or_none(record.get("totalCeilingStock") or record.get("totalCeiLingStock")),
            _float_or_none(record.get("totalFloorStock")),
            _float_or_none(record.get("totalMatch")), _float_or_none(record.get("totalMatchValue")),
            _float_or_none(record.get("totalBuyForeignValue")), _float_or_none(record.get("totalSellForeignValue")),
            _float_or_none(record.get("netPurchasesForeignValue")),
            "SSI", fetched_at,
        )
        with self.conn:
            self.conn.execute(
                f"INSERT OR REPLACE INTO market_summary VALUES ({', '.join('?' for _ in values)})", values
            )

    def load_market_summary(self, board: str) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM market_summary WHERE board = ? ORDER BY trading_date", self.conn, params=[board]
        )

    # ------------------------------------------------------------------ truy vết và nhật ký

    def save_raw(self, endpoint: str, params: dict[str, Any], payload: Any) -> None:
        """Lưu nguyên văn response SSI (dùng làm raw_hook của SSIClient)."""
        with self.conn:
            self.conn.execute(
                "INSERT INTO raw_responses (fetched_at, endpoint, params, payload) VALUES (?, ?, ?, ?)",
                (now_vn(), endpoint, json.dumps(params, ensure_ascii=False), json.dumps(payload, ensure_ascii=False)),
            )

    def log_fetch(self, entry: dict[str, Any]) -> None:
        """Ghi một dòng nhật ký cập nhật."""
        columns = [col for col in self._columns("fetch_log") if col != "id" and col in entry]
        with self.conn:
            self.conn.execute(
                f"INSERT INTO fetch_log ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                [entry[col] for col in columns],
            )

    def load_fetch_log(self, limit: int = 100) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM fetch_log ORDER BY id DESC LIMIT ?", self.conn, params=[limit]
        )


def _float_or_none(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None
