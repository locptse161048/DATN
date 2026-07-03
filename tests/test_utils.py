"""
Unit test cho src/utils (S2.1). Chạy: pytest tests/test_utils.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "utils"))
import config as cfgmod          # noqa: E402
from logger import get_logger    # noqa: E402
from seed import set_seed        # noqa: E402


def test_set_seed_reproducible():
    set_seed(42)
    a = np.random.rand(5)
    set_seed(42)
    b = np.random.rand(5)
    assert np.allclose(a, b)


def test_set_seed_returns_value():
    assert set_seed(123) == 123


def test_config_load_and_get(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("image_width: 448\nsplit:\n  seed: 7\n", encoding="utf-8")
    cfg = cfgmod.load_config(p)
    assert cfg["image_width"] == 448
    assert cfgmod.get(cfg, "split.seed") == 7
    assert cfgmod.get(cfg, "missing.key", 99) == 99


def test_native_height():
    assert cfgmod.native_height(1000, 448) == 3          # ceil(1000/448)
    assert cfgmod.native_height(10**9, 448, max_bytes=31457280) == \
        cfgmod.native_height(31457280, 448)              # bị cắt theo max_bytes


def test_logger_no_duplicate_handlers():
    lg1 = get_logger("test_dup")
    n = len(lg1.handlers)
    lg2 = get_logger("test_dup")
    assert lg1 is lg2 and len(lg2.handlers) == n
    lg1.info("hello")  # không lỗi
