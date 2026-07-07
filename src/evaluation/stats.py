"""
stats.py — Kiểm định thống kê cho lưới hợp nhất (S5b.1, trục độ phân giải)
--------------------------------------------------------------------------
docs/EXPERIMENTS.md §6 yêu cầu: mọi phát biểu "224 ≈ 336 ≈ 448" phải kèm
kiểm định ý nghĩa (paired t-test trên seed, hoặc McNemar trên dự đoán test).

Module này cung cấp paired t-test (dùng điểm số theo từng seed — luôn có sẵn
từ cost.json/test_metrics.json, không cần sửa train.py) và McNemar test khi có
sẵn dự đoán từng mẫu (tuỳ chọn, ít dùng vì train.py hiện không lưu raw predictions).
"""

from __future__ import annotations

from scipy import stats as _stats


def paired_ttest(scores_a: list[float], scores_b: list[float]) -> dict:
    """
    So sánh 2 nhóm điểm số ĐÃ GHÉP CẶP theo seed (cùng thứ tự seed ở 2 danh sách).

    Trả về dict: {"t_stat", "p_value", "mean_diff", "significant" (p<0.05),
                  "n"}. "significant=False" → kết luận đúng là "tương đương
                  trong nhiễu" (docs/EXPERIMENTS.md §6), không phải "bằng nhau".
    """
    if len(scores_a) != len(scores_b):
        raise ValueError(f"Hai nhóm phải cùng số seed đã ghép cặp: {len(scores_a)} vs {len(scores_b)}")
    if len(scores_a) < 2:
        return {"t_stat": float("nan"), "p_value": float("nan"),
                "mean_diff": float("nan"), "significant": False, "n": len(scores_a)}

    t_stat, p_value = _stats.ttest_rel(scores_a, scores_b)
    mean_diff = sum(scores_a) / len(scores_a) - sum(scores_b) / len(scores_b)
    return {
        "t_stat": float(t_stat),
        "p_value": float(p_value),
        "mean_diff": float(mean_diff),
        "significant": bool(p_value < 0.05),
        "n": len(scores_a),
    }


def mcnemar_test(y_true: list[int], pred_a: list[int], pred_b: list[int]) -> dict:
    """
    McNemar test trên dự đoán CÙNG một tập test của 2 model (so hai cấu hình
    trực tiếp trên từng mẫu, thay vì qua seed). Cần list dự đoán nhị phân
    cùng độ dài, cùng thứ tự mẫu.

    Trả về dict: {"b", "c" (số mẫu 2 model bất đồng), "statistic", "p_value",
                  "significant"}. b = A đúng/B sai, c = A sai/B đúng.
    Dùng correction liên tục (Edwards) khi b+c nhỏ; xấp xỉ chi-square 1 bậc tự do.
    """
    if not (len(y_true) == len(pred_a) == len(pred_b)):
        raise ValueError("y_true, pred_a, pred_b phải cùng độ dài (cùng tập mẫu).")

    b = c = 0  # b: A đúng, B sai | c: A sai, B đúng
    for yt, pa, pb in zip(y_true, pred_a, pred_b):
        a_correct = (pa == yt)
        b_correct = (pb == yt)
        if a_correct and not b_correct:
            b += 1
        elif b_correct and not a_correct:
            c += 1

    n_disagree = b + c
    if n_disagree == 0:
        return {"b": b, "c": c, "statistic": 0.0, "p_value": 1.0, "significant": False}

    # Continuity-corrected McNemar (chuẩn khi b+c nhỏ, vẫn đúng khi lớn)
    statistic = (abs(b - c) - 1) ** 2 / n_disagree
    p_value = float(1 - _stats.chi2.cdf(statistic, df=1))
    return {"b": b, "c": c, "statistic": float(statistic), "p_value": p_value,
            "significant": bool(p_value < 0.05)}


__all__ = ["paired_ttest", "mcnemar_test"]
