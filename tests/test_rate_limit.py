"""Kiểm thử cơ chế tự giới hạn tần suất của SSIClient bằng đồng hồ thật (không giả lập thời gian chờ)."""
import time

from src.ssi_api.client import SSIClient


def test_requests_are_spaced_at_least_min_interval():
    client = SSIClient("key", "secret", min_interval=0.05)
    sent = []
    for _ in range(5):
        client._wait_for_rate_limit()
        sent.append(time.perf_counter())
    gaps = [b - a for a, b in zip(sent, sent[1:])]
    assert min(gaps) >= 0.05                      # không bao giờ ngắn hơn mức tự đặt, kể cả vài mili giây
    assert client.request_count == 5


def test_first_request_does_not_wait():
    client = SSIClient("key", "secret", min_interval=5)
    started = time.perf_counter()
    client._wait_for_rate_limit()
    assert time.perf_counter() - started < 0.5   # yêu cầu đầu tiên gửi ngay
