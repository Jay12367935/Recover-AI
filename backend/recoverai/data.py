from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from .constants import ACTION_ORDER, BANKS, FAILURE_CODES, MERCHANT_CATEGORIES, PAYMENT_METHODS


INDIAN_NAMES = [
    "Aarav",
    "Ananya",
    "Vihaan",
    "Isha",
    "Kabir",
    "Meera",
    "Rahul",
    "Priya",
    "Arjun",
    "Sneha",
    "Rohan",
    "Nisha",
    "Dev",
    "Kavya",
    "Aditya",
    "Tara",
]


def clamp(value: float, low: float = 0.02, high: float = 0.96) -> float:
    return max(low, min(high, value))


def weighted_choice(rng: random.Random, weighted_values: list[tuple[str, float]]) -> str:
    total = sum(weight for _, weight in weighted_values)
    point = rng.random() * total
    upto = 0.0
    for value, weight in weighted_values:
        upto += weight
        if upto >= point:
            return value
    return weighted_values[-1][0]


def generate_customers(count: int = 1200, seed: int = 42) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    customers: list[dict[str, Any]] = []
    for idx in range(1, count + 1):
        name = f"{rng.choice(INDIAN_NAMES)} {chr(64 + rng.randint(1, 26))}."
        previous_success = max(0, int(rng.gauss(5, 4)))
        previous_failures = max(0, int(rng.gauss(1.5, 1.3)))
        age_days = rng.randint(10, 900)
        customers.append(
            {
                "id": f"cust_{idx:05d}",
                "name": name,
                "phone": f"+91{rng.randint(7000000000, 9999999999)}",
                "email": f"customer{idx}@example.com",
                "customer_previous_success": previous_success,
                "customer_previous_failures": previous_failures,
                "customer_age_days": age_days,
                "previous_recovery_success": round(rng.betavariate(2 + previous_success, 4 + previous_failures), 3),
            }
        )
    return customers


def _amount(rng: random.Random) -> int:
    buckets = [
        (299, 0.08),
        (799, 0.15),
        (1499, 0.18),
        (2499, 0.18),
        (4999, 0.17),
        (8999, 0.10),
        (12999, 0.07),
        (18000, 0.04),
        (32000, 0.03),
    ]
    base = weighted_choice(rng, [(str(value), weight) for value, weight in buckets])
    jitter = rng.randint(-80, 180)
    return max(99, int(base) + jitter)


def _failure_for_method(rng: random.Random, method: str) -> str:
    if method == "upi":
        weights = [
            ("BANK_ERROR", 0.23),
            ("GATEWAY_TIMEOUT", 0.16),
            ("NETWORK_ERROR", 0.12),
            ("UPI_COLLECT_EXPIRED", 0.17),
            ("USER_CANCELLED", 0.14),
            ("INSUFFICIENT_FUNDS", 0.08),
            ("RISK_CHECK_FAILED", 0.04),
            ("UNKNOWN", 0.06),
        ]
    elif method == "card":
        weights = [
            ("AUTHENTICATION_FAILED", 0.22),
            ("CARD_DECLINED", 0.21),
            ("INSUFFICIENT_FUNDS", 0.16),
            ("BANK_ERROR", 0.13),
            ("USER_CANCELLED", 0.12),
            ("RISK_CHECK_FAILED", 0.07),
            ("UNKNOWN", 0.09),
        ]
    elif method == "netbanking":
        weights = [
            ("BANK_ERROR", 0.25),
            ("GATEWAY_TIMEOUT", 0.20),
            ("AUTHENTICATION_FAILED", 0.16),
            ("USER_CANCELLED", 0.12),
            ("NETWORK_ERROR", 0.10),
            ("RISK_CHECK_FAILED", 0.06),
            ("UNKNOWN", 0.11),
        ]
    else:
        weights = [
            ("PAYMENT_METHOD_ISSUE", 0.28),
            ("USER_CANCELLED", 0.18),
            ("NETWORK_ERROR", 0.15),
            ("BANK_ERROR", 0.12),
            ("INSUFFICIENT_FUNDS", 0.10),
            ("RISK_CHECK_FAILED", 0.05),
            ("UNKNOWN", 0.12),
        ]
    return weighted_choice(rng, weights)


def build_failed_payment(
    idx: int,
    customer: dict[str, Any],
    rng: random.Random,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    method = weighted_choice(
        rng,
        [("upi", 0.44), ("card", 0.28), ("netbanking", 0.14), ("wallet", 0.09), ("emi", 0.05)],
    )
    failure_code = _failure_for_method(rng, method)
    ts = created_at or (datetime.now(timezone.utc) - timedelta(minutes=rng.randint(2, 60 * 72)))
    amount = _amount(rng)
    risk_base = 0.08 + (amount / 100000) + (0.12 if failure_code == "RISK_CHECK_FAILED" else 0)
    risk_base += 0.06 if customer["customer_previous_failures"] > customer["customer_previous_success"] else 0
    risk_score = clamp(rng.gauss(risk_base, 0.08), 0.01, 0.98)

    return {
        "id": f"pay_{idx:06d}",
        "order_id": f"order_{idx:06d}",
        "customer_id": customer["id"],
        "customer_name": customer["name"],
        "phone": customer["phone"],
        "email": customer["email"],
        "amount": amount,
        "method": method,
        "bank": rng.choice(BANKS),
        "status": "failed",
        "failure_code": failure_code,
        "created_at": ts.isoformat(),
        "hour": ts.hour,
        "day_of_week": ts.weekday(),
        "attempt_number": rng.choices([1, 2, 3, 4], [0.58, 0.26, 0.12, 0.04])[0],
        "time_since_last_attempt": rng.randint(0, 180),
        "merchant_category": rng.choice(MERCHANT_CATEGORIES),
        "customer_previous_success": customer["customer_previous_success"],
        "customer_previous_failures": customer["customer_previous_failures"],
        "customer_age_days": customer["customer_age_days"],
        "previous_recovery_success": customer["previous_recovery_success"],
        "risk_score": round(risk_score, 3),
    }


def true_recovery_probability(payment: dict[str, Any], action: str) -> float:
    failure = str(payment.get("failure_code", "UNKNOWN")).upper()
    method = str(payment.get("method", "upi")).lower()
    amount = float(payment.get("amount", 0))
    hour = int(payment.get("hour", 12))
    previous_success = float(payment.get("customer_previous_success", 0))
    previous_failures = float(payment.get("customer_previous_failures", 0))
    attempt = float(payment.get("attempt_number", 1))
    previous_recovery = float(payment.get("previous_recovery_success", 0.3))
    risk_score = float(payment.get("risk_score", 0.1))

    base_by_action = {
        "retry_immediate": 0.25,
        "retry_30m": 0.39,
        "payment_link": 0.48,
        "alternate_method": 0.52,
        "human_review": 0.22,
        "no_retry": 0.03,
    }
    p = base_by_action.get(action, 0.2)

    if failure in {"BANK_ERROR", "GATEWAY_TIMEOUT", "NETWORK_ERROR"}:
        if action == "retry_30m":
            p += 0.24
        if action == "retry_immediate":
            p += 0.07
        if action == "payment_link":
            p += 0.08
    if failure in {"INSUFFICIENT_FUNDS", "UPI_COLLECT_EXPIRED"}:
        if action == "payment_link":
            p += 0.18
        if action == "alternate_method":
            p += 0.14
        if action == "retry_immediate":
            p -= 0.13
    if failure in {"AUTHENTICATION_FAILED", "CARD_DECLINED", "PAYMENT_METHOD_ISSUE"}:
        if action == "alternate_method":
            p += 0.25
        if action == "payment_link":
            p += 0.10
        if action == "retry_immediate":
            p -= 0.08
    if failure == "USER_CANCELLED":
        p -= 0.16
        if action == "payment_link":
            p += 0.10
        if action == "no_retry":
            p += 0.08
    if failure == "RISK_CHECK_FAILED":
        p -= 0.28
        if action == "human_review":
            p += 0.25
        if action in {"retry_immediate", "retry_30m", "payment_link", "alternate_method"}:
            p -= 0.18

    if method == "upi" and action == "alternate_method":
        p += 0.09
    if method == "card" and action == "alternate_method":
        p += 0.07
    if method == "netbanking" and action == "retry_30m":
        p += 0.08

    p += min(previous_success, 14) * 0.018
    p -= min(previous_failures, 8) * 0.024
    p += (previous_recovery - 0.35) * 0.22
    p -= max(attempt - 1, 0) * 0.055
    p -= min(amount / 60000, 0.35)
    p -= risk_score * 0.38

    if 21 <= hour or hour <= 2:
        if action == "retry_30m":
            p += 0.08
        if action == "retry_immediate":
            p -= 0.04
    if 9 <= hour <= 13 and action in {"payment_link", "alternate_method"}:
        p += 0.04

    return round(clamp(p), 4)


def choose_historical_action(payment: dict[str, Any], rng: random.Random) -> str:
    failure = str(payment.get("failure_code", "UNKNOWN")).upper()
    if failure == "RISK_CHECK_FAILED" or float(payment.get("risk_score", 0)) > 0.78:
        return weighted_choice(rng, [("human_review", 0.75), ("no_retry", 0.15), ("payment_link", 0.10)])
    if failure in {"BANK_ERROR", "GATEWAY_TIMEOUT", "NETWORK_ERROR"}:
        return weighted_choice(rng, [("retry_30m", 0.42), ("retry_immediate", 0.24), ("payment_link", 0.20), ("alternate_method", 0.10), ("no_retry", 0.04)])
    if failure in {"AUTHENTICATION_FAILED", "CARD_DECLINED", "PAYMENT_METHOD_ISSUE"}:
        return weighted_choice(rng, [("alternate_method", 0.40), ("payment_link", 0.26), ("retry_30m", 0.14), ("retry_immediate", 0.10), ("no_retry", 0.10)])
    if failure == "USER_CANCELLED":
        return weighted_choice(rng, [("payment_link", 0.32), ("no_retry", 0.31), ("alternate_method", 0.18), ("retry_30m", 0.12), ("retry_immediate", 0.07)])
    return weighted_choice(rng, [("payment_link", 0.30), ("alternate_method", 0.24), ("retry_30m", 0.20), ("retry_immediate", 0.14), ("no_retry", 0.12)])


def generate_historical_attempts(count: int = 50000, seed: int = 42) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    customers = generate_customers(max(300, count // 35), seed)
    rows: list[dict[str, Any]] = []
    for idx in range(1, count + 1):
        customer = rng.choice(customers)
        created_at = datetime.now(timezone.utc) - timedelta(days=rng.randint(1, 180), minutes=rng.randint(0, 1440))
        payment = build_failed_payment(idx, customer, rng, created_at)
        action = choose_historical_action(payment, rng)
        probability = true_recovery_probability(payment, action)
        recovered = 1 if rng.random() < probability else 0
        rows.append({**payment, "action": action, "recovered": recovered, "true_probability": probability})
    return rows


def generate_demo_failed_payments(count: int = 180, seed: int = 99) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    customers = generate_customers(220, seed + 5)
    payments: list[dict[str, Any]] = []
    for idx in range(1, count + 1):
        payment = build_failed_payment(idx, rng.choice(customers), rng)
        payment["id"] = f"pay_demo_{idx:04d}"
        payment["order_id"] = f"order_demo_{idx:04d}"
        payments.append(payment)

    showcase = [
        {
            "id": "pay_showcase_4999",
            "order_id": "order_showcase_4999",
            "customer_id": "cust_showcase_rahul",
            "customer_name": "Rahul S.",
            "phone": "+919876543210",
            "email": "rahul@example.com",
            "amount": 4999,
            "method": "upi",
            "bank": "HDFC",
            "status": "failed",
            "failure_code": "BANK_ERROR",
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=14)).isoformat(),
            "hour": 22,
            "day_of_week": 4,
            "attempt_number": 1,
            "time_since_last_attempt": 12,
            "merchant_category": "edtech",
            "customer_previous_success": 8,
            "customer_previous_failures": 1,
            "customer_age_days": 420,
            "previous_recovery_success": 0.71,
            "risk_score": 0.09,
        },
        {
            "id": "pay_showcase_18000",
            "order_id": "order_showcase_18000",
            "customer_id": "cust_showcase_review",
            "customer_name": "Nisha R.",
            "phone": "+919123456780",
            "email": "nisha@example.com",
            "amount": 18000,
            "method": "card",
            "bank": "ICICI",
            "status": "failed",
            "failure_code": "RISK_CHECK_FAILED",
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=7)).isoformat(),
            "hour": 19,
            "day_of_week": 2,
            "attempt_number": 1,
            "time_since_last_attempt": 0,
            "merchant_category": "gaming",
            "customer_previous_success": 0,
            "customer_previous_failures": 4,
            "customer_age_days": 16,
            "previous_recovery_success": 0.11,
            "risk_score": 0.91,
        },
    ]
    return showcase + payments

