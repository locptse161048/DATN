"""
seed.py — Đặt seed cho tái lập (reproducibility).
Gọi set_seed(seed) ở đầu mỗi script/run. Hoạt động cả khi CHƯA cài torch
(môi trường Kali chỉ tiền xử lý) — torch được import có điều kiện.
"""

from __future__ import annotations

import os
import random

import numpy as np


def set_seed(seed: int = 42, deterministic: bool = True) -> int:
    """
    Đặt seed cho random, numpy, và (nếu có) torch + CUDA.

    Args:
        seed: giá trị seed.
        deterministic: bật chế độ xác định cho cuDNN (chậm hơn nhưng tái lập).

    Returns:
        seed đã đặt.
    """
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)

    try:
        import torch
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        if deterministic:
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
    except ImportError:
        pass  # Kali tiền xử lý: chưa cần torch

    return seed


__all__ = ["set_seed"]
