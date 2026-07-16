"""
vm_verify_files.py — Kiểm chứng NHÃN bằng FILE THẬT, chạy TRONG VM KALI (S6.3)
==============================================================================
Bổ sung cho tra-VirusTotal-bằng-hash: dùng file gốc (chỉ ĐỌC) để lấy thêm 2
nguồn phán quyết ĐỘC LẬP, không tốn quota, và cứu được các mẫu "không có trên VT".

AN TOÀN — script này CHỈ:
  * ĐỌC byte tĩnh của file (parse PE header, chữ ký số nhúng)
  * Quét bằng ClamAV CỤC BỘ (offline)
KHÔNG thực thi file. KHÔNG upload. KHÔNG sửa/di chuyển/xoá file.
=> Đầu ra là 1 CSV metadata (an toàn mang ra host).

BA TÍN HIỆU:
  1. ClamAV phát hiện          -> xác nhận ĐỘC HẠI (nhãn đúng)
  2. Có chữ ký số nhúng        -> tín hiệu SẠCH (nhưng xem CẢNH BÁO bên dưới)
  3. Là .NET + GUI subsystem   -> nhiều khả năng là BUILDER, không phải payload

⚠ CẢNH BÁO QUAN TRỌNG — chữ ký số KHÔNG phải bằng chứng tuyệt đối:
  malware CÓ THỂ ký bằng chứng chỉ ĐÁNH CẮP. Chính họ `Mediyes` trong dataset này
  nổi tiếng vì điều đó. Vì vậy chữ ký chỉ là MỘT tín hiệu; kết luận "nhãn sai" chỉ
  chắc khi CẢ BA nguồn (VirusTotal + ClamAV + chữ ký) cùng nói sạch.

CHUẨN BỊ TRÊN KALI:
    sudo apt update && sudo apt install -y clamav
    sudo freshclam                       # tải CSDL virus (bắt buộc, ~1 lần)
    pip install pefile                   # parse PE (nếu chưa có)

CÁCH DÙNG (trong VM Kali):
    python3 vm_verify_files.py \
        --hashes rat_all_hashes.txt \
        --labels labels.csv \
        --out vm_verify_rat.csv

    # nếu đường dẫn trong labels.csv không còn đúng:
    python3 vm_verify_files.py ... --search-root /home/kali/data/raw/malware/RAT
"""

from __future__ import annotations

import argparse
import csv
import math
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

try:
    import pefile
    HAVE_PEFILE = True
except ImportError:
    HAVE_PEFILE = False

SUBSYSTEM = {2: "GUI", 3: "Console"}


def sniff_pe(path: Path)