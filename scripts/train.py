"""
train.py — Giai đoạn 5 (S5.1 + S5.2)
------------------------------------
Huấn luyện model phát hiện nhị phân (benign vs malware) trên ảnh 3 kênh.
Config-driven. Chạy trên MÁY CÓ GPU (local RTX 4060 cho 224 / Colab cho 448).

Usage:
    python scripts/train.py --config configs/detect_vgg16_224.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.datasets.malware_dataset import MalwareImageDataset  # noqa: E402
from src.models.factory import build_model                    # noqa: E402
from src.utils.config import load_config, get                 # noqa: E402
from src.utils.logger import get_logger                       # noqa: E402
from src.utils.seed import set_seed                           # noqa: E402
from src.evaluation.metrics import (compute_metrics, save_evaluation_report,  # noqa: E402
                                    plot_training_curves)


def make_loaders(cfg, logger):
    sd = Path(get(cfg, "data.split_dir", "data/interim"))
    stats = get(cfg, "data.channel_stats", "data/interim/channel_stats.json")
    img = get(cfg, "data.img_size", 224)
    chan = get(cfg, "data.channels", "full")
    bs = get(cfg, "data.batch_size", 32)
    nw = get(cfg, "data.num_workers", 4)
    aug = get(cfg, "data.augment", False)
    prefix = get(cfg, "data.split_prefix", "split")  # "split" (detection) | "sweep" (resolution sweep)
    # image_root: nếu set (sweep), tự dựng path theo img_size thay vì cột image_path trong CSV
    # (1 bộ sweep_*.csv dùng chung cho cả 224/336/448 — xem MalwareImageDataset).
    image_root = get(cfg, "data.image_root", None)

    train_ds = MalwareImageDataset(sd / f"{prefix}_train.csv", stats, img, True, aug, chan, image_root)
    val_ds = MalwareImageDataset(sd / f"{prefix}_val.csv", stats, img, False, False, chan, image_root)
    test_ds = MalwareImageDataset(sd / f"{prefix}_test.csv", stats, img, False, False, chan, image_root)
    logger.info("train=%d %s | val=%d | test=%d", len(train_ds), train_ds.class_counts(),
                len(val_ds), len(test_ds))

    train_ld = DataLoader(train_ds, batch_size=bs, shuffle=True, num_workers=nw,
                          pin_memory=True, drop_last=True)
    val_ld = DataLoader(val_ds, batch_size=bs, shuffle=False, num_workers=nw, pin_memory=True)
    test_ld = DataLoader(test_ds, batch_size=bs, shuffle=False, num_workers=nw, pin_memory=True)
    return train_ds, train_ld, val_ld, test_ld


def class_weights(train_ds, num_classes, device):
    c = train_ds.class_counts()
    total = sum(c.values())
    w = [total / (num_classes * c.get(i, 1)) for i in range(num_classes)]
    return torch.tensor(w, dtype=torch.float32, device=device)


@torch.no_grad()
def predict(model, loader, device):
    """Trả về (y_true, y_pred, y_prob) dạng list — dùng cho metrics/plots."""
    model.eval()
    ys, ps, probs = [], [], []
    for x, y in loader:
        x = x.to(device, non_blocking=True)
        out = model(x)
        prob = torch.softmax(out, dim=1)[:, 1]
        ps += out.argmax(1).cpu().tolist()
        probs += prob.cpu().tolist()
        ys += y.tolist()
    return ys, ps, probs


def evaluate(model, loader, device):
    ys, ps, probs = predict(model, loader, device)
    return compute_metrics(ys, ps, probs)


def main():
    ap = argparse.ArgumentParser(description="Train model phát hiện malware (S5).")
    ap.add_argument("--config", type=Path, required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)

    run = get(cfg, "run_name", "run")
    seed = get(cfg, "seed", 42)
    set_seed(seed)
    run_dir = Path(get(cfg, "paths.out_dir", "experiments")) / f"{run}_{int(time.time())}"
    run_dir.mkdir(parents=True, exist_ok=True)
    logger = get_logger(run, log_file=str(run_dir / "train.log"))
    (run_dir / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Device: %s | run_dir: %s", device, run_dir)

    train_ds, train_ld, val_ld, test_ld = make_loaders(cfg, logger)

    num_classes = get(cfg, "model.num_classes", 2)
    model = build_model(get(cfg, "model.name", "vgg16"), num_classes,
                        get(cfg, "model.pretrained", True),
                        get(cfg, "model.freeze_backbone", False),
                        get(cfg, "model.in_chans", 3)).to(device)

    # Loss: class weights tự động (benign khan hiếm)
    weight = None
    if get(cfg, "train.class_weights", "auto") == "auto":
        weight = class_weights(train_ds, num_classes, device)
        logger.info("class_weights=%s", weight.cpu().tolist())
    criterion = nn.CrossEntropyLoss(weight=weight)

    lr = get(cfg, "train.lr", 1e-4)
    wd = get(cfg, "train.weight_decay", 1e-4)
    epochs = get(cfg, "train.epochs", 30)
    patience = get(cfg, "train.early_stop_patience", 6)
    use_amp = get(cfg, "train.amp", True) and device == "cuda"
    accum = max(1, get(cfg, "train.grad_accum_steps", 1))
    img_size = get(cfg, "data.img_size", 224)

    optimizer = torch.optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()),
                                  lr=lr, weight_decay=wd)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp)

    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()

    best_f1, best_ep, bad = -1.0, 0, 0
    history = []
    for ep in range(1, epochs + 1):
        model.train()
        t0, run_loss = time.time(), 0.0
        optimizer.zero_grad(set_to_none=True)
        n_batches = len(train_ld)
        for i, (x, y) in enumerate(train_ld):
            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)
            with torch.cuda.amp.autocast(enabled=use_amp):
                loss = criterion(model(x), y) / accum
            scaler.scale(loss).backward()
            if (i + 1) % accum == 0 or (i + 1) == n_batches:
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
            run_loss += loss.item() * accum * x.size(0)
        scheduler.step()
        epoch_time = time.time() - t0

        val = evaluate(model, val_ld, device)
        val_f1 = val.get("f1", val["acc"])
        train_loss = run_loss / len(train_ld.dataset)
        logger.info("Epoch %02d/%d | loss=%.4f | val acc=%.4f f1=%.4f auc=%.4f | %.0fs",
                    ep, epochs, train_loss, val["acc"],
                    val_f1, val.get("roc_auc", float("nan")), epoch_time)
        history.append({"epoch": ep, "loss": train_loss, "val_acc": val["acc"],
                        "val_f1": val_f1, "val_auc": val.get("roc_auc", float("nan")),
                        "epoch_time_s": epoch_time})

        if val_f1 > best_f1:
            best_f1, best_ep, bad = val_f1, ep, 0
            torch.save({"epoch": ep, "model_state": model.state_dict(),
                        "config": cfg, "val_metrics": val},
                       run_dir / "best.pt")
            (run_dir / "best_metrics.json").write_text(
                json.dumps(val, indent=2, ensure_ascii=False))
            logger.info("  ↑ best (f1=%.4f) → best.pt", best_f1)
        else:
            bad += 1
            if bad >= patience:
                logger.info("Early stop ở epoch %d (best ep %d, f1=%.4f).", ep, best_ep, best_f1)
                break

    logger.info("XONG. Best val f1=%.4f (epoch %d). Checkpoint: %s/best.pt",
                best_f1, best_ep, run_dir)

    # Đánh giá cuối cùng trên TEST set bằng checkpoint tốt nhất + xuất đồ thị (S6.1)
    fig_dir = run_dir / "figures"
    plot_training_curves(history, fig_dir / "training_curves.png")

    ckpt = torch.load(run_dir / "best.pt", map_location=device, weights_only=False)
    model.load_state_dict(ckpt["model_state"])
    ys, ps, probs = predict(model, test_ld, device)
    test_metrics = save_evaluation_report(ys, ps, probs, fig_dir, prefix="test")
    logger.info("Test (best ep %d) acc=%.4f f1=%.4f auc=%.4f | figures: %s",
                best_ep, test_metrics["acc"], test_metrics["f1"],
                test_metrics["roc_auc"], fig_dir)

    # Chi phí (S5b.2 — accuracy-vs-cost): GPU mem đỉnh + FLOPs, độc lập tốc độ máy
    n_in = len(train_ds[0][0]) if len(train_ds) else 3
    peak_mem_mb = (torch.cuda.max_memory_allocated() / 1024**2) if device == "cuda" else None
    try:
        from thop import profile
        dummy = torch.randn(1, n_in, img_size, img_size, device=device)
        was_training = model.training
        model.eval()
        macs, n_params = profile(model, inputs=(dummy,), verbose=False)
        model.train(was_training)
        gmacs, params_m = macs / 1e9, n_params / 1e6
    except Exception as e:  # thop có thể lỗi với vài kiến trúc — không chặn kết quả chính
        logger.warning("Không đo được FLOPs (%s)", e)
        gmacs, params_m = None, None

    cost = {
        "run_name": run,
        "model": get(cfg, "model.name", "vgg16"),
        "channels": get(cfg, "data.channels", "full"),
        "in_chans": get(cfg, "model.in_chans", 3),
        "img_size": img_size,
        "batch_size": get(cfg, "data.batch_size", 32),
        "grad_accum_steps": accum,
        "effective_batch_size": get(cfg, "data.batch_size", 32) * accum,
        "n_epochs": len(history),
        "best_epoch": best_ep,
        "total_time_s": sum(h["epoch_time_s"] for h in history),
        "avg_epoch_time_s": sum(h["epoch_time_s"] for h in history) / len(history),
        "peak_gpu_mem_mb": peak_mem_mb,
        "gmacs": gmacs,
        "params_m": params_m,
        "device_name": torch.cuda.get_device_name(0) if device == "cuda" else "cpu",
    }
    (run_dir / "cost.json").write_text(json.dumps(cost, indent=2, ensure_ascii=False))
    logger.info("Cost: epoch=%.1fs peak_mem=%.0fMB gmacs=%s params=%.1fM eff_batch=%d",
                cost["avg_epoch_time_s"], peak_mem_mb or -1, gmacs, params_m or -1,
                cost["effective_batch_size"])


if __name__ == "__main__":
    main()
