"""
config.py — Đọc cấu hình YAML (config-driven, không hard-code).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict:
    """Đọc file YAML → dict (rỗng nếu file trống)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Không thấy config: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get(cfg: dict, dotted_key: str, default: Any = None) -> Any:
    """
    Truy cập khóa lồng nhau bằng dấu chấm, vd get(cfg, 'split.seed', 42).
    """
    cur: Any = cfg
    for part in dotted_key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def native_height(size_bytes: int, width: int, max_bytes: int | None = None) -> int:
    """Chiều cao ảnh native = ceil(min(size, max_bytes) / width)."""
    n = min(size_bytes, max_bytes) if max_bytes else size_bytes
    return math.ceil(n / width)


__all__ = ["load_config", "get", "native_height"]
