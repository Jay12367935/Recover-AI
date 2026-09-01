from __future__ import annotations

from typing import Any

from .analyzer import analyze_failure
from .constants import ACTIONS, ACTION_ORDER
from .policy import evaluate_policy


def format_rupees(amount: float) -> str:
    value = int(round(amount))
    text = str(value)
    if len(text) <= 3:
        return f"₹{text}"
    last = text[-3:]
    rest = text[:-3]
    groups = []
    while rest:
        groups.append(rest[-2:])
        rest = rest[:-2]
    return f"₹{','.join(reversed(groups))},{last}"


class RecoveryAgent:
    def __init__(self, model: Any):
        self.model = model

    def decide(self, payment: dict[str, Any]) -> dict[str, Any]:
        analysis = analyze_failure(payment)
        probabilities = self.model.predict_actions(payment)
        amount = float(payment.get("amount", 0))

        expected_values: dict[str, float] = {}
        for action in ACTION_ORDER:
            cost = float(ACTIONS[action]["cost"])
            probability = probabilities[action]
            expected_values[action] = round((amount * probability) - cost, 2)

        if analysis["issue_type"] == "risky_issue":
            recommended = "human_review"
        else:
            candidate_actions = [action for action in ACTION_ORDER if action != "human_review"]
            recommended = max(candidate_actions, key=lambda action: expected_values[action])
            max_probability = probabilities[recommended]

            if max_probability < 0.18 and analysis["issue_type"] in {"low_intent", "unknown"}:
                recommended = "no_retry"

        policy = evaluate_policy(payment, recommended)
        final_action = policy["final_action"]

        confidence = probabilities.get(final_action, probabilities.get(recommended, 0.0))
        expected_recovery = round(amount * probabilities.get(final_action, 0.0), 2)

        return {
            "payment_id": payment.get("id"),
            "analysis": analysis,
            "probabilities": probabilities,
            "expected_values": expected_values,
            "recommended_action": recommended,
            "final_action": final_action,
            "policy": policy,
            "confidence": round(confidence, 4),
            "expected_recovery": expected_recovery,
            "reason": self._reason(payment, analysis, recommended, final_action, probabilities, expected_recovery, policy),
            "customer_message": self._message(payment, final_action, analysis),
        }

    def _reason(
        self,
        payment: dict[str, Any],
        analysis: dict[str, Any],
        recommended: str,
        final_action: str,
        probabilities: dict[str, float],
        expected_recovery: float,
        policy: dict[str, Any],
    ) -> str:
        amount_text = format_rupees(float(payment.get("amount", 0)))
        action_label = ACTIONS[final_action]["label"]
        rec_label = ACTIONS[recommended]["label"]
        probability = probabilities.get(final_action, 0.0)
        customer_success = int(payment.get("customer_previous_success", 0))
        customer_failures = int(payment.get("customer_previous_failures", 0))

        if final_action != recommended:
            return (
                f"Model recommended {rec_label}, but policy routed this {amount_text} payment to "
                f"{action_label.lower()} because {', '.join(policy['controls'])}. "
                f"Customer history is {customer_success} successful and {customer_failures} failed payments."
            )

        if final_action == "human_review":
            return (
                f"Human review is required for this {amount_text} payment because {analysis['summary'].lower()} "
                f"Controls applied: {', '.join(policy['controls'])}. "
                f"Customer history is {customer_success} successful and {customer_failures} failed payments."
            )

        return (
            f"{action_label} has a {probability:.0%} recovery probability for a {analysis['category']} failure. "
            f"Expected recovery is {format_rupees(expected_recovery)} from a {amount_text} payment. "
            f"Customer history is {customer_success} successful and {customer_failures} failed payments."
        )

    def _message(self, payment: dict[str, Any], final_action: str, analysis: dict[str, Any]) -> dict[str, str]:
        amount_text = format_rupees(float(payment.get("amount", 0)))
        name = str(payment.get("customer_name", "there")).split(" ")[0]
        method = str(payment.get("method", "payment method")).upper()

        if final_action == "payment_link":
            english = (
                f"Hi {name}, your payment of {amount_text} could not be completed because {analysis['summary'].lower()} "
                "You can use this secure recovery link to complete your order."
            )
            hinglish = (
                f"Hi {name}, aapka {amount_text} payment complete nahi ho paaya kyunki {analysis['summary'].lower()} "
                "Aap is secure recovery link se order complete kar sakte ho."
            )
        elif final_action == "alternate_method":
            english = (
                f"Hi {name}, your {amount_text} payment on {method} could not be completed because {analysis['summary'].lower()} "
                "Would you like to finish using another payment method?"
            )
            hinglish = (
                f"Hi {name}, {method} se {amount_text} payment complete nahi hua. "
                "Aap UPI, card, ya netbanking se safely complete kar sakte ho."
            )
        elif final_action == "retry_30m":
            english = (
                f"Hi {name}, your payment of {amount_text} could not be completed due to a temporary issue. "
                "We will retry safely in a few minutes."
            )
            hinglish = (
                f"Hi {name}, {amount_text} payment temporary issue ki wajah se fail hua. "
                "Hum thodi der mein safe retry karenge."
            )
        elif final_action == "retry_immediate":
            english = (
                f"Hi {name}, your payment of {amount_text} did not complete. "
                "We are retrying once because this looks temporary."
            )
            hinglish = (
                f"Hi {name}, {amount_text} payment complete nahi hua. "
                "Ye temporary lag raha hai, hum ek safe retry kar rahe hain."
            )
        elif final_action == "human_review":
            english = (
                f"Hi {name}, your {amount_text} payment could not be completed because {analysis['summary'].lower()} "
                "Since this transaction needs quick verification, we have paused automatic retry and our team will review it shortly."
            )
            hinglish = (
                f"Hi {name}, {amount_text} payment complete nahi hua kyunki {analysis['summary'].lower()} "
                "Is transaction ke liye quick verification chahiye, isliye automatic retry pause kar diya gaya hai."
            )
        else:
            english = (
                f"Hi {name}, your payment of {amount_text} could not be completed. "
                "We will not retry automatically to avoid unnecessary payment attempts."
            )
            hinglish = (
                f"Hi {name}, {amount_text} payment complete nahi hua. "
                "Unnecessary attempts avoid karne ke liye hum automatic retry nahi karenge."
            )

        return {"english": english, "hinglish": hinglish}
