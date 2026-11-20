"""
Báo cáo kiểm chứng (đưa vào Mục 7 của báo cáo): ghi ra thư mục docs/kiem_chung/ ba file Markdown.

    chat_luong_du_lieu.md   mỗi mã: số phiên, phiên thiếu, dòng bị gắn cờ, giá đã điều chỉnh, đối chiếu lợi suất
    nhat_ky_thu_thap.md     số phiên dữ liệu trong kho; mỗi lần cập nhật: lúc nào, phiên nào, số chuỗi thành công/lỗi
    kiem_dinh_var.md        kiểm định ngoài mẫu VaR 95% của 3 danh mục ví dụ (Kupiec, Christoffersen)
    so_sanh_danh_muc.md     so sánh kết quả kiểm tra của 3 danh mục ví dụ

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
from src.data.quality import collection_summary, cross_mismatch_details, quality_table, sessions_collected  # noqa: E402
from src.data.storage import Storage  # noqa: E402
from src.finance.examples import EXAMPLE_TOTAL, EXAMPLES, build_example, example_symbols  # noqa: E402
from src.finance.health import build_health_report, count_by_status, num, pct, vnd  # noqa: E402
from src.finance.whatif import key_metrics  # noqa: E402
from src.finance.market_data import load_market_data  # noqa: E402
from src.finance.portfolio import build_portfolio  # noqa: E402

OUT_DIR = config.PROJECT_ROOT / "docs" / "kiem_chung"


def _table(frame: pd.DataFrame) -> str:
    """Bảng Markdown đơn giản (không cần thư viện ngoài)."""
    header = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    line = "| " + " | ".join("---" for _ in frame.columns) + " |"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([header, line, *body])


def latest_close(storage: Storage, symbols: list[str]) -> pd.Series:
    """Giá đóng cửa phiên mới nhất của từng mã."""
    prices = {}
    for symbol in symbols:
        frame = storage.load_daily("stock_daily", symbol).tail(1)
        if not frame.empty:
            prices[symbol] = float(frame["close"].iloc[0])
    return pd.Series(prices, dtype=float)


def _vn(value: float, digits: int = 2) -> str:
    """Định dạng số kiểu Việt Nam: dấu chấm phân cách hàng nghìn, dấu phẩy thập phân."""
    return f"{value:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")


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
        mismatches = cross_mismatch_details(storage, config.TRACKED_SYMBOLS)
        summary = collection_summary(storage.load_fetch_log(limit=100_000), storage.trading_calendar(config.MARKET_INDEX))
        prices = latest_close(storage, example_symbols())
        reports = {}
        for key in EXAMPLES:
            rows, cash = build_example(key, prices)
            portfolio = build_portfolio(pd.concat([rows, pd.DataFrame({"symbol": ["CASH"], "quantity": [cash]})]))
            reports[key] = build_health_report(portfolio, load_market_data(storage, portfolio.symbols))

    # 1. Chất lượng dữ liệu
    view = quality.rename(columns={
        "symbol": "Mã", "sessions": "Số phiên", "first": "Từ ngày", "last": "Đến ngày", "missing": "Phiên thiếu",
        "flagged": "Dòng bị gắn cờ", "adjusted": "Phiên có giá đã điều chỉnh", "cross_checked": "Số phiên đối chiếu",
        "cross_mismatch": "Lệch > 1 điểm %"})
    total_missing = int(quality.get("missing", pd.Series(dtype=int)).fillna(0).sum())
    total_mismatch = int(quality.get("cross_mismatch", pd.Series(dtype=int)).fillna(0).sum())
    if mismatches.empty:
        detail = "\nKhông có phiên nào lệch quá 1 điểm %.\n"
    else:
        detail_view = pd.DataFrame({
            "Mã": mismatches["symbol"], "Ngày": mismatches["trading_date"],
            "Đóng cửa phiên trước (đã điều chỉnh)": mismatches["prev_close"].map(_vn),
            "Đóng cửa": mismatches["close"].map(_vn),
            "Lợi suất tự tính (%)": mismatches["computed_pct"].map(_vn),
            "% thay đổi SSI": mismatches["reported_pct"].map(_vn),
            "Giá tham chiếu SSI / đóng cửa trước": mismatches["ratio_prev_close"].map(lambda v: _vn(v, 4)),
        })
        detail = ("\n## Chi tiết các phiên lệch\n\nCột cuối khác 1 rõ rệt nghĩa là giá tham chiếu của sở khác giá "
                  "đóng cửa phiên trước trong chuỗi đã điều chỉnh, tức là có điều chỉnh giá (vd ngày giao dịch không "
                  "hưởng quyền). Cần tra lịch sự kiện của mã để xác nhận.\n\n" + _table(detail_view) + "\n")
    text = (_header("Chất lượng dữ liệu", db_path)
            + "Đối chiếu: lợi suất tự tính từ giá đóng cửa đã điều chỉnh so với `priceChangePercentage` do SSI công bố; "
              "lệch quá 1 điểm phần trăm thì đếm là lệch. Phiên thiếu tính theo lịch giao dịch của VN-Index.\n\n"
            + _table(view) + f"\n\n**Tổng:** {len(quality)} mã, {total_missing} phiên thiếu, {total_mismatch} phiên lệch.\n"
            + detail)
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

    # 3. Kiểm định VaR cho từng danh mục ví dụ
    var_rows = []
    for key, report in reports.items():
        bt = report.backtest
        pof = "Đạt" if bt.passes_pof else ("Không đạt (VaR thận trọng)" if bt.too_few_exceptions
                                           else "Không đạt (vượt nhiều hơn kỳ vọng)")
        ind = "Đạt" if bt.passes_independence else "Không đạt (dồn cục)"
        var_rows.append([EXAMPLES[key].title, bt.observations, bt.exceptions,
                         f"{pct(bt.exception_rate, 2)}", f"{num(bt.p_pof, 3)} – {pof}", f"{num(bt.p_ind, 3)} – {ind}"])
    first = next(iter(reports.values())).backtest
    span_bt = f"{first.series.index.min()} – {first.series.index.max()}" if first.observations else "—"
    text = (_header("Kiểm định ngoài mẫu VaR 95% (3 danh mục ví dụ)", db_path)
            + "VaR lịch sử 1 ngày, cửa sổ trượt 250 phiên; VaR của mỗi ngày chỉ dùng dữ liệu trước ngày đó. Mỗi "
              f"danh mục giữ tỷ trọng hiện tại trong suốt giai đoạn ({span_bt}). Tỷ lệ vượt kỳ vọng: 5%.\n\n"
            + _table(pd.DataFrame(var_rows, columns=["Danh mục", "Số ngày kiểm định", "Số lần vượt", "Tỷ lệ vượt",
                                                     "Kupiec (1995): p-value", "Christoffersen (1998): p-value"]))
            + "\n\nMức ý nghĩa 5%: p-value ≥ 0,05 thì không bác bỏ giả thuyết mô hình đúng.\n")
    (OUT_DIR / "kiem_dinh_var.md").write_text(text, encoding="utf-8")

    # 4. So sánh 3 danh mục ví dụ (kiểm tra tính hợp lý: danh mục đa dạng hơn phải có kết quả tập trung tốt hơn)
    metrics = {EXAMPLES[key].title: key_metrics(report) for key, report in reports.items()}
    compare = pd.DataFrame(metrics)
    compare.insert(0, "Chỉ số", compare.index)
    lines = []
    for key, report in reports.items():
        counts = count_by_status(report.checks)
        lines.append(f"- **{EXAMPLES[key].title}**: {EXAMPLES[key].description} Số tiêu chí: "
                     + ", ".join(f"{level} {n}" for level, n in counts.items()) + ".")
    text = (_header("So sánh 3 danh mục ví dụ", db_path)
            + f"Danh mục giả định, mỗi danh mục khoảng {vnd(EXAMPLE_TOTAL)}, số lượng làm tròn theo lô 100 cổ phiếu "
              "theo giá đóng cửa phiên mới nhất trong kho. Các danh mục được chọn theo cấu trúc, không chỉnh để ra "
              "kết quả đẹp.\n\n" + "\n".join(lines) + "\n\n" + _table(compare.reset_index(drop=True)) + "\n")
    (OUT_DIR / "so_sanh_danh_muc.md").write_text(text, encoding="utf-8")

    print(f"Đã ghi 4 file vào {OUT_DIR}")
    print(f"   Chất lượng: {len(quality)} mã, {total_missing} phiên thiếu, {total_mismatch} phiên lệch > 1 điểm %")
    for row in mismatches.itertuples(index=False):
        print(f"      Lệch: {row.symbol} ngày {row.trading_date}: tự tính {row.computed_pct:.2f}%, SSI {row.reported_pct:.2f}%, "
              f"giá tham chiếu / đóng cửa trước = {row.ratio_prev_close:.4f}")
    print(f"   Thu thập: kho có {len(calendar)} phiên ({span}); ứng dụng đã chạy cập nhật vào {len(sessions)} phiên "
          f"({', '.join(sessions)})")
    for row in var_rows:
        print(f"   Kiểm định VaR – {row[0]}: {row[2]}/{row[1]} ngày vượt ({row[3]}), Kupiec p = {row[4]}, "
              f"Christoffersen p = {row[5]}")
    for title, values in metrics.items():
        print(f"   {title}: kết luận {values['Kết luận chung']}, mã lớn nhất {values['Mã lớn nhất']}, "
              f"VaR {values['Mức lỗ phiên xấu (VaR 95%)']}")


if __name__ == "__main__":
    main()
