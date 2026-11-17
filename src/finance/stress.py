"""
Kịch bản căng thẳng (stress test): nếu mọi mã trong danh mục cùng giảm sàn thì mất bao nhiêu.

Đặc thù thị trường Việt Nam: giá mỗi phiên bị giới hạn trong biên độ quanh giá tham chiếu.
Biên độ cổ phiếu: HOSE ±7%, HNX ±10%, UPCoM ±15%.
Giá sàn = giá tham chiếu × (1 − biên độ), làm tròn LÊN tới bước giá gần nhất
(làm tròn lên để giá sàn không thấp hơn mức biên độ cho phép).
Bước giá HOSE: dưới 10.000đ là 10đ; 10.000–49.950đ là 50đ; từ 50.000đ là 100đ. HNX, UPCoM: 100đ.

Giả định: giá tham chiếu phiên kế tiếp = giá đóng cửa gần nhất (không có sự kiện quyền).
Kịch bản nhiều phiên áp dụng liên tiếp: giá sàn phiên trước làm giá tham chiếu phiên sau.
Đây là kịch bản cực đoan dùng để hình dung rủi ro đuôi, không phải dự báo.
"""
from __future__ import annotations

import math

import pandas as pd

PRICE_LIMITS = {"HOSE": 0.07, "HNX": 0.10, "UPCOM": 0.15}
DEFAULT_BOARD = "HOSE"


def tick_size(price: float, board: str) -> int:
    """Bước giá cổ phiếu theo sàn và mức giá."""
    if board.upper() != "HOSE":
        return 100
    if price < 10_000:
        return 10
    if price < 50_000:
        return 50
    return 100


def floor_price(reference: float, board: str) -> float:
    """Giá sàn của một phiên, làm tròn lên tới bước giá."""
    limit = PRICE_LIMITS.get(board.upper(), PRICE_LIMITS[DEFAULT_BOARD])
    raw = reference * (1 - limit)
    tick = tick_size(raw, board)
    return float(math.ceil(round(raw / tick, 9)) * tick)  # round(...) tránh sai số dấu phẩy động


def floor_scenario(valuation: pd.DataFrame, boards: pd.Series, sessions: int = 1) -> tuple[pd.DataFrame, dict]:
    """Tổn thất nếu mọi mã giảm sàn liên tiếp `sessions` phiên.

    `boards`: sàn niêm yết của từng mã (index = mã). Mã không rõ sàn coi như HOSE.
    """
    table = valuation.loc[valuation["has_price"], ["symbol", "quantity", "price", "market_value"]].copy()
    table["board"] = table["symbol"].map(boards).fillna(DEFAULT_BOARD).str.upper()

    stressed = []
    for price, board in zip(table["price"], table["board"]):
        current = price
        for _ in range(sessions):
            current = floor_price(current, board)
        stressed.append(current)
    table["stressed_price"] = stressed
    table["loss"] = (table["price"] - table["stressed_price"]) * table["quantity"]
    table["loss_pct"] = table["loss"] / table["market_value"]

    total_loss = float(table["loss"].sum())
    return table, {"sessions": sessions, "total_loss": total_loss}
