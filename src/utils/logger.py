"""
logger.py — Logger ghi ra stdout + (tùy chọn) file, định dạng thống nhất.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATEFMT = "%H:%M:%S"


def get_logger(name: str = "datn",
               log_file: Optional[str] = None,
               level: int = logging.INFO) -> logging.Logger:
    """
    Trả về logger đã cấu hình. Gọi nhiều lần với cùng `name` không thêm handler trùng.

    Args:
        name: tên logger.
        log_file: nếu có, ghi thêm ra file này (tự tạo thư mục cha).
        level: mức log.
    """
    logger = logging.getLogger(name)
    if logger.handlers:           # đã cấu hình → trả về luôn
        return logger
    logger.setLevel(level)
    logger.propagate = False
    fmt = logging.Formatter(_FORMAT, _DATEFMT)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


__all__ = ["get_logger"]
