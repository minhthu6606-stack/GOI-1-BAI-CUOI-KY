"""
Báo cáo kiểm chứng (đưa vào Mục 7 của báo cáo): ghi ra thư mục docs/kiem_chung/ ba file Markdown.

    chat_luong_du_lieu.md   mỗi mã: số phiên, phiên thiếu, dòng bị gắn cờ, giá đã điều chỉnh, đối chiếu lợi suất
    nhat_ky_thu_thap.md     số phiên dữ liệu trong kho; mỗi lần cập nhật: lúc nào, phiên nào, số chuỗi thành công/lỗi
    kiem_dinh_var.md        kiểm định ngoài mẫu VaR 95% của danh mục mặc định (Kupiec, Christoffersen)

Mọi con số đều tính từ kho dữ liệu thật (data/portfolio.db; nếu chưa có thì data_sample/sample.db).

Cách chạy:
    python scripts/verification_report.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src import config  # noqa: E402
from src.data.quality import collection_summary, quality_table, sessions_collected  # noqa: E402
from src.data.storage import Storage  # noqa: E402
from src.finance.health import build_health_report, num, pct  # noqa: E402
from src.finance.market_data import load_market_data  # noqa: E402
from src.finance.portfolio import load_portfolio_csv  # noqa: E402

OUT_DIR = config.PROJECT_ROOT / "docs" / "kiem_chung"


def _table(frame: pd.DataFrame) -> str:
    """Bảng Markdown đơn giản (không cần thư viện ngoài)."""
    header = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    line = "| " + " | ".join("---" for _ in frame.columns) + " |"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([header, line, *body])


def _header(title: str, db_path: Path) -> str:
    now = datetime.now(config.VN_TZ).strftime("%d/%m/%Y %H:%M")
    return f"# {title}\n\nTạo lúc {now} (giờ Việt Nam) từ kho `{db_path.relative_to(config.PROJECT_ROOT)}`.\n\n"


def main() -> None:
    db_path = config.DB_PATH if config.DB_PATH.exists() else config.SAMPLE_DB_PATH
    if not db_path.exists():
        sys.exit("[LỖI] Chưa có kho dữ liệu. Hãy chạy: python scripts/update_data.py")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with Storage(db_path) as storage:
        quality = quality_table(storage, config.TRACKED_SYMBOLS)
        summary = collection_summary(storage.load_fetch_log(limit=100_000), storage.trading_calendar(config.MARKET_INDEX))
        portfolio = load_portfolio_csv(config.DEMO_PORTFOLIO_PATH)
        market = load_market_data(storage, portfolio.symbols)
    report = build_health_report(portfolio, market)

    # 1. Chất lượng dữ liệu
    view = quality.rename(columns={
        "symbol": "Mã", "sessions": "Số phiên", "first": "Từ ngày", "last": "Đến ngày", "missing": "Phiên thiếu",
        "flagged": "Dòng bị gắn cờ", "adjusted": "Phiên có giá đã điều chỉnh", "cross_checked": "Số phiên đối chiếu",
        "cross_mismatch": "Lệch > 1 điểm %"})
    total_missing = int(quality.get("missing", pd.Series(dtype=int)).fillna(0).sum())
    total_mismatch = int(quality.get("cross_mismatch", pd.Series(dtype=int)).fillna(0).sum())
    text = (_header("Chất lượng dữ liệu", db_path)
            + "Đối chiếu: lợi suất tự tính từ giá đóng cửa đã điều chỉnh so với `priceChangePercentage` do SSI công bố; "
              "lệch quá 1 điểm phần trăm thì đếm là lệch. Phiên thiếu tính theo lịch giao dịch của VN-Index.\n\n"
            + _table(view) + f"\n\n**Tổng:** {len(quality)} mã, {total_missing} phiên thiếu, {total_mismatch} phiên lệch.\n")
    (OUT_DIR / "chat_luong_du_lieu.md").write_text(text, encoding="utf-8")

    # 2. Nhật ký thu thập
    sessions = sessions_collected(summary)
    log_view = pd.DataFrame({
        "Lúc tải (giờ VN)": summary["started_at"].str[:16].str.replace("T", " "),
        "Phiên": summary["session"], "Tải đúng ngày": summary["on_time"].map({True: "có", False: "tải bù"}),
        "Số chuỗi": summary["series"], "Thành công": summary["ok"], "Lỗi": summary["error"],
    })
    with Storage(db_path) as storage:
        calendar = storage.trading_calendar(config.MARKET_INDEX)
    span = f"từ {calendar[0]} đến {calendar[-1]}" if calendar else "chưa có"
    text = (_header("Nhật ký thu thập dữ liệu", db_path)
            + f"- Dữ liệu theo phiên trong kho, do mã nguồn tự tải từ SSI FastConnect và lưu kèm thời điểm tải: "
              f"**{len(calendar)} phiên giao dịch** ({span}).\n"
            + f"- Ứng dụng đã chạy cập nhật vào **{len(sessions)} phiên**: {', '.join(sessions) or 'chưa có'}.\n"
            + "- \"Tải bù\": lần tải diễn ra sau ngày của phiên (vd mở máy hôm sau); mỗi lần tải lại 14 ngày gần nhất "
              "nên không mất phiên nào.\n\n" + _table(log_view) + "\n")
    (OUT_DIR / "nhat_ky_thu_thap.md").write_text(text, encoding="utf-8")

    # 3. Kiểm định VaR
    bt = report.backtest
    pof_text = "Đạt" if bt.passes_pof else ("Không đạt - vượt ít hơn kỳ vọng (VaR thận trọng)"
                                              if bt.too_few_exceptions else "Không đạt - vượt nhiều hơn kỳ vọng")
    verdict = (pof_text, "Đạt" if bt.passes_independence else "Không đạt - các lần vượt dồn cục")
    text = (_header("Kiểm định ngoài mẫu VaR 95% (danh mục mặc định)", db_path)
            + "VaR lịch sử 1 ngày, cửa sổ trượt 250 phiên; VaR của mỗi ngày chỉ dùng dữ liệu trước ngày đó. "
              "Danh mục giữ tỷ trọng hiện tại trong suốt giai đoạn.\n\n"
            + _table(pd.DataFrame([
                ["Số ngày kiểm định", bt.observations],
                ["Từ ngày – đến ngày", f"{bt.series.index.min()} – {bt.series.index.max()}" if bt.observations else "—"],
                ["Số lần lỗ vượt VaR", bt.exceptions],
                ["Tỷ lệ vượt thực tế / kỳ vọng", f"{pct(bt.exception_rate, 2)} / {pct(bt.expected_rate, 0)}"],
                ["Kupiec (1995): LR / p-value / kết luận", f"{num(bt.lr_pof, 3)} / {num(bt.p_pof, 3)} / {verdict[0]}"],
                ["Christoffersen (1998): LR / p-value / kết luận",
                 f"{num(bt.lr_ind, 3)} / {num(bt.p_ind, 3)} / {verdict[1]}"],
            ], columns=["Chỉ tiêu", "Giá trị"])) + "\n\nMức ý nghĩa 5%: p-value ≥ 0,05 thì không bác bỏ giả thuyết mô hình đúng.\n")
    (OUT_DIR / "kiem_dinh_var.md").write_text(text, encoding="utf-8")

    print(f"Đã ghi 3 file vào {OUT_DIR}")
    print(f"   Chất lượng: {len(quality)} mã, {total_missing} phiên thiếu, {total_mismatch} phiên lệch > 1 điểm %")
    print(f"   Thu thập: kho có {len(calendar)} phiên ({span}); ứng dụng đã chạy cập nhật vào {len(sessions)} phiên "
          f"({', '.join(sessions)})")
    print(f"   Kiểm định VaR: {bt.exceptions}/{bt.observations} ngày vượt ({pct(bt.exception_rate, 2)}), "
          f"Kupiec p = {num(bt.p_pof, 3)} ({verdict[0]}), Christoffersen p = {num(bt.p_ind, 3)} ({verdict[1]})")


if __name__ == "__main__":
    main()
