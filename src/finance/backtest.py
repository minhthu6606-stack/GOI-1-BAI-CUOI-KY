"""
Kiểm định ngoài mẫu (backtest) cho VaR lịch sử: mô hình có dự báo đúng mức lỗ hay không.

Cách làm (cửa sổ trượt, không nhìn trước tương lai):
    - Với mỗi ngày t, tính VaR_t chỉ từ `window` lợi suất TRƯỚC ngày t (giống hệt cách ứng dụng tính VaR hôm nay).
    - Ngày t là một "lần vượt VaR" nếu lợi suất thực tế r_t < −VaR_t (lỗ nhiều hơn mức VaR dự báo).
    - VaR 95% đúng thì số lần vượt xấp xỉ 5% số ngày kiểm định.

Hai kiểm định thống kê:
    1. Kupiec (1995) - tỷ lệ vượt (POF, proportion of failures):
       H0: tỷ lệ vượt thực tế = p = 1 − độ tin cậy.
       LR_pof = −2·ln[(1−p)^(n−x)·p^x] + 2·ln[(1−x/n)^(n−x)·(x/n)^x]  ~ χ²(1)
    2. Christoffersen (1998) - tính độc lập: các lần vượt có dồn cục (ngày này vượt thì ngày sau dễ vượt) không?
       So xác suất vượt sau một ngày không vượt (π0) với sau một ngày vượt (π1).  LR_ind ~ χ²(1)
    p-value ≥ 5% -> không bác bỏ H0 -> mô hình chấp nhận được.

Tài liệu:
    Kupiec, P. H. (1995). Techniques for verifying the accuracy of risk measurement models.
        The Journal of Derivatives, 3(2), 73–84.
    Christoffersen, P. F. (1998). Evaluating interval forecasts. International Economic Review, 39(4), 841–862.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

from src.finance.risk import VAR_CONFIDENCE, VAR_WINDOW

SIGNIFICANCE = 0.05


@dataclass
class BacktestResult:
    observations: int            # số ngày kiểm định
    exceptions: int              # số lần lỗ vượt VaR
    expected_rate: float         # tỷ lệ kỳ vọng (vd 0.05)
    lr_pof: float
    p_pof: float
    lr_ind: float
    p_ind: float
    series: pd.DataFrame = field(default_factory=pd.DataFrame)   # cột: return, var (tổn thất dương), exception

    @property
    def exception_rate(self) -> float:
        return self.exceptions / self.observations if self.observations else float("nan")

    @property
    def expected_exceptions(self) -> float:
        return self.expected_rate * self.observations

    @property
    def passes_pof(self) -> bool:
        return self.p_pof == self.p_pof and self.p_pof >= SIGNIFICANCE

    @property
    def passes_independence(self) -> bool:
        return self.p_ind != self.p_ind or self.p_ind >= SIGNIFICANCE   # không đủ dữ liệu thì không bác bỏ

    @property
    def too_few_exceptions(self) -> bool:
        """Kupiec bác bỏ vì vượt ÍT hơn kỳ vọng: VaR đang thận trọng (ước lượng lỗ cao hơn thực tế), không nguy hiểm.

        Kiểm định Kupiec là hai phía: bác bỏ cả khi vượt quá nhiều (đánh giá thấp rủi ro - nguy hiểm) lẫn khi vượt
        quá ít (đánh giá quá cao rủi ro - chỉ kém chính xác). Cần tách hai trường hợp để cảnh báo đúng chiều.
        """
        return not self.passes_pof and self.exception_rate < self.expected_rate


def chi2_1_pvalue(statistic: float) -> float:
    """p-value của phân phối Khi bình phương 1 bậc tự do: P(χ²₁ > s) = erfc(√(s/2))."""
    if statistic != statistic:
        return float("nan")
    return math.erfc(math.sqrt(max(statistic, 0.0) / 2))


def _xlogy(x: float, y: float) -> float:
    """x·ln(y), quy ước 0·ln(0) = 0."""
    return 0.0 if x == 0 else x * math.log(y)


def kupiec_pof(observations: int, exceptions: int, p: float) -> tuple[float, float]:
    """Thống kê LR và p-value của kiểm định Kupiec."""
    n, x = observations, exceptions
    if n <= 0:
        return float("nan"), float("nan")
    rate = x / n
    log_h0 = _xlogy(n - x, 1 - p) + _xlogy(x, p)
    log_h1 = _xlogy(n - x, 1 - rate) + _xlogy(x, rate)
    statistic = -2 * (log_h0 - log_h1)
    return statistic, chi2_1_pvalue(statistic)


def christoffersen_independence(hits: pd.Series) -> tuple[float, float]:
    """Thống kê LR và p-value của kiểm định độc lập Christoffersen (chuỗi 0/1 các lần vượt)."""
    values = hits.astype(int).tolist()
    pairs = list(zip(values[:-1], values[1:]))
    n00 = sum(1 for a, b in pairs if a == 0 and b == 0)
    n01 = sum(1 for a, b in pairs if a == 0 and b == 1)
    n10 = sum(1 for a, b in pairs if a == 1 and b == 0)
    n11 = sum(1 for a, b in pairs if a == 1 and b == 1)
    if (n01 + n11) == 0 or (n00 + n10) == 0 or (n00 + n01) == 0:
        return float("nan"), float("nan")
    pi0 = n01 / (n00 + n01)
    pi1 = n11 / (n10 + n11) if (n10 + n11) else 0.0
    pi = (n01 + n11) / (n00 + n01 + n10 + n11)
    log_h0 = _xlogy(n00 + n10, 1 - pi) + _xlogy(n01 + n11, pi)
    log_h1 = _xlogy(n00, 1 - pi0) + _xlogy(n01, pi0) + _xlogy(n10, 1 - pi1) + _xlogy(n11, pi1)
    statistic = -2 * (log_h0 - log_h1)
    return statistic, chi2_1_pvalue(statistic)


def backtest_var(returns: pd.Series, confidence: float = VAR_CONFIDENCE, window: int = VAR_WINDOW) -> BacktestResult:
    """Kiểm định VaR lịch sử bằng cửa sổ trượt `window` phiên trên chuỗi lợi suất ngày."""
    returns = returns.dropna()
    p = 1 - confidence
    if len(returns) <= window:
        return BacktestResult(0, 0, p, float("nan"), float("nan"), float("nan"), float("nan"))
    # VaR của ngày t dùng các lợi suất t-window ... t-1 (shift(1): không dùng chính ngày t)
    var = -returns.rolling(window).quantile(p).shift(1)
    frame = pd.DataFrame({"return": returns, "var": var}).dropna()
    frame["exception"] = frame["return"] < -frame["var"]
    n, x = len(frame), int(frame["exception"].sum())
    lr_pof, p_pof = kupiec_pof(n, x, p)
    lr_ind, p_ind = christoffersen_independence(frame["exception"])
    return BacktestResult(n, x, p, lr_pof, p_pof, lr_ind, p_ind, frame)
