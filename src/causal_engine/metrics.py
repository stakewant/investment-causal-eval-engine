from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Callable, Sequence
from typing import Any


def mean_absolute_error(gold: Sequence[float], predicted: Sequence[float]) -> float:
    _same_nonempty(gold, predicted)
    return sum(abs(a - b) for a, b in zip(gold, predicted)) / len(gold)


def root_mean_squared_error(gold: Sequence[float], predicted: Sequence[float]) -> float:
    _same_nonempty(gold, predicted)
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(gold, predicted)) / len(gold))


def quadratic_weighted_kappa(
    gold: Sequence[int],
    predicted: Sequence[int],
    *,
    minimum: int = 1,
    maximum: int = 5,
) -> float:
    _same_nonempty(gold, predicted)
    categories = maximum - minimum + 1
    observed = [[0.0] * categories for _ in range(categories)]
    gold_hist = [0.0] * categories
    predicted_hist = [0.0] * categories
    for actual, guess in zip(gold, predicted):
        if not minimum <= actual <= maximum or not minimum <= guess <= maximum:
            raise ValueError("rating outside configured QWK range")
        i, j = actual - minimum, guess - minimum
        observed[i][j] += 1
        gold_hist[i] += 1
        predicted_hist[j] += 1
    denominator_scale = max(1, (categories - 1) ** 2)
    observed_disagreement = 0.0
    expected_disagreement = 0.0
    total = float(len(gold))
    for i in range(categories):
        for j in range(categories):
            weight = ((i - j) ** 2) / denominator_scale
            observed_disagreement += weight * observed[i][j] / total
            expected_disagreement += weight * (gold_hist[i] * predicted_hist[j]) / (total * total)
    if expected_disagreement == 0:
        return 1.0 if observed_disagreement == 0 else 0.0
    return 1.0 - observed_disagreement / expected_disagreement


def macro_f1(gold: Sequence[str], predicted: Sequence[str]) -> float:
    _same_nonempty(gold, predicted)
    labels = sorted(set(gold) | set(predicted))
    scores = []
    for label in labels:
        tp = sum(a == label and b == label for a, b in zip(gold, predicted))
        fp = sum(a != label and b == label for a, b in zip(gold, predicted))
        fn = sum(a == label and b != label for a, b in zip(gold, predicted))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


def exact_match(gold: Sequence[Any], predicted: Sequence[Any]) -> float:
    _same_nonempty(gold, predicted)
    return sum(a == b for a, b in zip(gold, predicted)) / len(gold)


def expected_calibration_error(
    correct: Sequence[bool], confidence: Sequence[float], *, bins: int = 10
) -> float:
    _same_nonempty(correct, confidence)
    total = len(correct)
    error = 0.0
    for bin_index in range(bins):
        low, high = bin_index / bins, (bin_index + 1) / bins
        members = [
            index
            for index, value in enumerate(confidence)
            if (low <= value <= high if bin_index == bins - 1 else low <= value < high)
        ]
        if not members:
            continue
        accuracy = sum(bool(correct[index]) for index in members) / len(members)
        average_confidence = sum(confidence[index] for index in members) / len(members)
        error += len(members) / total * abs(accuracy - average_confidence)
    return error


def span_f1(
    gold_spans: Sequence[tuple[int, int, str]],
    predicted_spans: Sequence[tuple[int, int, str]],
) -> dict[str, float]:
    gold_set = set(gold_spans)
    predicted_set = set(predicted_spans)
    true_positive = len(gold_set & predicted_set)
    precision = true_positive / len(predicted_set) if predicted_set else 0.0
    recall = true_positive / len(gold_set) if gold_set else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def bootstrap_confidence_interval(
    gold: Sequence[Any],
    predicted: Sequence[Any],
    metric: Callable[[Sequence[Any], Sequence[Any]], float],
    *,
    samples: int = 1000,
    confidence: float = 0.95,
    seed: int = 20260819,
) -> dict[str, float]:
    _same_nonempty(gold, predicted)
    rng = random.Random(seed)
    values = []
    for _ in range(samples):
        indices = [rng.randrange(len(gold)) for _ in gold]
        values.append(metric([gold[index] for index in indices], [predicted[index] for index in indices]))
    values.sort()
    alpha = (1 - confidence) / 2
    lower = values[min(len(values) - 1, int(alpha * len(values)))]
    upper = values[min(len(values) - 1, int((1 - alpha) * len(values)) - 1)]
    return {"estimate": metric(gold, predicted), "lower": lower, "upper": upper, "confidence": confidence}


def group_bootstrap_confidence_interval(
    gold: Sequence[Any],
    predicted: Sequence[Any],
    groups: Sequence[str],
    metric: Callable[[Sequence[Any], Sequence[Any]], float],
    *,
    samples: int = 1000,
    confidence: float = 0.95,
    seed: int = 20260819,
) -> dict[str, float]:
    _same_nonempty(gold, predicted)
    if len(groups) != len(gold):
        raise ValueError("group labels must match metric input length")
    by_group: dict[str, list[int]] = {}
    for index, group in enumerate(groups):
        by_group.setdefault(str(group), []).append(index)
    group_ids = sorted(by_group)
    if not group_ids:
        raise ValueError("at least one bootstrap group is required")
    rng = random.Random(seed)
    values = []
    for _ in range(samples):
        sampled_groups = [rng.choice(group_ids) for _ in group_ids]
        indices = [index for group in sampled_groups for index in by_group[group]]
        values.append(metric([gold[index] for index in indices], [predicted[index] for index in indices]))
    values.sort()
    alpha = (1 - confidence) / 2
    lower = values[min(len(values) - 1, int(alpha * len(values)))]
    upper = values[min(len(values) - 1, int((1 - alpha) * len(values)) - 1)]
    return {"estimate": metric(gold, predicted), "lower": lower, "upper": upper, "confidence": confidence}


def inter_rater_report(ratings: Sequence[Sequence[float]]) -> dict[str, float]:
    if len(ratings) < 2 or any(len(row) < 2 for row in ratings):
        raise ValueError("at least two items and two raters are required")
    width = len(ratings[0])
    if any(len(row) != width for row in ratings):
        raise ValueError("all rating rows must have equal width")
    first = [int(round(row[0])) for row in ratings]
    second = [int(round(row[1])) for row in ratings]
    return {
        "pairwise_qwk": quadratic_weighted_kappa(first, second),
        "pairwise_mae": mean_absolute_error(first, second),
        "exact_agreement": exact_match(first, second),
        "icc_absolute_single": _icc_absolute_single(ratings),
    }


def _icc_absolute_single(ratings: Sequence[Sequence[float]]) -> float:
    n, k = len(ratings), len(ratings[0])
    grand = sum(sum(row) for row in ratings) / (n * k)
    row_means = [sum(row) / k for row in ratings]
    col_means = [sum(row[column] for row in ratings) / n for column in range(k)]
    ms_rows = k * sum((value - grand) ** 2 for value in row_means) / (n - 1)
    ms_cols = n * sum((value - grand) ** 2 for value in col_means) / (k - 1)
    residual = sum(
        (ratings[row][column] - row_means[row] - col_means[column] + grand) ** 2
        for row in range(n)
        for column in range(k)
    )
    ms_error = residual / ((n - 1) * (k - 1))
    denominator = ms_rows + (k - 1) * ms_error + k * (ms_cols - ms_error) / n
    return (ms_rows - ms_error) / denominator if denominator else 1.0


def classification_report(gold: Sequence[str], predicted: Sequence[str]) -> dict[str, Any]:
    _same_nonempty(gold, predicted)
    return {
        "count": len(gold),
        "macro_f1": macro_f1(gold, predicted),
        "accuracy": exact_match(gold, predicted),
        "gold_distribution": dict(Counter(gold)),
        "predicted_distribution": dict(Counter(predicted)),
    }


def _same_nonempty(left: Sequence[Any], right: Sequence[Any]) -> None:
    if not left or len(left) != len(right):
        raise ValueError("metric inputs must be non-empty and have equal length")
