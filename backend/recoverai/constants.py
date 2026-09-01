from __future__ import annotations

ACTIONS = {
    "retry_immediate": {
        "label": "Retry immediately",
        "cost": 8,
        "automation": True,
        "description": "Useful for transient gateway hiccups and low-risk payments.",
    },
    "retry_30m": {
        "label": "Retry after 30 min",
        "cost": 5,
        "automation": True,
        "description": "Best for bank downtime, rate limits, and network timeouts.",
    },
    "payment_link": {
        "label": "Send payment link",
        "cost": 12,
        "automation": True,
        "description": "Gives the customer a clean checkout path after a failed attempt.",
    },
    "alternate_method": {
        "label": "Suggest alternate method",
        "cost": 10,
        "automation": True,
        "description": "Moves the customer to UPI, card, netbanking, or wallet based on failure.",
    },
    "human_review": {
        "label": "Human review",
        "cost": 35,
        "automation": False,
        "description": "Escalates high-risk or high-value failures before any action.",
    },
    "no_retry": {
        "label": "Do not retry",
        "cost": 0,
        "automation": True,
        "description": "Avoids wasting attempts when customer intent or recovery odds are low.",
    },
}

ACTION_ORDER = list(ACTIONS.keys())

PAYMENT_METHODS = ["upi", "card", "netbanking", "wallet", "emi"]

BANKS = [
    "HDFC",
    "ICICI",
    "SBI",
    "AXIS",
    "KOTAK",
    "YESBANK",
    "IDFC",
    "BOB",
]

FAILURE_CODES = [
    "BANK_ERROR",
    "GATEWAY_TIMEOUT",
    "NETWORK_ERROR",
    "INSUFFICIENT_FUNDS",
    "USER_CANCELLED",
    "AUTHENTICATION_FAILED",
    "PAYMENT_METHOD_ISSUE",
    "RISK_CHECK_FAILED",
    "CARD_DECLINED",
    "UPI_COLLECT_EXPIRED",
    "UNKNOWN",
]

MERCHANT_CATEGORIES = [
    "edtech",
    "ecommerce",
    "travel",
    "saas",
    "food",
    "gaming",
    "healthcare",
    "marketplace",
]

FAILURE_GROUPS = {
    "BANK_ERROR": "temporary_issue",
    "GATEWAY_TIMEOUT": "temporary_issue",
    "NETWORK_ERROR": "temporary_issue",
    "INSUFFICIENT_FUNDS": "customer_issue",
    "USER_CANCELLED": "low_intent",
    "AUTHENTICATION_FAILED": "customer_issue",
    "PAYMENT_METHOD_ISSUE": "payment_method_issue",
    "CARD_DECLINED": "payment_method_issue",
    "UPI_COLLECT_EXPIRED": "customer_issue",
    "RISK_CHECK_FAILED": "risky_issue",
    "UNKNOWN": "unknown",
}

