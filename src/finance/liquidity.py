"""
Thanh khoản của danh mục: cần bao nhiêu ngày để bán hết mà không làm giá biến động mạnh.

Phương pháp:
    - ADV (Average Daily Volume): khối lượng khớp lệnh trung bình 20 phiên gần nhất.
    - Giả định tỷ lệ tham gia: mỗi phiên chỉ bán tối đa p% khối lượng của thị trường (mặc định 20%)
      để không tự đẩy giá xuống. Đây là giả định thực hành phổ biến, người dùng chỉnh được trên giao diện.
    - Số phiên cần để bán hết = số cổ phiếu nắm giữ / (p × ADV), làm tròn lên.
    - Số ngày làm việc để có tiền = số phiên bán + 2 ngày thanh toán (chu kỳ T+2 của Việt Nam).

Phân loại theo SEC Rule 22e-4 (17 CFR 270.22e-4) - "chuyển thành tiền" nghĩa là bán VÀ đã thanh toán:
    - Thanh khoản cao:       có tiền trong <= 3 ngày làm việc
    - Thanh khoản trung bình: có tiền trong <= 7 ngày lịch (quy đổi <= 5 ngày làm việc)
    - Thanh khoản thấp:       lâu hơn
    Quy tắc này cũng giới hạn tài sản kém thanh khoản không quá 15% danh mục.

Tài liệu:
    U.S. Securities and Exchange Commission. (2016). Investment company liquidity risk management
        programs (Rule 22e-4, 17 CFR 270.22e-4).
"""
from __future__ import annotations

import math

import pandas as pd

ADV_WINDOW = 20
DEFAULT_PARTICIPATION = 0.20
SETTLEMENT_DAYS = 2            # thanh toán T+2
HIGH_LIQUIDITY_DAYS = 3        # SEC: 3 ngày làm việc
MODERATE_LIQUIDITY_DAYS = 5    # SEC: 7 ngày lịch ~ 5 ngày làm việc
ILLIQUID_SHARE_LIMIT = 0.15    # SEC: không quá 15% tài sản kém thanh khoản

BUCKET_HIGH = "Cao"
BUCKET_MODERATE = "Trung bình"
BUCKET_LOW = "Thấp"


def average_daily_volume(volume: pd.DataFrame, window: int = ADV_WINDOW) -> pd.Series:
    """Khối lượng trung bình `window` phiên gần nhất của từng mã (cột = mã, dòng = ngày)."""
    return volume.tail(window).mean(skipna=True)


def sessions_to_sell(quantity: float, adv: float, participation: float = DEFAULT_PARTICIPATION) -> float:
    """Số phiên cần để bán hết `quantity` cổ phiếu khi mỗi phiên chỉ bán `participation` × ADV."""
    if quantity <= 0:
        return 0.0
    if adv is None or not adv > 0 or participation <= 0:
        return math.inf
    return float(math.ceil(quantity / (participation * adv)))


def liquidity_bucket(days_to_cash: float) -> str:
    """Phân loại thanh khoản theo SEC Rule 22e-4."""
    if days_to_cash <= HIGH_LIQUIDITY_DAYS:
        return BUCKET_HIGH
    if days_to_cash <= MODERATE_LIQUIDITY_DAYS:
        return BUCKET_MODERATE
    return BUCKET_LOW


def liquidity_table(valuation: pd.DataFrame, adv: pd.Series,
                    participation: float = DEFAULT_PARTICIPATION) -> pd.DataFrame:
    """Bảng thanh khoản từng mã: ADV, % ADV đang nắm giữ, số phiên bán, số ngày có tiền, phân loại."""
    table = valuation[["symbol", "quantity", "market_value", "weight_total"]].copy()
    table["adv"] = table["symbol"].map(adv)
    table["position_pct_adv"] = table["quantity"] / table["adv"]
    table["sessions_to_sell"] = [
        sessions_to_sell(q, a, participation) for q, a in zip(table["quantity"], table["adv"])
    ]
    table["days_to_cash"] = table["sessions_to_sell"] + SETTLEMENT_DAYS
    table["bucket"] = table["days_to_cash"].map(liquidity_bucket)
    return table


def illiquid_share(table: pd.DataFrame) -> float:
    """Tỷ trọng (trên tổng tài sản) của các mã thanh khoản thấp."""
    return float(table.loc[table["bucket"] == BUCKET_LOW, "weight_total"].sum())
