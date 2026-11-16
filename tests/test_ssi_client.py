"""Kiểm thử src/ssi_api/client.py bằng máy chủ SSI giả lập (không cần mạng, không cần key thật)."""
from datetime import date

import pytest

from src.ssi_api import client as client_module
from src.ssi_api.client import SSIClient, SSIError, date_chunks


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body
        self.text = str(body)
        self.headers = {}

    def json(self):
        return self._body


class FakeSession:
    """Session giả: trả lần lượt các response đã chuẩn bị và ghi lại các yêu cầu đã nhận."""

    def __init__(self, get_responses):
        self.get_responses = list(get_responses)
        self.get_calls = []
        self.post_calls = 0

    def post(self, url, json=None, timeout=None):
        self.post_calls += 1
        return FakeResponse(200, {"accessToken": f"token-{self.post_calls}", "expiresAt": 9_999_999_999})

    def get(self, url, headers=None, params=None, timeout=None):
        self.get_calls.append({"url": url, "params": dict(params), "auth": headers["Authorization"]})
        return self.get_responses.pop(0)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Bỏ thời gian chờ để kiểm thử chạy nhanh."""
    monkeypatch.setattr(client_module.time, "sleep", lambda seconds: None)


def make_client(responses):
    session = FakeSession(responses)
    return SSIClient("key", "secret", min_interval=0, session=session), session


def test_date_chunks_split_long_range():
    chunks = date_chunks(date(2024, 1, 1), date(2025, 6, 30), max_days=365)
    assert chunks[0] == (date(2024, 1, 1), date(2024, 12, 30))
    assert chunks[-1][1] == date(2025, 6, 30)
    assert len(chunks) == 2


def test_paginates_until_short_page(monkeypatch):
    monkeypatch.setattr(client_module.config, "SSI_PAGE_SIZE", 2)
    page1 = {"data": [{"tradingDate": "2026/11/13"}, {"tradingDate": "2026/11/12"}]}
    page2 = {"data": [{"tradingDate": "2026/11/11"}]}
    client, session = make_client([FakeResponse(200, page1), FakeResponse(200, page2)])
    records = client.get_stock_daily("FPT", date(2026, 11, 11), date(2026, 11, 13))
    assert len(records) == 3
    assert [call["params"]["pageNumber"] for call in session.get_calls] == [1, 2]
    assert session.get_calls[0]["params"]["from"] == "2026/11/11"  # đúng định dạng SSI chấp nhận


def test_reauthenticates_after_401():
    client, session = make_client([FakeResponse(401, {"msg": "expired"}), FakeResponse(200, [{"symbol": "FPT"}])])
    assert client.get_securities("HOSE") == [{"symbol": "FPT"}]
    assert session.post_calls == 2  # xác thực lần đầu + xác thực lại sau 401
    assert session.get_calls[1]["auth"] == "Bearer token-2"


def test_retries_on_server_error_then_succeeds():
    client, _ = make_client([FakeResponse(503, "busy"), FakeResponse(200, [{"symbol": "FPT"}])])
    assert client.get_securities("HOSE") == [{"symbol": "FPT"}]


def test_raises_on_bad_request_without_retry():
    client, session = make_client([FakeResponse(400, {"code": 400213, "msg": "Invalid Date/Timestamp Format"})])
    with pytest.raises(SSIError):
        client.get_securities("HOSE")
    assert len(session.get_calls) == 1


def test_raw_hook_receives_each_page():
    saved = []
    client, _ = make_client([FakeResponse(200, [{"symbol": "FPT"}])])
    client.raw_hook = lambda path, params, body: saved.append(path)
    client.get_securities("HOSE")
    assert saved == ["data/securitiesByBoard"]


def test_index_daily_uses_datetime_format():
    client, session = make_client([FakeResponse(200, {"data": []})])
    client.get_index_daily("VNINDEX", date(2026, 11, 1), date(2026, 11, 16))
    params = session.get_calls[0]["params"]
    assert params["from"] == "2026/11/01 00:00:00"
    assert params["to"] == "2026/11/16 23:59:59"
    assert params["timeFrame"] == "1d"


def test_stock_daily_uses_short_chunks_without_paging():
    # 1 năm dữ liệu -> chia đoạn 120 ngày -> 4 yêu cầu, mỗi yêu cầu chỉ xin trang 1
    responses = [FakeResponse(200, {"data": [{"tradingDate": "2026/01/02"}]}) for _ in range(4)]
    client, session = make_client(responses)
    client.get_stock_daily("FPT", date(2026, 1, 1), date(2026, 12, 31))
    assert len(session.get_calls) == 4
    assert all(call["params"]["pageNumber"] == 1 for call in session.get_calls)
    assert session.get_calls[1]["params"]["from"] == "2026/05/01"
