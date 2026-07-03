"""
Unit test cho src/preprocessing/channels.py (S2.2b).
Kênh 2 = entropy từ chuỗi byte; kênh 3 = tỉ lệ ký tự in được (ASCII).
Chạy: pytest tests/test_channels.py -v
"""

import numpy as np

from src.preprocessing.channels import (
    byte_entropy_channel, printable_ratio_channel, make_composite, normalize_uint8,
)


def _gray():
    return np.random.default_rng(0).integers(0, 256, (60, 40), dtype=np.uint8)


def test_normalize_range():
    n = normalize_uint8(np.array([[0.0, 5.0], [10.0, 2.0]]))
    assert n.dtype == np.uint8 and n.min() == 0 and n.max() == 255


def test_normalize_constant_array():
    n = normalize_uint8(np.full((3, 3), 7.0))
    assert (n == 0).all()


def test_channels_same_hw():
    g = _gray()
    assert byte_entropy_channel(g).shape == g.shape
    assert printable_ratio_channel(g).shape == g.shape


def test_composite_shape_dtype():
    c = make_composite(_gray())
    assert c.shape == (60, 40, 3) and c.dtype == np.uint8


def test_full_three_channels_differ():
    g = _gray()
    c = make_composite(g)
    np.testing.assert_array_equal(c[..., 0], g)          # kênh 1 = gray
    assert not np.array_equal(c[..., 0], c[..., 1])      # entropy khác gray
    assert not np.array_equal(c[..., 1], c[..., 2])      # ascii khác entropy


def test_ablation_gray3():
    c = make_composite(_gray(), use_entropy=False, use_ascii=False)
    np.testing.assert_array_equal(c[..., 0], c[..., 1])
    np.testing.assert_array_equal(c[..., 1], c[..., 2])


def test_ablation_entropy_only():
    g = _gray()
    c = make_composite(g, use_entropy=True, use_ascii=False)
    np.testing.assert_array_equal(c[..., 0], c[..., 2])  # ascii tắt → kênh3 = gray
    assert not np.array_equal(c[..., 1], c[..., 0])      # entropy bật → khác


def test_byte_entropy_detects_packed():
    """Vùng byte đồng nhất (entropy thấp) vs ngẫu nhiên (cao)."""
    rng = np.random.default_rng(0)
    seq = np.concatenate([np.zeros(2000, np.uint8),
                          rng.integers(0, 256, 2000, dtype=np.uint8)])
    seq = np.pad(seq, (0, (-len(seq)) % 40)).reshape(-1, 40)
    e = byte_entropy_channel(seq, window=256)
    assert e.reshape(-1)[:1500].mean() < e.reshape(-1)[-1500:].mean()


def test_printable_ratio_detects_text():
    """Vùng ASCII (text) sáng hơn vùng nhị phân."""
    text = np.frombuffer(b"hello world http://x.com " * 100, np.uint8)[:2000]
    binr = np.random.default_rng(0).integers(128, 256, 2000, dtype=np.uint8)
    seq = np.concatenate([text, binr])
    seq = np.pad(seq, (0, (-len(seq)) % 40)).reshape(-1, 40)
    a = printable_ratio_channel(seq, window=256)
    assert a.reshape(-1)[:1800].mean() > a.reshape(-1)[-1800:].mean() + 100


def test_readonly_input_ok():
    """Mảng read-only (như từ PIL) vẫn xử lý được (đã copy nội bộ)."""
    g = _gray()
    g.flags.writeable = False
    c = make_composite(g)
    assert c.shape == (60, 40, 3)
