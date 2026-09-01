from __future__ import annotations

import math
from typing import Any

from .constants import ACTION_ORDER, BANKS, FAILURE_CODES, MERCHANT_CATEGORIES, PAYMENT_METHODS


NUMERIC_FEATURES = [
    "amount_scaled",
    "hour_scaled",
    "day_scaled",
    "previous_success_scaled",
    "previous_failures_scaled",
    "attempt_scaled",
    "time_since_last_attempt_scaled",
    "customer_age_scaled",
    "previous_recovery_success",
    "risk_score",
]

CATEGORICAL_SPACES = {
    "method": PAYMENT_METHODS,
    "bank": BANKS,
    "failure_code": FAILURE_CODES,
    "merchant_category": MERCHANT_CATEGORIES,
    "action": ACTION_ORDER,
}


def feature_names() -> list[str]:
    names = ["bias"]
    names.extend(NUMERIC_FEATURES)
    for field, values in CATEGORICAL_SPACES.items():
        names.extend([f"{field}={value}" for value in values])
    return names


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def vectorize(payment: dict[str, Any], action: str) -> list[float]:
    amount = max(_float(payment.get("amount")), 1.0)
    hour = max(0.0, min(23.0, _float(payment.get("hour"))))
    day = max(0.0, min(6.0, _float(payment.get("day_of_week"))))
    previous_success = max(0.0, _float(payment.get("customer_previous_success")))
    previous_failures = max(0.0, _float(payment.get("customer_previous_failures")))
    attempt_number = max(1.0, _float(payment.get("attempt_number"), 1.0))
    time_since_last = max(0.0, _float(payment.get("time_since_last_attempt")))
    customer_age = max(0.0, _float(payment.get("customer_age_days")))
    previous_recovery_success = max(0.0, min(1.0, _float(payment.get("previous_recovery_success"))))
    risk_score = max(0.0, min(1.0, _float(payment.get("risk_score"))))

    values = [
        1.0,
        min(math.log1p(amount) / math.log(100000), 1.2),
        hour / 23.0,
        day / 6.0,
        min(previous_success / 20.0, 1.0),
        min(previous_failures / 10.0, 1.0),
        min(attempt_number / 5.0, 1.0),
        min(time_since_last / 180.0, 1.0),
        min(customer_age / 1000.0, 1.0),
        previous_recovery_success,
        risk_score,
    ]

    for field, choices in CATEGORICAL_SPACES.items():
        observed = action if field == "action" else str(payment.get(field, "")).lower()
        if field in {"bank", "failure_code"}:
            observed = str(payment.get(field, "")).upper()
        for choice in choices:
            values.append(1.0 if observed == choice else 0.0)

    return values

