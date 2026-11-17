"""
Tạo danh mục MINH HỌA (không phải tài khoản thật) từ giá đóng cửa mới nhất trong kho.

Thiết kế có chủ đích để khi trình diễn, sản phẩm có đủ các trạng thái:
    - FPT chiếm ~30% tổng tài sản -> vượt chuẩn 10%/mã của UCITS;
    - 2 mã ngân hàng (VCB, MBB) -> thấy rõ tập trung theo ngành;
    - ~10% tiền mặt.
Số cổ phiếu làm tròn xuống theo lô 100. Giá vốn giả định = giá đóng cửa (đã điều chỉnh)
khoảng 60 phiên trước, làm tròn theo bước giá, để có lãi/lỗ ban đầu.

Cách chạy (sau khi đã chạy scripts/update_data.py):
    python scripts/make_demo_portfolio.py
Kết quả: data_sample/demo_portfolio.csv
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src import config  # noqa: E402
from src.data.storage import Storage  # noqa: E402
from src.finance.stress import tick_size  # noqa: E402

TOTAL_CAPITAL = 500_000_000  # 500 triệu đồng
TARGET_WEIGHTS = {"FPT": 0.30, "VCB": 0.15, "MBB": 0.15, "HPG": 0.12, "SSI": 0.10, "MWG": 0.08}
LOT_SIZE = 100
COST_LOOKBACK_SESSIONS = 60
OUTPUT = config.SAMPLE_DIR / "demo_portfolio.csv"


def main() -> None:
    rows = []
    with Storage() as storage:
        for symbol, weight in TARGET_WEIGHTS.items():
            history = storage.load_daily("stock_daily", symbol)
            if history.empty:
                sys.exit(f"[LỖI] Kho chưa có dữ liệu {symbol}. Hãy chạy: python scripts/update_data.py")
            price = float(history["close"].iloc[-1])
            quantity = math.floor(TOTAL_CAPITAL * weight / price / LOT_SIZE) * LOT_SIZE
            past = float(history["close"].iloc[-min(COST_LOOKBACK_SESSIONS, len(history))])
            tick = tick_size(past, "HOSE")
            avg_cost = round(past / tick) * tick
            rows.append({"symbol": symbol, "quantity": quantity, "avg_cost": avg_cost, "price": price})

    invested = sum(r["quantity"] * r["price"] for r in rows)
    rows.append({"symbol": "CASH", "quantity": round(TOTAL_CAPITAL - invested), "avg_cost": None, "price": None})

    config.SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame[["symbol", "quantity", "avg_cost"]].to_csv(OUTPUT, index=False)
    print(f"Đã tạo {OUTPUT} (giá hiện tại chỉ để tham khảo, không lưu vào file)")
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
