from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter
from pathlib import Path
from typing import Any

MODEL_FORMAT_VERSION = "hashed-softmax-v1"


def _features(text: str, dimensions: int) -> dict[int, float]:
    normalized = " ".join(text.casefold().split())
    tokens = normalized.split()
    grams = list(tokens)
    compact = normalized.replace(" ", "")
    for width in (2, 3, 4):
        grams.extend(compact[index : index + width] for index in range(max(0, len(compact) - width + 1)))
    counts = Counter(grams)
    result: dict[int, float] = {}
    for gram, count in counts.items():
        index = int(hashlib.sha256(gram.encode("utf-8")).hexdigest()[:16], 16) % dimensions
        result[index] = result.get(index, 0.0) + 1.0 + math.log(count)
    norm = math.sqrt(sum(value * value for value in result.values())) or 1.0
    return {index: value / norm for index, value in result.items()}


class HashedSoftmaxClassifier:
    """Small reproducible learned baseline for annotation experiments.

    It is intentionally not the production score authority. It supplies calibrated
    candidates to the same validators used by neural or LLM extractors.
    """

    def __init__(self, *, dimensions: int = 2048, seed: int = 20260819) -> None:
        self.dimensions = dimensions
        self.seed = seed
        self.labels: list[str] = []
        self.weights: list[list[float]] = []
        self.bias: list[float] = []

    def fit(
        self,
        texts: list[str],
        labels: list[str],
        *,
        epochs: int = 25,
        learning_rate: float = 0.08,
        l2: float = 0.0001,
    ) -> "HashedSoftmaxClassifier":
        if not texts or len(texts) != len(labels):
            raise ValueError("non-empty equal-length texts and labels are required")
        self.labels = sorted(set(labels))
        label_to_index = {label: index for index, label in enumerate(self.labels)}
        self.weights = [[0.0] * self.dimensions for _ in self.labels]
        self.bias = [0.0] * len(self.labels)
        examples = [(_features(text, self.dimensions), label_to_index[label]) for text, label in zip(texts, labels)]
        rng = random.Random(self.seed)
        for epoch in range(epochs):
            rng.shuffle(examples)
            rate = learning_rate / math.sqrt(1 + epoch * 0.2)
            for features, gold in examples:
                probabilities = self._probabilities(features)
                for label_index in range(len(self.labels)):
                    error = (1.0 if label_index == gold else 0.0) - probabilities[label_index]
                    self.bias[label_index] += rate * error
                    row = self.weights[label_index]
                    for feature_index, value in features.items():
                        row[feature_index] += rate * (error * value - l2 * row[feature_index])
        return self

    def predict_proba(self, text: str) -> dict[str, float]:
        probabilities = self._probabilities(_features(text, self.dimensions))
        return dict(zip(self.labels, probabilities))

    def predict(self, text: str) -> tuple[str, float]:
        probabilities = self.predict_proba(text)
        return max(probabilities.items(), key=lambda item: item[1])

    def _probabilities(self, features: dict[int, float]) -> list[float]:
        if not self.labels:
            raise ValueError("classifier has not been fitted")
        logits = [
            self.bias[index] + sum(self.weights[index][feature] * value for feature, value in features.items())
            for index in range(len(self.labels))
        ]
        maximum = max(logits)
        exponents = [math.exp(value - maximum) for value in logits]
        total = sum(exponents)
        return [value / total for value in exponents]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_format_version": MODEL_FORMAT_VERSION,
            "dimensions": self.dimensions,
            "seed": self.seed,
            "labels": self.labels,
            "weights": self.weights,
            "bias": self.bias,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "HashedSoftmaxClassifier":
        if value.get("model_format_version") != MODEL_FORMAT_VERSION:
            raise ValueError("unsupported classifier model format")
        model = cls(dimensions=int(value["dimensions"]), seed=int(value["seed"]))
        model.labels = [str(item) for item in value["labels"]]
        model.weights = [[float(cell) for cell in row] for row in value["weights"]]
        model.bias = [float(item) for item in value["bias"]]
        return model

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "HashedSoftmaxClassifier":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8-sig")))


class RubricCalibrator:
    """A compact feed-forward score calibrator for research, never score authority."""

    FORMAT = "rubric-calibrator-mlp-v1"

    def __init__(self, input_size: int, hidden_size: int = 8, seed: int = 20260819) -> None:
        self.input_size = input_size
        self.hidden_size = hidden_size
        rng = random.Random(seed)
        self.w1 = [[rng.uniform(-0.05, 0.05) for _ in range(input_size)] for _ in range(hidden_size)]
        self.b1 = [0.0] * hidden_size
        self.w2 = [rng.uniform(-0.05, 0.05) for _ in range(hidden_size)]
        self.b2 = 0.0

    def fit(self, features: list[list[float]], gold: list[float], *, epochs: int = 500, rate: float = 0.01) -> "RubricCalibrator":
        if not features or len(features) != len(gold) or any(len(row) != self.input_size for row in features):
            raise ValueError("invalid calibrator training matrix")
        for _ in range(epochs):
            for row, target in zip(features, gold):
                hidden_raw = [self.b1[h] + sum(self.w1[h][i] * row[i] for i in range(self.input_size)) for h in range(self.hidden_size)]
                hidden = [max(0.0, value) for value in hidden_raw]
                raw = self.b2 + sum(self.w2[h] * hidden[h] for h in range(self.hidden_size))
                output = 1.0 + 4.0 / (1.0 + math.exp(-raw))
                delta_out = 2 * (output - target) * (output - 1.0) * (5.0 - output) / 4.0
                old_w2 = self.w2[:]
                for h in range(self.hidden_size):
                    self.w2[h] -= rate * delta_out * hidden[h]
                self.b2 -= rate * delta_out
                for h in range(self.hidden_size):
                    delta_hidden = delta_out * old_w2[h] * (1.0 if hidden_raw[h] > 0 else 0.0)
                    for i in range(self.input_size):
                        self.w1[h][i] -= rate * delta_hidden * row[i]
                    self.b1[h] -= rate * delta_hidden
        return self

    def predict(self, row: list[float]) -> float:
        if len(row) != self.input_size:
            raise ValueError("calibrator feature width mismatch")
        hidden = [max(0.0, self.b1[h] + sum(self.w1[h][i] * row[i] for i in range(self.input_size))) for h in range(self.hidden_size)]
        raw = self.b2 + sum(self.w2[h] * hidden[h] for h in range(self.hidden_size))
        return 1.0 + 4.0 / (1.0 + math.exp(-raw))

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_format_version": self.FORMAT,
            "input_size": self.input_size,
            "hidden_size": self.hidden_size,
            "w1": self.w1,
            "b1": self.b1,
            "w2": self.w2,
            "b2": self.b2,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RubricCalibrator":
        if value.get("model_format_version") != cls.FORMAT:
            raise ValueError("unsupported rubric calibrator format")
        model = cls(int(value["input_size"]), int(value["hidden_size"]))
        model.w1 = [[float(cell) for cell in row] for row in value["w1"]]
        model.b1 = [float(cell) for cell in value["b1"]]
        model.w2 = [float(cell) for cell in value["w2"]]
        model.b2 = float(value["b2"])
        return model

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "RubricCalibrator":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8-sig")))
