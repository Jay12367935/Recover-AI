from __future__ import annotations

import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import ACTION_ORDER
from .features import feature_names, vectorize


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1 / (1 + z)
    z = math.exp(value)
    return z / (1 + z)


class RecoveryModel:
    def __init__(self, weights: list[float] | None = None, metadata: dict[str, Any] | None = None):
        self.names = feature_names()
        self.weights = weights or [0.0 for _ in self.names]
        self.metadata = metadata or {}

    def predict_one(self, payment: dict[str, Any], action: str) -> float:
        features = vectorize(payment, action)
        score = sum(weight * value for weight, value in zip(self.weights, features))
        return round(max(0.01, min(0.98, sigmoid(score))), 4)

    def predict_actions(self, payment: dict[str, Any]) -> dict[str, float]:
        return {action: self.predict_one(payment, action) for action in ACTION_ORDER}

    def train(
        self,
        rows: list[dict[str, Any]],
        epochs: int = 11,
        learning_rate: float = 0.08,
        l2: float = 0.0008,
        seed: int = 42,
    ) -> dict[str, Any]:
        rng = random.Random(seed)
        data = rows[:]
        split = max(1, int(len(data) * 0.82))
        rng.shuffle(data)
        train_rows = data[:split]
        validation_rows = data[split:]

        for epoch in range(epochs):
            rng.shuffle(train_rows)
            lr = learning_rate / (1 + epoch * 0.18)
            for row in train_rows:
                action = str(row["action"])
                y = float(row["recovered"])
                x = vectorize(row, action)
                pred = sigmoid(sum(weight * value for weight, value in zip(self.weights, x)))
                error = pred - y
                for idx, value in enumerate(x):
                    if value:
                        self.weights[idx] -= lr * (error * value + l2 * self.weights[idx])

        metrics = self.evaluate(validation_rows or train_rows)
        metrics.update(
            {
                "trained_rows": len(train_rows),
                "validation_rows": len(validation_rows),
                "feature_count": len(self.weights),
                "trained_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self.metadata = metrics
        return metrics

    def evaluate(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {"roc_auc": 0.0, "precision": 0.0, "recall": 0.0, "f1_score": 0.0, "brier_score": 0.0, "log_loss": 0.0}
        correct = 0
        brier = 0.0
        log_loss = 0.0
        scored: list[tuple[float, int]] = []
        tp = 0
        fp = 0
        fn = 0
        for row in rows:
            y = int(row["recovered"])
            p = self.predict_one(row, str(row["action"]))
            correct += 1 if (p >= 0.5) == bool(y) else 0
            if p >= 0.5 and y:
                tp += 1
            elif p >= 0.5 and not y:
                fp += 1
            elif p < 0.5 and y:
                fn += 1
            brier += (p - y) ** 2
            p_safe = max(0.001, min(0.999, p))
            log_loss += -(y * math.log(p_safe) + (1 - y) * math.log(1 - p_safe))
            scored.append((p, y))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return {
            "accuracy": round(correct / len(rows), 4),
            "roc_auc": round(self._roc_auc(scored), 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "brier_score": round(brier / len(rows), 4),
            "log_loss": round(log_loss / len(rows), 4),
        }

    def _roc_auc(self, scored: list[tuple[float, int]]) -> float:
        positives = sum(1 for _, label in scored if label == 1)
        negatives = len(scored) - positives
        if not positives or not negatives:
            return 0.0
        ranked = sorted(scored, key=lambda item: item[0])
        rank_sum = 0.0
        idx = 0
        while idx < len(ranked):
            end = idx + 1
            while end < len(ranked) and ranked[end][0] == ranked[idx][0]:
                end += 1
            average_rank = (idx + 1 + end) / 2
            for tie_idx in range(idx, end):
                if ranked[tie_idx][1] == 1:
                    rank_sum += average_rank
            idx = end
        return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "feature_names": self.names,
            "weights": self.weights,
            "metadata": self.metadata,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "RecoveryModel":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        names = feature_names()
        stored_names = payload.get("feature_names", [])
        if stored_names != names:
            raise ValueError("Stored model feature schema does not match current code.")
        return cls(weights=[float(value) for value in payload["weights"]], metadata=payload.get("metadata", {}))
