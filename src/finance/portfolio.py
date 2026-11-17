"""
Danh mục đầu tư: đọc file danh mục, kiểm tra hợp lệ và định giá theo giá hiện tại.

Định dạng file CSV danh mục (mỗi dòng một mã; dòng CASH là tiền mặt, ghi số tiền ở cột quantity):
    symbol,quantity,avg_cost
    FPT,3000,48000
    VCB,1000,60000
    CASH,50000000,

Danh mục do người dùng tự nhập. Sản phẩm KHÔNG đọc tài khoản chứng khoán thật,
nên không đụng tới dữ liệu cá nhân nhạy cảm (Mục 4 của đề).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

CASH_SYMBOL = "CASH"
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{3,10}$")


class PortfolioError(ValueError):
    """Danh mục nhập vào không hợp lệ."""


@dataclass
class Portfolio:
    holdings: pd.DataFrame   # cột: symbol, quantity, avg_cost
    cash: float = 0.0

    @property
    def symbols(self) -> list[str]:
        return self.holdings["symbol"].tolist()


def build_portfolio(rows: pd.DataFrame) -> Portfolio:
    """Kiểm tra và chuẩn hóa bảng danh mục (dùng chung cho file CSV và bảng nhập trên giao diện).

    - Mã viết hoa, bỏ khoảng trắng; mã phải gồm 3–10 ký tự chữ/số.
    - Số lượng phải là số dương; giá vốn để trống được (coi như chưa biết).
    - Một mã nhập nhiều dòng thì gộp lại, giá vốn tính bình quân gia quyền theo số lượng.
    """
    required = {"symbol", "quantity"}
    if not required.issubset(rows.columns):
        raise PortfolioError("Danh mục phải có cột symbol và quantity")

    frame = rows.copy()
    if "avg_cost" not in frame.columns:
        frame["avg_cost"] = None
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce")
    frame["avg_cost"] = pd.to_numeric(frame["avg_cost"], errors="coerce")
    frame = frame[frame["symbol"] != ""]

    cash_rows = frame["symbol"] == CASH_SYMBOL
    cash = float(frame.loc[cash_rows, "quantity"].fillna(0).sum())
    if cash < 0:
        raise PortfolioError("Tiền mặt không được âm")
    stocks = frame[~cash_rows]

    bad_symbols = [s for s in stocks["symbol"] if not SYMBOL_PATTERN.match(s)]
    if bad_symbols:
        raise PortfolioError(f"Mã không hợp lệ: {', '.join(bad_symbols)}")
    if stocks["quantity"].isna().any() or (stocks["quantity"] <= 0).any():
        raise PortfolioError("Số lượng cổ phiếu phải là số dương")
    if (stocks["avg_cost"] < 0).any():
        raise PortfolioError("Giá vốn không được âm")
    if stocks.empty:
        raise PortfolioError("Danh mục chưa có cổ phiếu nào")

    # Gộp các dòng trùng mã; giá vốn bình quân gia quyền theo số lượng
    stocks = stocks.assign(cost_value=stocks["quantity"] * stocks["avg_cost"])
    grouped = stocks.groupby("symbol", as_index=False, sort=False).agg(
        quantity=("quantity", "sum"), cost_value=("cost_value", "sum"), known_cost=("avg_cost", "count")
    )
    grouped["avg_cost"] = (grouped["cost_value"] / grouped["quantity"]).where(grouped["known_cost"] > 0)
    holdings = grouped[["symbol", "quantity", "avg_cost"]].reset_index(drop=True)
    return Portfolio(holdings=holdings, cash=cash)


def load_portfolio_csv(path: Path | str) -> Portfolio:
    """Đọc danh mục từ file CSV."""
    try:
        rows = pd.read_csv(path, dtype={"symbol": str})
    except FileNotFoundError as exc:
        raise PortfolioError(f"Không tìm thấy file danh mục: {path}") from exc
    return build_portfolio(rows)


def value_portfolio(portfolio: Portfolio, latest_prices: pd.Series) -> tuple[pd.DataFrame, dict[str, float]]:
    """Định giá danh mục theo giá đóng cửa gần nhất.

    Trả về:
        - bảng từng mã: giá hiện tại, giá trị thị trường, lãi/lỗ chưa thực hiện,
          tỷ trọng trên tổng tài sản (có tính tiền mặt) và trên phần cổ phiếu;
        - tổng: giá trị cổ phiếu, tiền mặt, tổng tài sản.
    Mã không có giá (chưa có dữ liệu) bị loại khỏi phép tính và được báo ở cột has_price.
    """
    table = portfolio.holdings.copy()
    table["price"] = table["symbol"].map(latest_prices)
    table["has_price"] = table["price"].notna()
    table["market_value"] = table["quantity"] * table["price"]
    table["cost_value"] = table["quantity"] * table["avg_cost"]
    table["pnl"] = table["market_value"] - table["cost_value"]
    table["pnl_pct"] = table["pnl"] / table["cost_value"]

    equity_value = float(table["market_value"].sum(skipna=True))
    total_value = equity_value + portfolio.cash
    table["weight_total"] = table["market_value"] / total_value if total_value > 0 else float("nan")
    table["weight_equity"] = table["market_value"] / equity_value if equity_value > 0 else float("nan")

    totals = {
        "equity_value": equity_value,
        "cash": portfolio.cash,
        "total_value": total_value,
        "cash_weight": portfolio.cash / total_value if total_value > 0 else float("nan"),
        "pnl": float(table["pnl"].sum(skipna=True)),
    }
    return table, totals
