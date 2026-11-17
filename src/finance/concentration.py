"""
Đo mức độ tập trung của danh mục: theo từng mã và theo ngành.

Chỉ số và cơ sở:
    - HHI (Herfindahl–Hirschman) = tổng bình phương tỷ trọng. Danh mục chia đều N mã có HHI = 1/N.
    - Số mã hiệu dụng N_eff = 1 / HHI: danh mục "tương đương" với bao nhiêu mã chia đều.
      Ngưỡng tham khảo: Evans & Archer (1968) cho thấy phần lớn lợi ích đa dạng hóa đạt được
      với khoảng 10 cổ phiếu, nên N_eff < 10 được coi là chưa đa dạng hóa đủ, N_eff < 5 là tập trung cao.
    - Quy tắc 5/10/40 của UCITS (Chỉ thị EU 2009/65/EC, Điều 52): quỹ đại chúng không đầu tư quá
      10% tài sản vào một tổ chức phát hành; tổng các khoản vượt 5% không quá 40% tài sản.
      Dùng làm chuẩn tham chiếu của nhà đầu tư tổ chức, không phải quy định bắt buộc với cá nhân.
    - Tập trung ngành: không có quy định chuẩn cho cá nhân. Sản phẩm dùng quy tắc nghiệp vụ tự đặt:
      một ngành chiếm hơn 50% phần cổ phiếu nghĩa là quá nửa danh mục phụ thuộc vào cùng một nhóm
      yếu tố rủi ro ngành.

Tài liệu:
    Evans, J. L., & Archer, S. H. (1968). Diversification and the reduction of dispersion:
        An empirical analysis. The Journal of Finance, 23(5), 761–767.
    European Parliament and Council. (2009). Directive 2009/65/EC (UCITS), Article 52.
"""
from __future__ import annotations

import pandas as pd

UCITS_SINGLE_LIMIT = 0.10      # tối đa 10% tài sản cho một tổ chức phát hành
UCITS_LARGE_POSITION = 0.05    # khoản "lớn" là khoản vượt 5%
UCITS_AGGREGATE_LIMIT = 0.40   # tổng các khoản lớn không quá 40%
EFFECTIVE_N_WELL_DIVERSIFIED = 10
EFFECTIVE_N_CONCENTRATED = 5
SECTOR_LIMIT = 0.50            # quy tắc nghiệp vụ tự đặt


def hhi(weights: pd.Series) -> float:
    """Chỉ số HHI của các tỷ trọng (tự chuẩn hóa để tổng bằng 1). Trả NaN nếu không có tỷ trọng dương."""
    weights = weights.dropna()
    weights = weights[weights > 0]
    total = weights.sum()
    if total <= 0:
        return float("nan")
    normalized = weights / total
    return float((normalized ** 2).sum())


def effective_number(weights: pd.Series) -> float:
    """Số mã hiệu dụng N_eff = 1 / HHI."""
    value = hhi(weights)
    return 1 / value if value == value else float("nan")  # value == value là cách kiểm tra không phải NaN


def ucits_check(weights_total: pd.Series) -> dict[str, object]:
    """Đối chiếu tỷ trọng (trên TỔNG tài sản, có tính tiền mặt) với quy tắc 5/10/40.

    Trả về: mã có tỷ trọng lớn nhất, danh sách mã vượt 10%, tổng tỷ trọng các mã vượt 5%,
    và hai cờ vi phạm.
    """
    weights = weights_total.dropna()
    over_single = weights[weights > UCITS_SINGLE_LIMIT].sort_values(ascending=False)
    large_sum = float(weights[weights > UCITS_LARGE_POSITION].sum())
    return {
        "max_symbol": weights.idxmax() if not weights.empty else None,
        "max_weight": float(weights.max()) if not weights.empty else float("nan"),
        "over_single_limit": over_single.index.tolist(),
        "large_positions_sum": large_sum,
        "breach_single": not over_single.empty,
        "breach_aggregate": large_sum > UCITS_AGGREGATE_LIMIT,
    }


def sector_weights(valuation: pd.DataFrame, securities: pd.DataFrame) -> pd.Series:
    """Tỷ trọng từng ngành (theo phân ngành ICB của SSI) trên phần cổ phiếu của danh mục."""
    sectors = securities.set_index("symbol")["icb_name"] if not securities.empty else pd.Series(dtype=str)
    table = valuation[["symbol", "market_value"]].dropna()
    table = table.assign(sector=table["symbol"].map(sectors).fillna("Chưa rõ ngành"))
    by_sector = table.groupby("sector")["market_value"].sum()
    total = by_sector.sum()
    return (by_sector / total).sort_values(ascending=False) if total > 0 else by_sector
