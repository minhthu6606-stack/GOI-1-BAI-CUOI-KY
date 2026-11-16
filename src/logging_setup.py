"""
Thiết lập ghi nhật ký (logging) cho toàn dự án.

Nhật ký vừa in ra màn hình, vừa ghi vào logs/<tên>.log để khi mất kết nối
hoặc API trả lỗi có thể xem lại nguyên nhân (yêu cầu Mục 9 của đề).
"""
from __future__ import annotations

import logging

from src.config import LOG_DIR

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging(name: str = "app", level: int = logging.INFO) -> None:
    """Cấu hình logging một lần cho cả chương trình."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if root.handlers:  # đã cấu hình rồi thì không thêm lần nữa
        return
    root.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")

    file_handler = logging.FileHandler(LOG_DIR / f"{name}.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(console_handler)
