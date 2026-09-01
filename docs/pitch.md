# RecoverAI 3-Minute Pitch

## 0:00-0:20

Every failed payment is not the same. Today, most systems retry everything or send the same generic message. That wastes attempts, annoys customers, and still leaves revenue on the table.

RecoverAI treats a failed payment like a recovery decision.

## 0:20-1:00

Use the calculator to enter a `₹4,999` UPI transaction with `BANK_ERROR`.

RecoverAI checks:

- failure reason
- bank
- method
- amount
- time of day
- attempt number
- customer success and failure history
- risk score

Then it predicts recovery probability by action:

- retry immediately
- retry after 30 minutes
- payment link
- alternate payment method
- human review
- no retry

The agent chooses the highest expected rupee value, not just the highest probability.

Click **Calculate only** to show that the model can calculate from user-entered values. Then click **Save and calculate** to store the payment in the database.

## 1:00-1:40

Show the customer message.

For example:

`Hi Rahul, UPI se ₹4,999 payment complete nahi hua. Aap UPI, card, ya netbanking se ek baar try kar sakte ho.`

Click **Execute safe action**. The dashboard updates recovered revenue and logs the gateway simulator response.

Then click **Webhook demo** to show the same recovery flow starting from a Razorpay-style `payment.failed` event.

## 1:40-2:20

Run **Batch Simulation** for 10,000 failed payments.

Now show the counterfactual:

- Traditional recovery blindly retries every failed payment.
- RecoverAI retries fewer payments and chooses payment links, alternate methods, review, or no retry when appropriate.
- The report button exports the payment-level recovery audit as CSV.
- The dashboard separates recovery rate from revenue recovery so the financial metrics are mathematically consistent.

The judge-facing line:

`RecoverAI recovered more revenue while making fewer unnecessary recovery attempts.`

## 2:20-3:00

Select the `₹18,000` high-risk payment.

The model may find possible recovery value, but policy blocks automated recovery because risk and amount thresholds are crossed.

Finish with:

`RecoverAI does not blindly retry payments. It decides when, how, and whether recovery is worth attempting, and every financial action is bounded by deterministic safety policies.`
