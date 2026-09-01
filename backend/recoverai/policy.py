from __future__ import annotations

from typing import Any


def evaluate_policy(payment: dict[str, Any], recommended_action: str) -> dict[str, Any]:
    amount = float(payment.get("amount", 0))
    risk_score = float(payment.get("risk_score", 0))
    attempt = int(payment.get("attempt_number", 1))
    failure_code = str(payment.get("failure_code", "")).upper()

    controls: list[str] = []

    if recommended_action == "human_review":
        return {
            "allowed": True,
            "final_action": "human_review",
            "status": "review",
            "reason": "Agent selected human review as the safest recovery route.",
            "controls": ["human_review_is_non_money_moving"],
        }

    if recommended_action == "no_retry":
        return {
            "allowed": True,
            "final_action": "no_retry",
            "status": "allowed",
            "reason": "No money-moving API call is required.",
            "controls": ["no_retry_has_zero_financial_side_effect"],
        }

    if failure_code == "RISK_CHECK_FAILED":
        controls.append("risk_check_failed_requires_manual_review")
    if risk_score >= 0.80:
        controls.append("risk_score_above_0_80")
    if amount > 10000:
        controls.append("amount_above_10000")
    if attempt >= 4 and recommended_action.startswith("retry"):
        controls.append("retry_limit_reached")

    if controls:
        return {
            "allowed": False,
            "final_action": "human_review",
            "status": "blocked",
            "reason": "Policy blocked automated recovery and routed the payment to human review.",
            "controls": controls,
        }

    if recommended_action.startswith("retry"):
        controls.append("retry_limit_not_exceeded")
    if recommended_action in {"payment_link", "alternate_method"}:
        controls.append("customer_initiated_completion_required")

    return {
        "allowed": True,
        "final_action": recommended_action,
        "status": "allowed",
        "reason": "Policy allowed automated recovery within configured risk and value limits.",
        "controls": controls,
    }

