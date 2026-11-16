"""
Kiểm tra kết nối SSI FastConnect API v3 (chỉ dữ liệu thị trường, không dùng OTP).

Mục đích:
    - Xác nhận API key hoạt động.
    - Xem thực tế mỗi endpoint trả về những trường nào, trước khi thiết kế kho dữ liệu
      (tài liệu SSI đặt tên trường và định dạng ngày chưa nhất quán).
    - Tự dò định dạng ngày mà API chấp nhận.

Cách chạy (trong thư mục gốc của repo):
    python scripts/check_ssi_connection.py

Kết quả:
    - In tóm tắt ra màn hình (không in key, secret hay token).
    - Lưu response thô vào data/probe/ (thư mục data/ đã bị .gitignore chặn).
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

BASE_URL = "https://api.ssi.com.vn/api/v3"
PROBE_DIR = Path(__file__).resolve().parents[1] / "data" / "probe"
PAUSE_SECONDS = 1.1  # Tự giới hạn khoảng 1 yêu cầu/giây, thấp hơn nhiều so với hạn mức SSI
TIMEOUT_SECONDS = 20

# Mã lỗi SSI trả về khi sai định dạng ngày (quan sát được ở lần chạy thử đầu tiên)
INVALID_DATE_CODE = "400213"
# Các định dạng ngày sẽ thử lần lượt; dạng đầu tiên khớp với trường tradingDate SSI trả về
DATE_FORMAT_CANDIDATES = ["%Y/%m/%d", "%Y/%m/%d %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d"]


def get_token(api_key: str, api_secret: str) -> str:
    """Lấy access token KHÔNG kèm OTP.

    Token không có OTP chỉ có quyền đọc dữ liệu thị trường, nên về mặt kỹ thuật
    chương trình không thể đặt lệnh giao dịch thật.
    """
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/token",
            json={"apiKey": api_key, "apiSecret": api_secret},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        sys.exit(f"[LỖI] Không kết nối được máy chủ SSI: {exc}")

    if resp.status_code != 200:
        sys.exit(f"[LỖI] Xác thực thất bại: HTTP {resp.status_code} - {resp.text[:300]}")

    body = resp.json()
    token = body.get("accessToken") or (body.get("data") or {}).get("accessToken")
    if not token:
        sys.exit(f"[LỖI] Không thấy accessToken trong response. Các khóa nhận được: {list(body)}")

    print(f"[OK] Xác thực thành công. Token hết hạn lúc (expiresAt): {body.get('expiresAt')}")
    return token


def describe(body: Any) -> None:
    """In cấu trúc response: số bản ghi, tên các trường và khoảng ngày của dữ liệu."""
    if isinstance(body, dict) and isinstance(body.get("data"), list):
        records = body["data"]
        print(
            f"   itemsCount={body.get('itemsCount')} | pageCount={body.get('pageCount')} "
            f"| số bản ghi ở trang này={len(records)}"
        )
    elif isinstance(body, dict) and isinstance(body.get("data"), dict):
        records = [body["data"]]
    elif isinstance(body, list):
        records = body
        print(f"   Mảng gồm {len(records)} phần tử")
    elif isinstance(body, dict):
        records = [body]
    else:
        print(f"   Kiểu dữ liệu lạ: {type(body)}")
        return

    if not records:
        print("   Không có bản ghi nào.")
        return

    first = records[0]
    if not isinstance(first, dict):
        print(f"   Phần tử đầu: {str(first)[:200]}")
        return

    print(f"   Các trường: {', '.join(first.keys())}")
    print(f"   Bản ghi đầu: {json.dumps(first, ensure_ascii=False)[:400]}")

    # Cho biết dữ liệu sắp xếp tăng hay giảm dần theo ngày
    last = records[-1]
    if len(records) > 1 and isinstance(last, dict) and "tradingDate" in first:
        print(f"   tradingDate bản ghi đầu: {first.get('tradingDate')} | bản ghi cuối: {last.get('tradingDate')}")


def probe(name: str, path: str, params: dict[str, Any], headers: dict[str, str]) -> tuple[int | None, Any]:
    """Gọi thử một endpoint GET, in tóm tắt, lưu response thô ra file JSON.

    Trả về (mã HTTP, nội dung JSON) để hàm gọi quyết định có thử lại hay không.
    """
    url = f"{BASE_URL}/{path}"
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        print(f"\n[{name}] LỖI KẾT NỐI: {exc}")
        time.sleep(PAUSE_SECONDS)
        return None, None
    time.sleep(PAUSE_SECONDS)

    rate_limit = {k: v for k, v in resp.headers.items() if k.lower().startswith("x-ratelimit")}
    print(f"\n[{name}] GET /{path} -> HTTP {resp.status_code} | rate-limit: {rate_limit or 'không có header'}")

    try:
        body = resp.json()
    except ValueError:
        print(f"   Response không phải JSON: {resp.text[:200]}")
        return resp.status_code, None

    out_file = PROBE_DIR / f"{name}.json"
    out_file.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    describe(body)
    return resp.status_code, body


def is_invalid_date(status: int | None, body: Any) -> bool:
    """True nếu SSI từ chối vì sai định dạng ngày (HTTP 400, mã lỗi 400213)."""
    return status == 400 and isinstance(body, dict) and str(body.get("code")) == INVALID_DATE_CODE


def probe_with_dates(
    name: str,
    path: str,
    params: dict[str, Any],
    date_params: dict[str, date],
    headers: dict[str, str],
) -> str | None:
    """Thử lần lượt các định dạng ngày cho tới khi SSI chấp nhận.

    Trả về định dạng dùng được, hoặc None nếu không định dạng nào được chấp nhận.
    """
    for fmt in DATE_FORMAT_CANDIDATES:
        full_params = dict(params)
        for key, value in date_params.items():
            full_params[key] = value.strftime(fmt)
        print(f"\n   -> Thử định dạng ngày '{fmt}'")
        status, body = probe(name, path, full_params, headers)
        if not is_invalid_date(status, body):
            return fmt
    print(f"   [!] Không định dạng nào được chấp nhận cho /{path}")
    return None


def last_weekday_before(day: date) -> date:
    """Trả về ngày thứ Hai–thứ Sáu gần nhất trước `day` (bỏ qua cuối tuần)."""
    candidate = day - timedelta(days=1)
    while candidate.weekday() >= 5:  # 5 = thứ Bảy, 6 = Chủ nhật
        candidate -= timedelta(days=1)
    return candidate


def main() -> None:
    load_dotenv()
    api_key = os.getenv("SSI_API_KEY")
    api_secret = os.getenv("SSI_API_SECRET")
    if not api_key or not api_secret:
        sys.exit("[LỖI] Chưa có SSI_API_KEY hoặc SSI_API_SECRET trong file .env (xem .env.example).")

    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    token = get_token(api_key, api_secret)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    today = date.today()
    one_year_ago = today - timedelta(days=365)
    two_weeks_ago = today - timedelta(days=14)
    recent_weekday = last_weekday_before(today)

    ohlc_params = {"timeFrame": "1d", "pageIndex": 1, "pageSize": 100}
    ohlc_dates = {"from": one_year_ago, "to": today}
    found: dict[str, str | None] = {}

    # 1. Danh sách mã trên HOSE (không cần ngày)
    probe("01_securities_HOSE", "data/securitiesByBoard", {"board": "HOSE"}, headers)

    # 2. Thông tin giao dịch theo phiên của một cổ phiếu (2 tuần gần nhất)
    found["securitiesSummary"] = probe_with_dates(
        "02_summary_FPT",
        "data/securitiesSummary",
        {"symbol": "FPT", "pageNumber": 1, "pageSize": 20},
        {"from": two_weeks_ago, "to": today},
        headers,
    )

    # 3. Nến ngày 1 năm của một cổ phiếu
    found["ohlc"] = probe_with_dates(
        "03_ohlc_1d_FPT", "data/ohlc", {"symbol": "FPT", **ohlc_params}, ohlc_dates, headers
    )

    # 4–5. Dùng định dạng vừa tìm được để thử mã chỉ số và ETF (cần cho beta)
    ohlc_fmt = found["ohlc"] or DATE_FORMAT_CANDIDATES[0]
    ohlc_dates_text = {key: value.strftime(ohlc_fmt) for key, value in ohlc_dates.items()}
    probe("04_ohlc_1d_VNINDEX", "data/ohlc", {"symbol": "VNINDEX", **ohlc_params, **ohlc_dates_text}, headers)
    probe("05_ohlc_1d_E1VFVN30", "data/ohlc", {"symbol": "E1VFVN30", **ohlc_params, **ohlc_dates_text}, headers)

    # 6. Tổng hợp thị trường sàn HOSE của một ngày trong quá khứ (để lấy lịch sử độ rộng thị trường)
    found["indexSummary"] = probe_with_dates(
        "06_index_summary_HOSE_past",
        "data/indexSummary",
        {"board": "HOSE"},
        {"tradingDate": recent_weekday},
        headers,
    )

    print("\n=== ĐỊNH DẠNG NGÀY SSI CHẤP NHẬN ===")
    for endpoint, fmt in found.items():
        print(f"   {endpoint}: {fmt if fmt else 'KHÔNG TÌM ĐƯỢC'}")

    print(f"\nXong. Response thô đã lưu tại: {PROBE_DIR}")
    print("Hãy sao chép toàn bộ phần in ra màn hình ở trên để gửi lại (phần này không chứa key/token).")


if __name__ == "__main__":
    main()
