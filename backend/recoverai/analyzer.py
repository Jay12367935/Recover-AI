from __future__ import annotations

from typing import Any

from .constants import FAILURE_GROUPS


FAILURE_DETAILS = {
    "BANK_ERROR": {
        "category": "BANK_ERROR",
        "issue_type": "temporary_issue",
        "severity": "medium",
        "summary": "Bank response failed or bank-side downtime was likely.",
        "evidence": ["failure_code=BANK_ERROR", "bank-side failure class"],
    },
    "GATEWAY_TIMEOUT": {
        "category": "NETWORK_ERROR",
        "issue_type": "temporary_issue",
        "severity": "medium",
        "summary": "Gateway timeout suggests a transient processing delay.",
        "evidence": ["failure_code=GATEWAY_TIMEOUT", "retry later often improves outcome"],
    },
    "NETWORK_ERROR": {
        "category": "NETWORK_ERROR",
        "issue_type": "temporary_issue",
        "severity": "low",
        "summary": "Network instability interrupted the payment journey.",
        "evidence": ["failure_code=NETWORK_ERROR"],
    },
    "INSUFFICIENT_FUNDS": {
        "category": "INSUFFICIENT_FUNDS",
        "issue_type": "customer_issue",
        "severity": "medium",
        "summary": "The selected account or instrument may not have enough balance.",
        "evidence": ["failure_code=INSUFFICIENT_FUNDS"],
    },
    "USER_CANCELLED": {
        "category": "USER_CANCELLED",
        "issue_type": "low_intent",
        "severity": "low",
        "summary": "The customer abandoned or cancelled the payment.",
        "evidence": ["failure_code=USER_CANCELLED"],
    },
    "AUTHENTICATION_FAILED": {
        "category": "AUTHENTICATION_FAILED",
        "issue_type": "customer_issue",
        "severity": "medium",
        "summary": "Authentication, OTP, PIN, or 3DS confirmation failed.",
        "evidence": ["failure_code=AUTHENTICATION_FAILED"],
    },
    "PAYMENT_METHOD_ISSUE": {
        "category": "PAYMENT_METHOD_ISSUE",
        "issue_type": "payment_method_issue",
        "severity": "medium",
        "summary": "The chosen payment method appears unavailable or incompatible.",
        "evidence": ["failure_code=PAYMENT_METHOD_ISSUE"],
    },
    "CARD_DECLINED": {
        "category": "PAYMENT_METHOD_ISSUE",
        "issue_type": "payment_method_issue",
        "severity": "medium",
        "summary": "The issuing bank declined the card transaction.",
        "evidence": ["failure_code=CARD_DECLINED"],
    },
    "UPI_COLLECT_EXPIRED": {
        "category": "AUTHENTICATION_FAILED",
        "issue_type": "customer_issue",
        "severity": "low",
        "summary": "The customer did not approve the UPI collect request in time.",
        "evidence": ["failure_code=UPI_COLLECT_EXPIRED"],
    },
    "RISK_CHECK_FAILED": {
        "category": "POSSIBLE_FRAUD",
        "issue_type": "risky_issue",
        "severity": "high",
        "summary": "Risk controls detected an unusual or high-risk payment pattern.",
        "evidence": ["failure_code=RISK_CHECK_FAILED", "manual review required"],
    },
}


def analyze_failure(payment: dict[str, Any]) -> dict[str, Any]:
    code = str(payment.get("failure_code", "UNKNOWN")).upper()
    detail = FAILURE_DETAILS.get(
        code,
        {
            "category": "UNKNOWN",
            "issue_type": FAILURE_GROUPS.get(code, "unknown"),
            "severity": "medium",
            "summary": "The failure code is not mapped, so RecoverAI will rely on history and policy.",
            "evidence": [f"failure_code={code}"],
        },
    )

    evidence = list(detail["evidence"])
    amount = float(payment.get("amount", 0))
    risk_score = float(payment.get("risk_score", 0))
    attempt = int(payment.get("attempt_number", 1))

    if amount > 10000:
        evidence.append("amount_above_manual_review_threshold")
    if risk_score >= 0.8:
        evidence.append("risk_score_high")
    if attempt >= 3:
        evidence.append("multiple_failed_attempts")

    return {
        "failure_code": code,
        "category": detail["category"],
        "issue_type": detail["issue_type"],
        "severity": detail["severity"],
        "summary": detail["summary"],
        "evidence": evidence,
    }

