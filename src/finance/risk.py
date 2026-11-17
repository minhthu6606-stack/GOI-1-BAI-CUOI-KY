"""
Các thước đo rủi ro thị trường của danh mục.

Giả định chung: danh mục giữ nguyên tỷ trọng hiện tại trong quá khứ (tỷ trọng cố định,
tái cân bằng hằng ngày). Đây là cách thông dụng để hỏi "danh mục HIỆN TẠI rủi ro đến đâu",
không phải tái hiện lãi/lỗ thực tế đã qua. Tiền mặt coi như lợi suất bằng 0.

Lợi suất tính từ giá đóng cửa ĐÃ ĐIỀU CHỈNH của SSI (đã kiểm chứng khớp với phần trăm thay đổi
SSI công bố), nên không bị méo bởi cổ tức hay cổ phiếu thưởng.

Thước đo:
    - Độ biến động năm hóa = độ lệch chuẩn lợi suất ngày × căn(252).
    - Beta so với VN-Index = Cov(r_danh mục, r_thị trường) / Var(r_thị trường).
    - VaR lịch sử (mô phỏng lịch sử): tổn thất 1 ngày không bị vượt quá với độ tin cậy 95%,
      lấy phân vị 5% của 250 lợi suất ngày gần nhất (Jorion, 2007).
    - Mức sụt giảm tối đa (maximum drawdown): mức giảm lớn nhất từ đỉnh xuống đáy.

Tài liệu:
    Jorion, P. (2007). Value at risk: The new benchmark for managing financial risk (3rd ed.). McGraw-Hill.
    Sharpe, W. F. (1963). A simplified model for portfolio analysis. Management Science, 9(2), 277–293.
    Sharpe, W. F. (1964). Capital asset prices: A theory of market equilibrium under conditions of risk.
        The Journal of Finance, 19(3), 425–442.
"""
from __future__ import annotations

import math

import pandas as pd

TRADING_DAYS_PER_YEAR = 252
VAR_CONFIDENCE = 0.95
VAR_WINDOW = 250
BETA_WINDOW = 250


def daily_returns(close: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Lợi suất ngày = giá hôm nay / giá phiên trước − 1. Bỏ phiên đầu tiên (không có phiên trước)."""
    return close.pct_change(fill_method=None).iloc[1:]


def portfolio_returns(returns: pd.DataFrame, weights_total: pd.Series) -> pd.Series:
    """Lợi suất ngày của danh mục với tỷ trọng cố định trên tổng tài sản (phần tiền mặt có lợi suất 0).

    Phiên nào một mã thiếu dữ liệu thì phiên đó bị bỏ, để không tính sai bằng cách coi lợi suất = 0.
    """
    weights = weights_total.dropna()
    columns = [symbol for symbol in weights.index if symbol in returns.columns]
    aligned = returns[columns].dropna(how="any")
    return aligned.mul(weights[columns], axis=1).sum(axis=1)


def annualized_volatility(returns: pd.Series, periods: int = TRADING_DAYS_PER_YEAR) -> float:
    returns = returns.dropna()
    if len(returns) < 2:
        return float("nan")
    return float(returns.std(ddof=1) * math.sqrt(periods))


def beta(asset_returns: pd.Series, market_returns: pd.Series, window: int = BETA_WINDOW) -> float:
    """Beta theo `window` phiên chung gần nhất của tài sản và thị trường."""
    joined = pd.concat([asset_returns, market_returns], axis=1, join="inner").dropna().tail(window)
    if len(joined) < 20:
        return float("nan")
    market_var = joined.iloc[:, 1].var(ddof=1)
    if market_var == 0:
        return float("nan")
    return float(joined.iloc[:, 0].cov(joined.iloc[:, 1]) / market_var)


def r_squared(asset_returns: pd.Series, market_returns: pd.Series, window: int = BETA_WINDOW) -> float:
    """Tỷ lệ phương sai của tài sản được giải thích bởi thị trường (R² của mô hình chỉ số đơn).

    Theo mô hình chỉ số đơn (Sharpe, 1963): σ²_danh mục = β²σ²_thị trường + σ²_riêng.
    R² = β²σ²_thị trường / σ²_danh mục = bình phương hệ số tương quan. Phần (1 − R²) là rủi ro
    riêng của từng mã - phần có thể giảm bằng đa dạng hóa.
    """
    joined = pd.concat([asset_returns, market_returns], axis=1, join="inner").dropna().tail(window)
    if len(joined) < 20:
        return float("nan")
    correlation = joined.iloc[:, 0].corr(joined.iloc[:, 1])
    return float(correlation ** 2)


def historical_var(returns: pd.Series, confidence: float = VAR_CONFIDENCE, window: int = VAR_WINDOW) -> float:
    """VaR lịch sử 1 ngày, biểu diễn dưới dạng TỶ LỆ TỔN THẤT dương (vd 0.025 = mất 2,5%).

    Lấy phân vị (1 − confidence) của `window` lợi suất gần nhất rồi đổi dấu.
    """
    sample = returns.dropna().tail(window)
    if len(sample) < window // 2:
        return float("nan")
    return float(-sample.quantile(1 - confidence))


def max_drawdown(returns: pd.Series) -> float:
    """Mức sụt giảm tối đa từ đỉnh, dưới dạng số âm (vd −0.30 = giảm 30% từ đỉnh)."""
    returns = returns.dropna()
    if returns.empty:
        return float("nan")
    wealth = (1 + returns).cumprod()
    peak = wealth.cummax().clip(lower=1.0)  # tính cả mốc ban đầu = 1
    return float((wealth / peak - 1).min())
