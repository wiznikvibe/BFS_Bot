const form = document.querySelector("#ask-form");
const questionInput = document.querySelector("#question");
const answerEl = document.querySelector("#answer");
const contextEl = document.querySelector("#redacted-context");
const citationsEl = document.querySelector("#citations");
const traceEl = document.querySelector("#trace");
const customerHintEl = document.querySelector("#customer-hint");
const submitButton = form.querySelector("button");

// ----- State -----
let isSubmitting = false;

// ----- Initialize -----

function loadDemoCustomers() {
  fetch("/api/demo-customers")
    .then((response) => response.json())
    .then((payload) => {
      const ids = payload.customer_ids?.slice(0, 5) ?? [];
      customerHintEl.textContent =
        ids.length > 0
          ? `Sample IDs: ${ids.join(", ")}`
          : "No customers loaded. Run the seed command.";
    })
    .catch(() => {
      customerHintEl.textContent =
        "Customer IDs will appear after the API is connected.";
    });
}

// ----- Skeleton loading -----

function showSkeleton() {
  answerEl.innerHTML = `
    <div class="skeleton-answer" aria-busy="true" aria-label="Generating answer">
      <div class="skeleton-row" />
      <div class="skeleton-row" />
      <div class="skeleton-row" />
    </div>
  `;
  citationsEl.innerHTML = `
    <li class="skeleton-citation" aria-hidden="true" role="listitem" style="--height: 24px; aspect-ratio: 3/1;" /></li>
    <li class="skeleton-citation" aria-hidden="true" role="listitem" style="--height: 24px; aspect-ratio: 3/1;" /></li>
    <li class="skeleton-citation" aria-hidden="true" role="listitem" style="--height: 24px; aspect-ratio: 3/1;" /></li>
  `;
  traceEl.innerHTML = `
    <li class="trace-item skeleton-trace" aria-hidden="true" role="listitem" style="--height: 16px;" /></li>
    <li class="trace-item skeleton-trace" aria-hidden="true" role="listitem" style="--height: 16px;" /></li>
    <li class="trace-item skeleton-trace" aria-hidden="true" role="listitem" style="--height: 16px;" /></li>
  `;
}

function hideSkeleton() {
  // Skeleton removed by renderResponse
}

// ----- Response rendering -----

function renderResponse(payload) {
  // Answer
  if (payload.answer) {
    answerEl.textContent = payload.answer;
  } else {
    answerEl.textContent = "No answer returned.";
  }

  // Redacted customer context
  if (payload.redacted_customer_context) {
    contextEl.textContent = JSON.stringify(
      payload.redacted_customer_context,
      null,
      2
    );
    contextEl.className = "context-block";
  } else {
    contextEl.textContent = "No customer context used.";
    contextEl.className = "context-block";
  }

  // Policy citations
  citationsEl.innerHTML = "";
  if (payload.citations && payload.citations.length > 0) {
    for (const citation of payload.citations) {
      const item = document.createElement("li");
      item.role = "listitem";

      const link = document.createElement("a");
      link.href = citation.source;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = citation.title;
      item.append(link, ` - ${citation.section} (${citation.chunk_id})`);
      citationsEl.append(item);
    }
  } else {
    const item = document.createElement("li");
    item.textContent = "No policy citations.";
    item.role = "listitem";
    citationsEl.append(item);
  }

  // Agent trace
  traceEl.innerHTML = "";
  if (payload.trace && payload.trace.length > 0) {
    for (const step of payload.trace) {
      const item = document.createElement("li");
      item.className = "trace-item";
      item.role = "listitem";

      const status = document.createElement("span");
      status.className = `trace-status ${step.status}`;
      status.setAttribute("aria-hidden", "true");
      status.textContent = step.status;

      item.append(status, `${step.agent}: ${step.detail}`);
      traceEl.append(item);
    }
  } else {
    const item = document.createElement("li");
    item.className = "trace-item";
    item.role = "listitem";
    item.textContent = "No trace yet.";
    traceEl.append(item);
  }
}

// ----- Form submission -----

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (isSubmitting) return;
  isSubmitting = true;
  submitButton.disabled = true;
  submitButton.textContent = "Running…";

  // Show skeleton while waiting
  showSkeleton();

  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: questionInput.value.trim() }),
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Request failed");
    }
    renderResponse(payload);
  } catch (error) {
    answerEl.textContent =
      error instanceof Error ? error.message : "Unable to run the query.";
    // Clear skeleton on error
    answerEl.innerHTML = "";
    citationsEl.innerHTML = `
      <li role="listitem">No policy citations.</li>`;
    traceEl.innerHTML = `
      <li class="trace-item" role="listitem">No trace yet.</li>`;
  } finally {
    isSubmitting = false;
    submitButton.disabled = false;
    submitButton.textContent = "Ask";
  }
});

// ----- Accessibility: focus management -----
// Return focus to the textarea after each submission
questionInput.focus();

// ----- Initialize -----
loadDemoCustomers();