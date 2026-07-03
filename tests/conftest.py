"""
conftest.py — thêm đường dẫn để import được trong pytest.
Cho phép cả hai kiểu:
  - from src.preprocessing.bytes_to_image import ...   (cần ROOT trên sys.path)
  - from channels import ...                            (cần src/preprocessing trên sys.path)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "src" / "preprocessing", ROOT / "src" / "utils"):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)
