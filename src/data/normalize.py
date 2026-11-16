"""
Chuẩn hóa dữ liệu SSI thành bảng sạch và kiểm tra chất lượng dữ liệu.

Dữ liệu SSI trả về mọi con số dưới dạng chuỗi, ngày dạng "YYYY/MM/DD" và không
sắp xếp thống nhất. Module này:
    - đổi tên trường sang tên tiếng Anh thống nhất, dạng snake_case;
    - đổi chuỗi sang số, ngày sang dạng ISO "YYYY-MM-DD";
    - loại bản ghi thiếu ngày/giá, giá không dương, bản ghi trùng ngày;
    - đánh dấu (không loại) bản ghi có giá đóng cửa nằm ngoài [giá thấp nhất, giá cao nhất];
    - sắp xếp tăng dần theo ngày;
    - trả kèm báo cáo chất lượng để ghi nhật ký và đưa vào phần kiểm chứng.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

# Tên trường SSI (securitiesSummary) -> tên chuẩn trong kho dữ liệu
STOCK_DAILY_FIELDS: dict[str, str] = {
    "tradingDate": "trading_date",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "average": "average",
    "priceChange": "price_change",
    "priceChangePercentage": "price_change_pct",
    "totalMatch": "volume",
    "totalMatchValue": "value",
    "totalDeal": "deal_volume",
    "totalDealValue": "deal_value",
    "totalForeignBuy": "foreign_buy_volume",
    "totalForeignBuyValue": "foreign_buy_value",
    "totalForeignSell": "foreign_sell_volume",
    "totalForeignSellValue": "foreign_sell_value",
    "remainForeignRoom": "foreign_room_remaining",
    "totalForeignRoom": "foreign_room_total",
}

# Tên trường SSI (ohlc) -> tên chuẩn
INDEX_DAILY_FIELDS: dict[str, str] = {
    "tradingDate": "trading_date",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
    "value": "value",
}

DATE_INPUT_FORMATS = ("%Y/%m/%d", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d %H:%M:%S")


@dataclass
class QualityReport:
    """Tóm tắt chất lượng của một lần chuẩn hóa."""

    total: int = 0                   # số bản ghi nhận vào
    kept: int = 0                    # số bản ghi giữ lại
    dropped_missing: int = 0         # thiếu ngày hoặc giá đóng cửa
    dropped_invalid: int = 0         # giá đóng cửa <= 0
    dropped_duplicate: int = 0       # trùng ngày giao dịch
    flagged: int = 0                 # giữ lại nhưng bị đánh dấu nghi vấn
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"nhận {self.total}, giữ {self.kept}, loại thiếu {self.dropped_missing}, "
            f"loại sai giá {self.dropped_invalid}, loại trùng {self.dropped_duplicate}, "
            f"đánh dấu nghi vấn {self.flagged}"
        )


def parse_ssi_date(text: Any) -> str | None:
    """Đổi ngày SSI (vd "2026/11/09") sang dạng ISO "2026-11-09". Trả None nếu không đọc được."""
    if text is None:
        return None
    text = str(text).strip()
    for fmt in DATE_INPUT_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def to_float(value: Any) -> float | None:
    """Đổi chuỗi số của SSI sang float. Chuỗi rỗng, None, "null" hoặc không phải số -> None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().replace(",", "")
        if text == "" or text.lower() in {"null", "none", "nan"}:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
    return None if math.isnan(number) or math.isinf(number) else number


def _to_frame(records: list[dict[str, Any]], field_map: dict[str, str], symbol: str) -> pd.DataFrame:
    """Đổi danh sách bản ghi SSI thành DataFrame với tên cột chuẩn và kiểu dữ liệu đúng."""
    rows = []
    for record in records:
        row: dict[str, Any] = {"symbol": symbol}
        for api_name, our_name in field_map.items():
            raw = record.get(api_name)
            row[our_name] = parse_ssi_date(raw) if our_name == "trading_date" else to_float(raw)
        rows.append(row)
    columns = ["symbol", *field_map.values()]
    return pd.DataFrame(rows, columns=columns)


def _clean(frame: pd.DataFrame, report: QualityReport) -> pd.DataFrame:
    """Các bước làm sạch dùng chung cho cổ phiếu và chỉ số."""
    report.total = len(frame)

    missing = frame["trading_date"].isna() | frame["close"].isna()
    report.dropped_missing = int(missing.sum())
    frame = frame[~missing]

    invalid = frame["close"] <= 0
    report.dropped_invalid = int(invalid.sum())
    frame = frame[~invalid]

    duplicated = frame.duplicated(subset="trading_date", keep="last")
    report.dropped_duplicate = int(duplicated.sum())
    frame = frame[~duplicated]

    # Giá đóng cửa phải nằm trong [thấp nhất, cao nhất]; nếu không thì đánh dấu để kiểm tra lại
    outside_range = (frame["high"].notna() & frame["low"].notna()) & (
        (frame["close"] > frame["high"]) | (frame["close"] < frame["low"]) | (frame["high"] < frame["low"])
    )
    frame = frame.assign(quality_flag=outside_range.map({True: "close_outside_high_low", False: ""}))
    report.flagged = int(outside_range.sum())

    frame = frame.sort_values("trading_date").reset_index(drop=True)
    report.kept = len(frame)
    return frame


def normalize_stock_daily(records: list[dict[str, Any]], symbol: str) -> tuple[pd.DataFrame, QualityReport]:
    """Chuẩn hóa dữ liệu theo phiên của một cổ phiếu (endpoint securitiesSummary).

    Quan sát dữ liệu SSI ngày 16/11/2026:
        - giá lịch sử (open/high/low/close) ĐÃ được điều chỉnh cho cổ tức, cổ phiếu thưởng
          (xuất hiện giá lẻ thập phân như 68151.954, trong khi giá thật trên HOSE là số nguyên);
        - price_change lại là số đồng THẬT, chưa điều chỉnh.
    Vì vậy không được lấy close - price_change. Cột reference_price được suy ra từ phần trăm
    thay đổi (không phụ thuộc thang giá):  reference_price = close / (1 + price_change_pct / 100),
    nên cùng thang với giá đóng cửa đã điều chỉnh.
    """
    report = QualityReport()
    frame = _clean(_to_frame(records, STOCK_DAILY_FIELDS, symbol), report)

    pct = frame["price_change_pct"]
    usable = pct.notna() & (pct > -100)
    frame["reference_price"] = (frame["close"] / (1 + pct / 100)).where(usable)
    missing_pct = int((~usable).sum())
    if missing_pct:
        report.notes.append(f"{missing_pct} phiên thiếu phần trăm thay đổi, không suy ra được giá tham chiếu")
    return frame, report


def find_missing_sessions(frame: pd.DataFrame, calendar_dates: list[str]) -> list[str]:
    """Liệt kê các phiên có trong lịch giao dịch nhưng thiếu trong dữ liệu của một mã.

    `calendar_dates` là danh sách ngày giao dịch chuẩn (lấy từ VN-Index). Chỉ xét trong khoảng
    từ phiên đầu tiên đến phiên cuối cùng mà mã có dữ liệu, để không tính nhầm các phiên trước
    ngày niêm yết.
    """
    if frame.empty:
        return []
    first, last = frame["trading_date"].min(), frame["trading_date"].max()
    have = set(frame["trading_date"])
    return sorted(day for day in calendar_dates if first <= day <= last and day not in have)


def normalize_index_daily(records: list[dict[str, Any]], index_code: str) -> tuple[pd.DataFrame, QualityReport]:
    """Chuẩn hóa nến ngày của một chỉ số (endpoint ohlc)."""
    report = QualityReport()
    frame = _clean(_to_frame(records, INDEX_DAILY_FIELDS, index_code), report)
    return frame, report
