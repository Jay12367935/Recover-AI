const state = {
  payments: [],
  selectedPaymentId: null,
  options: null,
  report: null,
  reportFilter: "all",
};

const actionLabels = {
  retry_immediate: "Retry immediately",
  retry_30m: "Retry after 30 min",
  payment_link: "Payment link",
  alternate_method: "Alternate method",
  human_review: "Human review",
  no_retry: "Do not retry",
};

const formatMoney = (value) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number(value || 0));

const formatPercent = (value) => `${Math.round(Number(value || 0) * 100)}%`;

const wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function formatCompactMoney(value) {
  const amount = Number(value || 0);
  if (Math.abs(amount) >= 10000000) {
    return `₹${(amount / 10000000).toFixed(2)} Cr`;
  }
  if (Math.abs(amount) >= 100000) {
    return `₹${(amount / 100000).toFixed(1)} L`;
  }
  return formatMoney(amount);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

async function loadAll() {
  const [metrics, paymentsPayload, report] = await Promise.all([
    api("/api/metrics"),
    api("/api/payments?limit=80"),
    api("/api/report"),
  ]);

  state.payments = paymentsPayload.payments;
  renderMetrics(metrics);
  renderRootCauses(metrics.root_causes || []);
  renderPayments();
  state.report = report;
  renderReport(report);

  if (!state.selectedPaymentId && state.payments.length) {
    await selectPayment(state.payments[0].id);
  } else if (state.selectedPaymentId) {
    await selectPayment(state.selectedPaymentId);
  }
}

function renderRootCauses(rootCauses) {
  const list = document.querySelector("#rootCauseList");
  if (!rootCauses.length) {
    list.innerHTML = `<article class="root-cause-item"><p>No degradation clusters detected yet.</p></article>`;
    return;
  }
  list.innerHTML = rootCauses
    .map(
      (item) => {
        const lift = Number(item.lift || 0).toFixed(1);
        const degradation = item.degradation_detected ? "Payment degradation detected" : "Root cause cluster";
        return `
        <article class="root-cause-item">
          <div>
            <strong>${item.bank} / ${String(item.method).toUpperCase()}</strong>
            <span>${String(item.failure_code).replaceAll("_", " ")} · ${item.count} failures</span>
          </div>
          <strong>${formatMoney(item.amount)} at risk</strong>
          <p>${degradation}: ${item.likely_cause}. Failure concentration is ${lift}x expected. ${item.recommendation}</p>
        </article>
      `;
      },
    )
    .join("");
}

async function loadOptions() {
  state.options = await api("/api/options");
  fillSelect("method", state.options.payment_methods);
  fillSelect("bank", state.options.banks);
  fillSelect("failure_code", state.options.failure_codes);
  fillSelect("merchant_category", state.options.merchant_categories);

  document.querySelector("[name='method']").value = "upi";
  document.querySelector("[name='bank']").value = "HDFC";
  document.querySelector("[name='failure_code']").value = "BANK_ERROR";
  document.querySelector("[name='merchant_category']").value = "ecommerce";
}

function fillSelect(name, values) {
  const select = document.querySelector(`[name='${name}']`);
  select.innerHTML = values
    .map((value) => `<option value="${value}">${String(value).replaceAll("_", " ")}</option>`)
    .join("");
}

function renderMetrics(data) {
  const payments = data.payments;
  const cf = data.counterfactual;
  const model = data.model || {};

  document.querySelector("#failedAmount").textContent = formatMoney(payments.revenue_at_risk);
  document.querySelector("#failedCount").textContent = `${payments.total_count} failed-payment opportunities`;
  document.querySelector("#atRiskAmount").textContent = formatMoney(payments.eligible_amount);
  document.querySelector("#recoverableCount").textContent = `${payments.eligible_count} eligible payments · ${formatMoney(payments.expected_recovery_opportunity)} expected`;
  document.querySelector("#recoveredAmount").textContent = formatMoney(payments.realized_recovery_amount);
  document.querySelector("#recoveredCount").textContent = `${payments.recovered_count} payments saved`;
  document.querySelector("#recoveryRate").textContent = formatPercent(payments.recovery_rate);
  document.querySelector("#reviewQueue").textContent = `${payments.recovered_count} / ${payments.eligible_count} eligible payments recovered · ${formatPercent(payments.revenue_recovery_rate)} revenue recovery`;
  document.querySelector("#webhookEvents").textContent = Number(payments.webhook_events || 0).toLocaleString("en-IN");

  document.querySelector("#modelAuc").textContent = Number(model.roc_auc || 0).toFixed(2);
  document.querySelector("#modelPrecision").textContent = Number(model.precision || 0).toFixed(2);
  document.querySelector("#modelRecall").textContent = Number(model.recall || 0).toFixed(2);
  document.querySelector("#modelF1").textContent = Number(model.f1_score || 0).toFixed(2);
  document.querySelector("#modelRows").textContent = `${Number(model.validation_rows || 0).toLocaleString("en-IN")} held-out test rows`;

  document.querySelector("#incrementalRevenue").textContent = `${formatMoney(cf.incremental_revenue)} more`;
  document.querySelector("#tradHeroRecovered").textContent = formatMoney(cf.traditional.recovered_amount);
  document.querySelector("#aiHeroRecovered").textContent = formatMoney(cf.recoverai.recovered_amount);
  document.querySelector("#incrementalHero").textContent = formatMoney(cf.incremental_revenue);
  document.querySelector("#wasteHero").textContent = `${formatPercent(cf.unnecessary_attempt_reduction)} fewer`;
  document.querySelector("#tradFailed").textContent = cf.traditional.failed_payments.toLocaleString("en-IN");
  document.querySelector("#aiFailed").textContent = cf.recoverai.failed_payments.toLocaleString("en-IN");
  document.querySelector("#tradRetries").textContent = cf.traditional.retries.toLocaleString("en-IN");
  document.querySelector("#aiRetries").textContent = cf.recoverai.retries.toLocaleString("en-IN");
  document.querySelector("#tradRecovered").textContent = formatMoney(cf.traditional.recovered_amount);
  document.querySelector("#aiRecovered").textContent = formatMoney(cf.recoverai.recovered_amount);
  document.querySelector("#tradRate").textContent = formatPercent(cf.traditional.recovery_rate);
  document.querySelector("#aiRate").textContent = formatPercent(cf.recoverai.recovery_rate);
  document.querySelector("#tradWaste").textContent = cf.traditional.unnecessary_attempts.toLocaleString("en-IN");
  document.querySelector("#aiWaste").textContent = cf.recoverai.unnecessary_attempts.toLocaleString("en-IN");

  const uplift = cf.incremental_revenue;
  const attemptReduction = formatPercent(cf.unnecessary_attempt_reduction);
  const insight =
    uplift >= 0
      ? `RecoverAI has recovered ${formatMoney(uplift)} more than blind retry while reducing unnecessary attempts by ${attemptReduction}.`
      : `Run the AI batch to process the remaining queue and unlock the counterfactual recovery advantage.`;
  document.querySelector("#merchantInsight").textContent = insight;
}

function renderPayments() {
  const list = document.querySelector("#paymentList");
  document.querySelector("#queueCount").textContent = `${state.payments.length} items`;

  list.innerHTML = state.payments
    .map((payment) => {
      const decision = payment.latest_decision;
      const action = decision ? actionLabels[decision.final_action] : "Awaiting AI";
      return `
        <button class="payment-item ${payment.id === state.selectedPaymentId ? "active" : ""}" data-id="${payment.id}" type="button">
          <span class="payment-amount">${formatMoney(payment.amount)}</span>
          <span class="payment-meta">
            <strong>${payment.failure_code.replaceAll("_", " ")} · ${payment.method.toUpperCase()} · ${payment.bank}</strong>
            <span>${payment.customer_name} · ${action}</span>
          </span>
          <span class="payment-state">${payment.status.replaceAll("_", " ")}</span>
        </button>
      `;
    })
    .join("");

  list.querySelectorAll(".payment-item").forEach((button) => {
    button.addEventListener("click", () => selectPayment(button.dataset.id));
  });
}

function renderReport(report) {
  const body = document.querySelector("#reportBody");
  state.report = report;
  const rows = report.payments
    .filter((payment) => {
      if (state.reportFilter === "all") return true;
      if (state.reportFilter === "blocked") return payment.policy_status === "blocked";
      if (state.reportFilter === "failed") return payment.status === "failed";
      return payment.status === state.reportFilter || payment.result === state.reportFilter;
    })
    .slice(0, 80);
  body.innerHTML = rows
    .map((payment) => {
      const action = payment.final_action ? actionLabels[payment.final_action] || payment.final_action : "Not calculated";
      const recovered = payment.amount_recovered ? formatMoney(payment.amount_recovered) : "₹0";
      return `
        <tr data-id="${payment.id}" class="${payment.id === state.selectedPaymentId ? "selected" : ""}">
          <td>
            <strong>${formatMoney(payment.amount)}</strong>
            <span>${payment.id}</span>
          </td>
          <td>
            <strong>${payment.customer_name || "--"}</strong>
            <span>${payment.order_id || "--"}</span>
          </td>
          <td>
            <strong>${String(payment.failure_code || "--").replaceAll("_", " ")}</strong>
            <span>${String(payment.method || "").toUpperCase()} · ${payment.bank || "--"}</span>
          </td>
          <td>
            <strong>${action}</strong>
            <span>${payment.confidence ? `${Math.round(payment.confidence * 100)}% confidence` : "Awaiting decision"}</span>
          </td>
          <td>
            <strong>${String(payment.status || "--").replaceAll("_", " ")}</strong>
            <span>${payment.policy_status || payment.result || "--"}</span>
          </td>
          <td>
            <strong>${recovered}</strong>
            <span>${payment.executed_at || "Not executed"}</span>
          </td>
        </tr>
      `;
    })
    .join("");
  body.querySelectorAll("tr[data-id]").forEach((row) => {
    row.addEventListener("click", async () => {
      await selectPayment(row.dataset.id);
      document.querySelector("#decision").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

async function selectPayment(paymentId) {
  state.selectedPaymentId = paymentId;
  const payment = await api(`/api/payments/${paymentId}`);
  renderPayments();
  if (state.report) {
    renderReport(state.report);
  }
  renderDecision(payment);
}

function renderDecision(payment) {
  const decision = payment.fresh_decision || payment.latest_decision;
  if (!decision) return;

  const finalAction = decision.final_action;
  const badge = document.querySelector("#policyBadge");
  const isSimulation = String(payment.id || "").startsWith("PAY_SIM") || String(payment.id || "").startsWith("PAY_PREVIEW");
  const sourceLabel = isSimulation ? "Simulation payment" : "Live/demo queue payment";
  const previousSuccess = Number(payment.customer_previous_success || 0).toLocaleString("en-IN");
  const previousFailures = Number(payment.customer_previous_failures || 0).toLocaleString("en-IN");

  document.querySelector("#selectedTitle").textContent = `${formatMoney(payment.amount)} · ${payment.failure_code.replaceAll("_", " ")}`;
  document.querySelector("#selectedMeta").textContent =
    `${sourceLabel} · ${payment.id} · Customer history: ${previousSuccess} successful · ${previousFailures} failed`;
  document.querySelector("#recommendedAction").textContent = actionLabels[finalAction] || finalAction;
  document.querySelector("#expectedRecovery").textContent = formatMoney(decision.expected_recovery);
  document.querySelector("#decisionReason").textContent = decision.reason;
  document.querySelector("#customerMessage").textContent = decision.customer_message?.hinglish || "--";
  document.querySelector("#executeBtn").disabled =
    payment.status === "preview" || payment.status === "recovered" || payment.status === "pending_review";

  badge.textContent = decision.policy.status;
  badge.className = `pill ${decision.policy.status}`;

  const bars = Object.entries(decision.probabilities)
    .sort((a, b) => b[1] - a[1])
    .map(([action, probability]) => {
      const width = Math.round(probability * 100);
      const expectedValue = decision.expected_values?.[action] || 0;
      return `
        <div class="bar-row">
          <strong>${actionLabels[action] || action}</strong>
          <span class="bar-track"><span class="bar-fill" style="width:${width}%"></span></span>
          <span>${width}%</span>
          <span>${formatMoney(expectedValue)} EV</span>
        </div>
      `;
    })
    .join("");

  document.querySelector("#probabilityBars").innerHTML = bars;
  renderPipeline(payment, decision);
  renderPolicyGate(decision);
  renderWhyNot(decision);
  renderTimeline(payment, decision);
  renderAudit(payment, decision);
}

function renderPipeline(payment, decision) {
  const analysis = decision.analysis || {};
  const steps = [
    ["#pipelineDetect", `Payment failed · ${formatMoney(payment.amount)}`],
    ["#pipelineDiagnose", `Root cause: ${String(analysis.category || "--").replaceAll("_", " ")}`],
    ["#pipelineScore", `Recovery scored · ${formatPercent(decision.confidence)}`],
    ["#pipelinePolicy", `Policy: ${decision.policy.status}`],
    ["#pipelineExecute", `Action: ${actionLabels[decision.final_action] || decision.final_action}`],
  ];
  steps.forEach(([selector, text]) => {
    const node = document.querySelector(selector);
    node.textContent = text;
    node.className = "done";
  });
}

function renderPolicyGate(decision) {
  const gate = document.querySelector(".policy-gate");
  const title = document.querySelector("#policyGateTitle");
  const detail = document.querySelector("#policyGateDetail");
  gate.className = `policy-gate ${decision.policy.status === "blocked" ? "blocked" : "allowed"}`;
  title.textContent =
    decision.policy.status === "blocked"
      ? "Auto execution blocked"
      : decision.policy.status === "review"
        ? "Human review required"
        : "Auto action allowed";
  detail.textContent = `${decision.policy.reason} Controls: ${(decision.policy.controls || []).join(", ") || "standard recovery policy"}.`;
}

function renderWhyNot(decision) {
  const entries = Object.entries(decision.probabilities)
    .filter(([action]) => action !== decision.final_action)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([action, probability]) => `${actionLabels[action]}: ${formatPercent(probability)}`);
  document.querySelector("#whyNotText").textContent =
    `${actionLabels[decision.final_action]} was selected after comparing alternatives. Why not others? ${entries.join(" · ")}.`;
}

function formatDateTime(timestamp) {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? timestamp || "--" : date.toLocaleString("en-IN");
}

function formatTime(timestamp) {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? timestamp || "--" : date.toLocaleTimeString("en-IN");
}

function decisionPreviewEvents(payment, decision) {
  const events = Array.isArray(payment.audit_trail) ? [...payment.audit_trail] : [];
  const hasStoredDecision = events.some((item) => String(item.event || "").includes("Agent decision"));
  if (!hasStoredDecision && decision) {
    const timestamp = new Date().toISOString();
    events.push({
      timestamp,
      payment_id: payment.id,
      event: `Current decision preview: ${actionLabels[decision.final_action] || decision.final_action}`,
      reason: decision.reason,
      model_confidence: decision.confidence,
      policy_result: decision.policy.status,
      execution_result: payment.status === "preview" ? "not saved" : "not executed",
    });
    events.push({
      timestamp,
      payment_id: payment.id,
      event: `Policy evaluated: ${decision.policy.status}`,
      reason: decision.policy.reason,
      model_confidence: decision.confidence,
      policy_result: decision.policy.status,
      execution_result: decision.policy.status === "allowed" ? "ready to execute" : "requires human review",
    });
  }
  return events;
}

function renderTimeline(payment, decision) {
  const events = decisionPreviewEvents(payment, decision);
  if (events.length) {
    document.querySelector("#timelineList").innerHTML = events
      .map((item) => `<li>${formatTime(item.timestamp)} · ${item.event}</li>`)
      .join("");
    return;
  }
  const items = [
    "Payment failure received",
    `Failure classified as ${String(decision.analysis.category || "--").replaceAll("_", " ")}`,
    "Recovery probabilities generated",
    `${actionLabels[decision.recommended_action]} recommended`,
    `Policy check ${decision.policy.status}`,
    payment.status === "recovered" ? `${formatMoney(payment.amount)} recovered` : `${actionLabels[decision.final_action]} pending/executed`,
  ];
  document.querySelector("#timelineList").innerHTML = items.map((item) => `<li>${item}</li>`).join("");
}

function renderAudit(payment, decision) {
  const events = decisionPreviewEvents(payment, decision);
  if (events.length) {
    document.querySelector("#auditTrail").innerHTML = events
      .map(
        (item) => `
          <div>
            <strong>${formatDateTime(item.timestamp)} · ${item.event}</strong>
            <span>${item.payment_id} · ${item.reason}</span>
            <span>Confidence: ${item.model_confidence === null || item.model_confidence === undefined ? "--" : formatPercent(item.model_confidence)} · Policy: ${item.policy_result || "--"} · Result: ${item.execution_result || "--"}</span>
          </div>
        `,
      )
      .join("");
    return;
  }
  const audit = [
    ["Payment received", `${payment.id} · ${formatMoney(payment.amount)}`],
    ["Failure classified", `${decision.analysis.failure_code} · ${decision.analysis.summary}`],
    ["Model prediction generated", `${actionLabels[decision.final_action]} · ${formatPercent(decision.confidence)} confidence`],
    ["Policy evaluated", `${decision.policy.status} · ${decision.policy.reason}`],
  ];
  document.querySelector("#auditTrail").innerHTML = audit
    .map(([title, detail]) => `<div><strong>${title}</strong><span>${detail}</span></div>`)
    .join("");
}

async function executeSelected() {
  if (!state.selectedPaymentId) return;
  const button = document.querySelector("#executeBtn");
  button.disabled = true;
  button.textContent = "Executing...";
  try {
    await api(`/api/payments/${state.selectedPaymentId}/execute`, { method: "POST", body: "{}" });
    await loadAll();
  } finally {
    button.textContent = "Execute safe action";
    button.disabled = false;
  }
}

function formPayload() {
  const form = document.querySelector("#manualPaymentForm");
  const formData = new FormData(form);
  const payload = {};
  for (const [key, value] of formData.entries()) {
    if (value !== "") {
      payload[key] = value;
    }
  }
  return payload;
}

async function previewManualPayment() {
  const badge = document.querySelector("#formStatus");
  badge.textContent = "Calculating";
  badge.className = "pill neutral";
  try {
    const result = await api("/api/predict-recovery", {
      method: "POST",
      body: JSON.stringify(formPayload()),
    });
    state.selectedPaymentId = result.payment.id;
    renderDecision({ ...result.payment, fresh_decision: result.decision, status: "preview" });
    badge.textContent = "Calculated";
    badge.className = "pill allowed";
  } catch (error) {
    badge.textContent = error.message;
    badge.className = "pill blocked";
  }
}

async function saveManualPayment(event) {
  event.preventDefault();
  const badge = document.querySelector("#formStatus");
  badge.textContent = "Saving";
  badge.className = "pill neutral";
  try {
    const result = await api("/api/payments/manual", {
      method: "POST",
      body: JSON.stringify(formPayload()),
    });
    state.selectedPaymentId = result.payment.id;
    badge.textContent = "Saved";
    badge.className = "pill allowed";
    await loadAll();
  } catch (error) {
    badge.textContent = error.message;
    badge.className = "pill blocked";
  }
}

async function runBatch() {
  const button = document.querySelector("#batchBtn");
  button.disabled = true;
  button.textContent = "Running...";
  try {
    await api("/api/batch-run", { method: "POST", body: JSON.stringify({ limit: 40 }) });
    await loadAll();
  } finally {
    button.textContent = "Run AI batch";
    button.disabled = false;
  }
}

async function runBatchSimulation() {
  const button = document.querySelector("#runBatchSimulationBtn");
  const results = document.querySelector("#batchResults");
  const stepNodes = Array.from(document.querySelectorAll("#batchSteps span"));
  const stageLabels = ["Analyzing", "Classifying", "Scoring", "Applying policies", "Recovery actions"];
  button.disabled = true;
  button.textContent = "Simulating...";
  results.classList.remove("visible");
  results.innerHTML = "";
  stepNodes.forEach((step, idx) => {
    step.innerHTML = `<strong>${stageLabels[idx]}</strong><em>waiting</em>`;
    step.className = "";
  });
  try {
    const request = api("/api/batch-simulation", {
      method: "POST",
      body: JSON.stringify({ count: 10000 }),
    });
    for (const [idx, step] of stepNodes.entries()) {
      step.innerHTML = `<strong>${stageLabels[idx]}</strong><em>running</em>`;
      step.className = "running";
      await wait(180);
    }
    const result = await request;
    const pipeline = result.pipeline;
    const total = result.dataset_size.toLocaleString("en-IN");
    const steps = [
      ["Analyzing", pipeline.analyzed],
      ["Classifying", pipeline.classified],
      ["Scoring", pipeline.scored],
      ["Applying policies", pipeline.policy_checked],
      ["Recovery actions", pipeline.recovery_actions],
    ];
    stepNodes.forEach((step, idx) => {
      const [label, count] = steps[idx];
      step.innerHTML = `<strong>${label}</strong><em>✓ ${count.toLocaleString("en-IN")} / ${total}</em>`;
      step.className = "done";
    });
    renderBatchResults(result);
  } catch (error) {
    results.innerHTML = `<div class="batch-error"><span>Simulation failed</span><strong>${error.message}</strong></div>`;
    results.classList.add("visible");
  } finally {
    button.disabled = false;
    button.textContent = "Run simulation";
  }
}

function renderBatchResults(result) {
  const data = result.results;
  const failedCount = Number(result.dataset_size || 0).toLocaleString("en-IN");
  document.querySelector("#batchResults").innerHTML = `
    <h3>Batch results</h3>
    <div><span>Failed payments</span><strong>${failedCount}</strong></div>
    <div><span>Revenue at risk</span><strong>${formatCompactMoney(data.revenue_at_risk)}</strong></div>
    <div><span>Eligible recovery</span><strong>${formatCompactMoney(data.recoverable_amount)}</strong></div>
    <div><span>Expected recovery</span><strong>${formatCompactMoney(data.expected_recovery_opportunity)}</strong></div>
    <div><span>Realized recovery</span><strong>${formatCompactMoney(data.recovered_amount)}</strong></div>
    <div><span>Incremental vs blind retry</span><strong>+${formatCompactMoney(data.incremental_revenue)}</strong></div>
    <div><span>Unnecessary attempts</span><strong>${formatPercent(data.unnecessary_attempt_reduction)} fewer</strong></div>
    <div><span>Human escalations</span><strong>${data.human_escalations.toLocaleString("en-IN")}</strong></div>
    <div><span>Actions blocked</span><strong>${data.blocked_actions.toLocaleString("en-IN")}</strong></div>
  `;
  document.querySelector("#batchResults").classList.add("visible");
}

async function resetDemo() {
  const button = document.querySelector("#resetBtn");
  button.disabled = true;
  button.textContent = "Resetting...";
  try {
    await api("/api/demo/reset", { method: "POST", body: "{}" });
    state.selectedPaymentId = null;
    await loadAll();
  } finally {
    button.textContent = "Reset";
    button.disabled = false;
  }
}

async function downloadReport() {
  window.open("/api/report?format=csv", "_blank", "noopener");
}

async function refreshReport() {
  renderReport(await api("/api/report"));
}

function setReportFilter(filter) {
  state.reportFilter = filter;
  document.querySelectorAll(".filter-chip").forEach((button) => {
    button.classList.toggle("active", button.dataset.filter === filter);
  });
  if (state.report) {
    renderReport(state.report);
  }
}

async function webhookDemo() {
  const button = document.querySelector("#webhookBtn");
  button.disabled = true;
  button.textContent = "Simulating...";
  const payload = {
    event: "payment.failed",
    payload: {
      payment: {
        entity: {
          id: `pay_webhook_${Date.now()}`,
          order_id: `order_webhook_${Date.now()}`,
          amount: 499900,
          currency: "INR",
          method: "upi",
          bank: "HDFC",
          email: "demo.customer@example.com",
          contact: "+919999999999",
          error_code: "BANK_ERROR",
          created_at: Math.floor(Date.now() / 1000),
          notes: {
            customer_name: "Webhook Demo",
            customer_previous_success: 7,
            customer_previous_failures: 1,
            customer_age_days: 260,
            previous_recovery_success: 0.68,
            merchant_category: "ecommerce",
            risk_score: 0.12,
          },
        },
      },
    },
  };

  try {
    const result = await api("/api/webhooks/razorpay", {
      method: "POST",
      body: JSON.stringify(payload),
      headers: {
        "Content-Type": "application/json",
        "x-razorpay-event-id": `evt_demo_${Date.now()}`,
      },
    });
    state.selectedPaymentId = result.payment?.id || state.selectedPaymentId;
    await loadAll();
  } finally {
    button.textContent = "Simulate Payment Failure";
    button.disabled = false;
  }
}

async function simulateFailure() {
  const button = document.querySelector("#simulateBtn");
  button.disabled = true;
  button.textContent = "Creating...";
  try {
    const payment = await api("/api/payments/simulate-failure", { method: "POST", body: "{}" });
    state.selectedPaymentId = payment.id;
    await loadAll();
  } finally {
    button.textContent = "Create Test Failure";
    button.disabled = false;
  }
}

document.querySelector("#executeBtn").addEventListener("click", executeSelected);
document.querySelector("#manualPaymentForm").addEventListener("submit", saveManualPayment);
document.querySelector("#previewBtn").addEventListener("click", previewManualPayment);
document.querySelector("#batchBtn").addEventListener("click", runBatch);
document.querySelector("#runBatchSimulationBtn").addEventListener("click", runBatchSimulation);
document.querySelector("#simulateBtn").addEventListener("click", simulateFailure);
document.querySelector("#resetBtn").addEventListener("click", resetDemo);
document.querySelector("#reportBtn").addEventListener("click", downloadReport);
document.querySelector("#downloadCsvBtn").addEventListener("click", downloadReport);
document.querySelector("#refreshReportBtn").addEventListener("click", refreshReport);
document.querySelector("#webhookBtn").addEventListener("click", webhookDemo);
document.querySelectorAll(".filter-chip").forEach((button) => {
  button.addEventListener("click", () => setReportFilter(button.dataset.filter));
});

Promise.all([loadOptions(), loadAll()]).catch((error) => {
  document.querySelector("#paymentList").innerHTML = `<div class="reason-box"><p>${error.message}</p></div>`;
});
