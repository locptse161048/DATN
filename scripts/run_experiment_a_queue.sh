#!/bin/bash
# Chạy nốt các ô còn lại của Thí nghiệm A (ablation kênh, ResNet50, 224, 3 seed)
# gray1_s42 đã chạy riêng (smoke test) nên bỏ qua ở đây.
set -u
cd "$(dirname "$0")/.."
LOG=experiments/ablation_A_queue.log

# Chờ smoke test (gray1_s42) chạy xong trước khi bắt đầu, tránh tranh GPU
while kill -0 1554 2>/dev/null; do sleep 5; done

configs=(
  ascii_s42 ascii_s123 ascii_s2026
  entropy_s42 entropy_s123 entropy_s2026
  full_s42 full_s123 full_s2026
  gray1_s123 gray1_s2026
  gray3_s42 gray3_s123 gray3_s2026
)

for cfg in "${configs[@]}"; do
  echo "=== START $cfg $(date) ===" >> "$LOG"
  ./datn-env/Scripts/python.exe scripts/train.py --config "configs/ablation_resnet50_${cfg}.yaml" >> "$LOG" 2>&1
  echo "=== END $cfg exit=$? $(date) ===" >> "$LOG"
done

echo "=== QUEUE DONE $(date) ===" >> "$LOG"
