"""
factory.py — Giai đoạn 4 (S4.1)
-------------------------------
Khởi tạo model phân loại ảnh (pretrained ImageNet), thay lớp cuối theo số lớp.
Hỗ trợ: vgg16, resnet50, densenet121, convnext_tiny.

- Mặc định `in_chans=3` (ảnh composite 3 kênh) → dùng pretrained trực tiếp.
- `in_chans=1` (ảnh xám 1 kênh, cho ablation): tự sửa lớp conv ĐẦU thành 1 kênh và
  khởi tạo trọng số = TỔNG 3 kênh pretrained → đầu ra tương đương "gray×3" lúc khởi tạo
  (bắt đầu công bằng, chỉ khác số kênh đầu vào chứ không mất tri thức pretrained).
"""

from __future__ import annotations

import torch
import torch.nn as nn
from torchvision import models


def _set_requires_grad(module: nn.Module, flag: bool) -> None:
    for p in module.parameters():
        p.requires_grad = flag


def _new_first_conv(old: nn.Conv2d, in_chans: int) -> nn.Conv2d:
    """Tạo conv đầu mới với in_chans kênh, kế thừa trọng số pretrained."""
    new = nn.Conv2d(in_chans, old.out_channels, kernel_size=old.kernel_size,
                    stride=old.stride, padding=old.padding, dilation=old.dilation,
                    groups=old.groups, bias=(old.bias is not None))
    with torch.no_grad():
        w = old.weight  # (out, in_old, kh, kw)
        if in_chans == 1:
            new.weight.copy_(w.sum(dim=1, keepdim=True))      # tổng kênh → ~ gray×3
        elif in_chans <= w.shape[1]:
            new.weight.copy_(w[:, :in_chans])
        else:
            reps = (in_chans + w.shape[1] - 1) // w.shape[1]
            new.weight.copy_(w.repeat(1, reps, 1, 1)[:, :in_chans])
        if old.bias is not None:
            new.bias.copy_(old.bias)
    return new


def build_model(name: str,
                num_classes: int = 2,
                pretrained: bool = True,
                freeze_backbone: bool = False,
                in_chans: int = 3) -> nn.Module:
    """
    Args:
        name: vgg16 | resnet50 | densenet121 | convnext_tiny
        num_classes: số lớp đầu ra (2 cho phát hiện nhị phân).
        pretrained: dùng trọng số ImageNet.
        freeze_backbone: True → đóng băng backbone, chỉ train head.
        in_chans: số kênh đầu vào (3 mặc định; 1 cho ablation ảnh xám thuần).
    """
    name = name.lower()

    if name == "vgg16":
        w = models.VGG16_Weights.IMAGENET1K_V1 if pretrained else None
        m = models.vgg16(weights=w)
        m.classifier[6] = nn.Linear(m.classifier[6].in_features, num_classes)
        head = m.classifier[6]
        if in_chans != 3:
            m.features[0] = _new_first_conv(m.features[0], in_chans)

    elif name == "resnet50":
        w = models.ResNet50_Weights.IMAGENET1K_V2 if pretrained else None
        m = models.resnet50(weights=w)
        m.fc = nn.Linear(m.fc.in_features, num_classes)
        head = m.fc
        if in_chans != 3:
            m.conv1 = _new_first_conv(m.conv1, in_chans)

    elif name == "densenet121":
        w = models.DenseNet121_Weights.IMAGENET1K_V1 if pretrained else None
        m = models.densenet121(weights=w)
        m.classifier = nn.Linear(m.classifier.in_features, num_classes)
        head = m.classifier
        if in_chans != 3:
            m.features.conv0 = _new_first_conv(m.features.conv0, in_chans)

    elif name in ("convnext_tiny", "convnext"):
        w = models.ConvNeXt_Tiny_Weights.IMAGENET1K_V1 if pretrained else None
        m = models.convnext_tiny(weights=w)
        m.classifier[2] = nn.Linear(m.classifier[2].in_features, num_classes)
        head = m.classifier[2]
        if in_chans != 3:
            m.features[0][0] = _new_first_conv(m.features[0][0], in_chans)

    else:
        raise ValueError(f"Model chưa hỗ trợ: {name}")

    if freeze_backbone:
        _set_requires_grad(m, False)
        _set_requires_grad(head, True)   # chỉ train head

    return m


__all__ = ["build_model"]
