"""
channels.py — Giai đoạn 2 (S2.2b)
---------------------------------
Sinh ảnh 3 kênh composite từ ảnh xám PE:
  - Kênh 1: grayscale (bytes → pixel, đã có từ bytes_to_image).
  - Kênh 2: entropy TỪ CHUỖI BYTE — cửa sổ byte LIÊN TIẾP (mặc định 256), tính
            Shannon entropy mỗi khối rồi trải về đúng vị trí byte (căn chỉnh kênh 1).
            → phát hiện vùng packed/mã hóa (đúng ngữ nghĩa entropy cho malware).
  - Kênh 3: tỉ lệ KÝ TỰ IN ĐƯỢC (printable ASCII, 0x20–0x7E) TỪ CHUỖI BYTE —
            cửa sổ byte liên tiếp → làm nổi vùng chuỗi/text/resource vs code/packed.
Cả 3 kênh tính TỪ CHUỖI BYTE, **căn chỉnh không gian hoàn hảo** (cùng H×W),
tính ở native rồi mới resize.

Lưu ý: kênh 2 & 3 dùng cửa sổ byte 1D liền kề, không phải cửa sổ 2D trên ảnh.
Hàm `entropy_channel` (2D) giữ lại chỉ để so sánh byte-vs-2D, KHÔNG dùng ở pipeline mặc định.

KHÔNG nhân bản kênh — 3 kênh là 3 biểu diễn khác nhau (điểm mới chính 1).
Có thể tắt từng kênh (ablation): kênh tắt được thay bằng grayscale để giữ đủ 3 kênh
cho model pretrained ImageNet (in_chans=3).
"""

from __future__ import annotations

import numpy as np
from skimage.filters.rank import entropy as rank_entropy

ENTROPY_WINDOW = 9            # (cũ) cửa sổ entropy 2D trên ảnh — giữ để so sánh
BYTE_ENTROPY_WINDOW = 256     # cửa sổ byte liên tiếp cho entropy 1D (mặc định)
ASCII_WINDOW = 256            # cửa sổ byte cho tỉ lệ ký tự in được (kênh 3)
PRINTABLE_LO, PRINTABLE_HI = 0x20, 0x7E   # ' ' (32) .. '~' (126) = ký tự in được


def normalize_uint8(arr: np.ndarray) -> np.ndarray:
    """Chuẩn hóa min-max về 0–255 (uint8)."""
    a = arr.astype(np.float64)
    mn, mx = float(a.min()), float(a.max())
    if mx - mn < 1e-12:
        return np.zeros(a.shape, dtype=np.uint8)
    return ((a - mn) / (mx - mn) * 255.0).astype(np.uint8)


def byte_entropy_channel(gray: np.ndarray,
                         window: int = BYTE_ENTROPY_WINDOW) -> np.ndarray:
    """
    Entropy TỪ CHUỖI BYTE (không phải từ ảnh 2D).
    - Duỗi ảnh xám về chuỗi byte gốc (row-major = đúng thứ tự byte của file).
    - Chia thành khối `window` byte LIÊN TIẾP, tính Shannon entropy mỗi khối (0–8 bit).
    - Gán entropy của khối cho mọi byte trong khối → trải lại về đúng H×W (căn chỉnh kênh 1).
    Vectorized (một lần bincount), nhanh cả với ảnh lớn.
    """
    b = gray.reshape(-1).astype(np.int64)
    n = b.size
    nb = (n + window - 1) // window
    pad = nb * window - n
    if pad:
        b = np.concatenate([b, np.zeros(pad, dtype=b.dtype)])
    bb = b.reshape(nb, window)
    offset = np.arange(nb, dtype=np.int64)[:, None] * 256
    counts = np.bincount((bb + offset).reshape(-1),
                         minlength=nb * 256).reshape(nb, 256).astype(np.float64)
    p = counts / window
    with np.errstate(divide="ignore", invalid="ignore"):
        term = np.where(p > 0, p * np.log2(p), 0.0)
    ent = -term.sum(axis=1)                       # entropy mỗi khối (bit)
    per_pos = np.repeat(ent, window)[:n]
    return normalize_uint8(per_pos.reshape(gray.shape))


def entropy_channel(gray: np.ndarray, window: int = ENTROPY_WINDOW) -> np.ndarray:
    """(CŨ, để so sánh) Entropy 2D trên ẢNH, cửa sổ window×window → uint8 cùng H×W."""
    footprint = np.ones((window, window), dtype=np.uint8)
    gray = np.ascontiguousarray(gray, dtype=np.uint8).copy()
    e = rank_entropy(gray, footprint)
    return normalize_uint8(e)


def printable_ratio_channel(gray: np.ndarray,
                            window: int = ASCII_WINDOW) -> np.ndarray:
    """
    Kênh 3 — TỈ LỆ KÝ TỰ IN ĐƯỢC (printable ASCII) từ chuỗi byte.
    - Duỗi ảnh về chuỗi byte gốc; đánh dấu byte in được (0x20–0x7E) = 1, còn lại = 0.
    - Mỗi cửa sổ `window` byte liên tiếp: tỉ lệ = (số byte in được)/window ∈ [0,1].
    - Gán tỉ lệ cho mọi byte trong cửa sổ → trải về H×W (căn chỉnh kênh 1).
    - Map TUYỆT ĐỐI ×255 (0=không có text, 255=toàn text) — không min-max từng ảnh,
      nên giá trị nhất quán giữa các mẫu.
    Làm nổi vùng chuỗi/text/resource (mật độ ASCII cao) vs code/packed (thấp).
    """
    b = gray.reshape(-1)
    n = b.size
    is_print = ((b >= PRINTABLE_LO) & (b <= PRINTABLE_HI)).astype(np.float64)
    nb = (n + window - 1) // window
    pad = nb * window - n
    if pad:
        is_print = np.concatenate([is_print, np.zeros(pad, dtype=np.float64)])
    ratio = is_print.reshape(nb, window).mean(axis=1)      # 0..1 mỗi khối
    per_pos = np.repeat(ratio, window)[:n]
    return (per_pos.reshape(gray.shape) * 255.0).astype(np.uint8)


def make_composite(gray: np.ndarray,
                   use_entropy: bool = True,
                   use_ascii: bool = True,
                   entropy_from_bytes: bool = True) -> np.ndarray:
    """
    Ghép 3 kênh → ảnh H×W×3 (uint8), thứ tự [gray, entropy-byte, ascii-ratio].
    Cả kênh 2 và 3 đều tính TỪ CHUỖI BYTE (byte liền kề), căn chỉnh với kênh 1.

    entropy_from_bytes=True (mặc định): kênh 2 = entropy từ chuỗi byte.
    entropy_from_bytes=False: kênh 2 = entropy 2D trên ảnh (cũ) — chỉ để so sánh.

    Ablation: tắt kênh nào thì thay bằng grayscale (giữ 3 kênh).
      - full:      use_entropy=True,  use_ascii=True   → [gray, entropy, ascii]
      - +entropy:  use_entropy=True,  use_ascii=False  → [gray, entropy, gray]
      - +ascii:    use_entropy=False, use_ascii=True   → [gray, gray,    ascii]
      - gray×3:    use_entropy=False, use_ascii=False  → [gray, gray,    gray]
    """
    gray = np.array(gray, dtype=np.uint8)  # copy → ghi được (PIL trả read-only)
    if use_entropy:
        k2 = byte_entropy_channel(gray) if entropy_from_bytes else entropy_channel(gray)
    else:
        k2 = gray
    k3 = printable_ratio_channel(gray) if use_ascii else gray
    return np.stack([gray, k2, k3], axis=-1)


__all__ = ["normalize_uint8", "byte_entropy_channel", "printable_ratio_channel",
           "entropy_channel", "make_composite"]
