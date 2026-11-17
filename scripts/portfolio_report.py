"""
In báo cáo sức khỏe danh mục ra màn hình (bản dòng lệnh của phần phân tích trên giao diện).

Cách chạy:
    python scripts/portfolio_report.py                                   # danh mục minh họa
    python scripts/portfolio_report.py --portfolio duong_dan/danh_muc.csv
    python scripts/portfolio_report.py --participation 0.1               # giả định bán tối đa 10% ADV/phiên
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src import config  # noqa: E402
from src.data.storage import Storage  # noqa: E402
from src.finance.health import DISCLAIMER, build_health_report, pct, vnd  # noqa: E402
from src.finance.market_data import load_market_data  # noqa: E402
from src.finance.portfolio import PortfolioError, load_portfolio_csv  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Báo cáo sức khỏe danh mục")
    parser.add_argument("--portfolio", default=str(config.SAMPLE_DIR / "demo_portfolio.csv"))
    parser.add_argument("--participation", type=float, default=0.2, help="tỷ lệ tối đa của ADV bán mỗi phiên")
    args = parser.parse_args()

    try:
        portfolio = load_portfolio_csv(args.portfolio)
    except PortfolioError as exc:
        sys.exit(f"[LỖI] {exc}")

    with Storage() as storage:
        market = load_market_data(storage, portfolio.symbols)
    report = build_health_report(portfolio, market, participation=args.participation)

    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 120)
    print(f"\n{DISCLAIMER}")
    print(f"Dữ liệu đến phiên: {market.last_trading_date} | cập nhật lúc: {market.last_fetched_at} | nguồn: SSI FastConnect")
    for note in report.notes:
        print(f"[!] {note}")

    t = report.totals
    print(f"\n=== DANH MỤC === Tổng tài sản {vnd(t['total_value'])} | cổ phiếu {vnd(t['equity_value'])} "
          f"| tiền mặt {vnd(t['cash'])} ({pct(t['cash_weight'])}) | lãi/lỗ chưa thực hiện {vnd(t['pnl'])}")
    view = report.valuation[["symbol", "quantity", "price", "market_value", "weight_total", "pnl_pct"]].copy()
    view["weight_total"] = view["weight_total"].map(pct)
    view["pnl_pct"] = view["pnl_pct"].map(pct)
    print(view.to_string(index=False))

    print("\n=== TỶ TRỌNG THEO NGÀNH (phần cổ phiếu) ===")
    print(report.sectors.map(pct).to_string())

    print("\n=== THANH KHOẢN ===")
    liq = report.liquidity[["symbol", "quantity", "adv", "position_pct_adv", "sessions_to_sell", "days_to_cash", "bucket"]].copy()
    liq["adv"] = liq["adv"].map(lambda v: f"{v:,.0f}".replace(",", "."))
    liq["position_pct_adv"] = liq["position_pct_adv"].map(lambda v: pct(v, 2))
    for column in ("sessions_to_sell", "days_to_cash"):
        liq[column] = liq[column].map(lambda v: "không bán được" if v == float("inf") else f"{v:.0f}")
    print(liq.rename(columns={"adv": "KL TB 20 phiên", "position_pct_adv": "% KL TB đang nắm",
                              "sessions_to_sell": "số phiên bán", "days_to_cash": "ngày có tiền",
                              "bucket": "thanh khoản"}).to_string(index=False))

    print("\n=== KẾT QUẢ KIỂM TRA ===")
    for check in report.checks:
        print(f"[{check.status}] {check.group} - {check.name}: {check.value} (ngưỡng: {check.threshold})")
        print(f"      {check.explanation}")
        if check.source:
            print(f"      Cơ sở: {check.source}")


if __name__ == "__main__":
    main()
