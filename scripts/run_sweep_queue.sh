#!/bin/bash
# Queue lưới hợp nhất 5x3 (Thí nghiệm A) — chạy trên sweep_*.csv (res_eligible)
# 45 run ResNet50 (5 kênh x 3 size x 3 seed) + 9 run ConvNeXt-Tiny (full x 3 size x 3 seed)
#
# Cách dùng (Git Bash, từ thư mục gốc DATN):
#   ./scripts/run_sweep_queue.sh              # mặc định: chỉ các ô 224
#   ./scripts/run_sweep_queue.sh 224 336      # 224 xong rồi tới 336
#   ./scripts/run_sweep_queue.sh all          # cả 3 size (448 nặng — cân nhắc Colab)
#
# Tự BỎ QUA run đã hoàn tất (đã có experiments/{run_name}_*/best_metrics.json)
# → dừng giữa chừng (Ctrl+C / tắt máy) rồi chạy lại script là tiếp tục đúng chỗ.
set -u
cd "$(dirname "$0")/.."
PY=./datn-env/Scripts/python.exe
LOG=experiments/sweep_queue.log

sizes=("$@")
[ ${#sizes[@]} -eq 0 ] && sizes=(224)
[ "${sizes[0]}" = "all" ] && sizes=(224 336 448)

run_cfg() {
  local name=$1
  if ls experiments/${name}_*/best_metrics.json >/dev/null 2>&1; then
    echo "=== SKIP $name (da xong)" | tee -a "$LOG"
    return
  fi
  echo "=== START $name $(date)" | tee -a "$LOG"
  "$PY" scripts/train.py --config "configs/${name}.yaml" >> "$LOG" 2>&1
  echo "=== END $name exit=$? $(date)" | tee -a "$LOG"
}

for size in "${sizes[@]}"; do
  # ResNet50: đủ 5 cấu hình kênh
  for cfg in gray1 gray3 entropy ascii full; do
    for seed in 42 123 2026; do
      run_cfg "sweep_resnet50_${cfg}_${size}_s${seed}"
    done
  done
  # ConvNeXt-Tiny: chỉ 'full' — khẳng định kết luận 2 không phụ thuộc kiến trúc
  for seed in 42 123 2026; do
    run_cfg "sweep_convnext_tiny_${size}_s${seed}"
  done
done

echo "=== QUEUE DONE $(date)" | tee -a "$LOG"
