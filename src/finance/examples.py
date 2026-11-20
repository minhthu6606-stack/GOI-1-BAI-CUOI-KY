"""
Danh mục ví dụ: 3 tình huống điển hình của nhà đầu tư cá nhân mới, cùng quy mô để dễ so sánh.

Đây là danh mục GIẢ ĐỊNH (không phải tài khoản thật của ai). Giá là giá đóng cửa thật từ SSI ở phiên mới nhất
trong kho; số lượng được tính từ tỷ trọng mục tiêu rồi làm tròn theo lô 100 cổ phiếu, giá vốn = giá phiên đó
(nên lãi/lỗ bằng 0 lúc tạo); làm tròn xuống theo lô nên tỷ trọng thật ≤ mục tiêu. Các danh mục được chọn theo CẤU TRÚC, không chỉnh để ra kết quả đẹp:

    A. Người mới bắt đầu   4 mã ở 4 ngành, mỗi mã ~22,5%, tiền mặt ~10%
                           (nhà đầu tư cá nhân thường giữ ít mã - Goetzmann & Kumar, 2008)
    B. Dồn vào ngân hàng   4 mã cùng ngành ngân hàng, mỗi mã ~22,5%, tiền mặt ~10%
    C. Đa dạng hơn         8 mã ở 7 ngành, mỗi mã ~10%, tiền mặt ~20%

Quy mô 100 triệu đồng là giả định (chưa có thống kê chính thức về quy mô tài khoản nhà đầu tư mới).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

EXAMPLE_TOTAL = 100_000_000   # đồng
LOT_SIZE = 100                # lô chẵn trên HOSE


@dataclass(frozen=True)
class Example:
    key: str
    title: str
    description: str
    weights: dict[str, float]   # tỷ trọng mục tiêu trên tổng tài sản; phần còn lại là tiền mặt


EXAMPLES: dict[str, Example] = {
    "beginner": Example(
        "beginner", "Người mới bắt đầu", "4 mã ở 4 ngành, mỗi mã khoảng 22%, giữ 10% tiền mặt.",
        {"FPT": 0.225, "MBB": 0.225, "HPG": 0.225, "MWG": 0.225},
    ),
    "banks": Example(
        "banks", "Dồn vào ngân hàng", "4 mã cùng ngành ngân hàng, mỗi mã khoảng 22%, giữ 10% tiền mặt.",
        {"VCB": 0.225, "MBB": 0.225, "ACB": 0.225, "TCB": 0.225},
    ),
    "diversified": Example(
        "diversified", "Đa dạng hơn", "8 mã ở 7 ngành, mỗi mã khoảng 10%, giữ 20% tiền mặt.",
        {"FPT": 0.10, "VCB": 0.10, "MBB": 0.10, "HPG": 0.10, "MWG": 0.10, "VNM": 0.10, "GAS": 0.10, "SSI": 0.10},
    ),
}
DEFAULT_EXAMPLE = "beginner"


def example_symbols() -> list[str]:
    """Mọi mã xuất hiện trong các danh mục ví dụ (để cập nhật dữ liệu và xuất bản chốt)."""
    return list(dict.fromkeys(s for ex in EXAMPLES.values() for s in ex.weights))


def round_to_lot(value: float, price: float, lot: int = LOT_SIZE) -> int:
    """Số cổ phiếu theo bội số của lô, làm tròn XUỐNG để không vượt tỷ trọng mục tiêu (tối thiểu 1 lô).

    Làm tròn xuống tránh trường hợp một mã mục tiêu 10% bị đẩy lên 12% chỉ vì làm tròn lô, rồi bị báo vượt
    mốc 10% một cách oan; phần lẻ còn lại nằm ở tiền mặt.
    """
    return max(lot, int(value / price // lot) * lot)


def build_example(key: str, latest_prices: pd.Series, total: float = EXAMPLE_TOTAL) -> tuple[pd.DataFrame, float]:
    """Tạo bảng danh mục (symbol, quantity, avg_cost) và tiền mặt cho danh mục ví dụ `key`.

    Mã chưa có giá trong kho thì bỏ qua (phần tiền đó cộng vào tiền mặt). Tiền mặt = tổng - giá trị cổ phiếu,
    không âm (làm tròn lô có thể làm tổng lệch vài trăm nghìn so với 100 triệu).
    """
    example = EXAMPLES[key]
    rows = []
    for symbol, weight in example.weights.items():
        price = latest_prices.get(symbol)
        if price is None or not price == price or price <= 0:
            continue
        rows.append({"symbol": symbol, "quantity": round_to_lot(weight * total, float(price)),
                     "avg_cost": float(price)})
    frame = pd.DataFrame(rows, columns=["symbol", "quantity", "avg_cost"])
    invested = float((frame["quantity"] * frame["avg_cost"]).sum()) if not frame.empty else 0.0
    return frame, max(0.0, round(total - invested, -3))
