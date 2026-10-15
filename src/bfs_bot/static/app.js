const form = document.querySelector("#ask-form");
const loginForm = document.querySelector("#login-form");
const questionInput = document.querySelector("#question");
const answerEl = document.querySelector("#answer");
const contextEl = document.querySelector("#redacted-context");
const dataCitationsEl = document.querySelector("#data-citations");
const policyCitationsEl = document.querySelector("#policy-citations");
const traceEl = document.querySelector("#trace");
const personaHintEl = document.querySelector("#persona-hint");
const personaChipsEl = document.querySelector("#persona-chips");
const authHintEl = document.querySelector("#auth-hint");
const sessionBadgeEl = document.querySelector("#session-badge");
const answerGridEl = document.querySelector(".answer-grid");
const submitButton = document.querySelector("#ask-button");
const loginButton = document.querySelector("#login-button");
const logoutButton = document.querySelector("#logout-button");
const usernameInput = document.querySelector("#username");
const passwordInput = document.querySelector("#password");
const escalateBannerEl = document.querySelector("#escalate-banner");
const escalateDetailEl = document.querySelector("#escalate-detail");
const routeMetaEl = document.querySelector("#route-meta");
const routeBadgeEl = document.querySelector("#route-badge");
const confidenceBadgeEl = document.querySelector("#confidence-badge");
const resolvedMetaEl = document.querySelector("#resolved-meta");

const DEMO_PERSONA_IDS = new Set(["C001", "C002", "C003", "C004", "C005", "C006", "C007"]);

const DEMO_QUESTIONS = {
  C001: "Why no 10% loyalty discount?",
  C002: "Why was my invoice 10% lower?",
  C003: "Why no loyalty discount?",
  C004: "Why did I get a discount in November 2025?",
  C005: "Why not both annual and loyalty discounts?",
  C006: "Was my late fee correct?",
  C007: "Can I still get a refund?",
};

let isSubmitting = false;
let selectedCustomerId = null;
let sessionCustomerId = null;

function setSessionBadge(customerId, username) {
  if (customerId && username) {
    sessionBadgeEl.textContent = `${username} · ${customerId}`;
    sessionBadgeEl.classList.add("is-active");
  } else if (customerId) {
    sessionBadgeEl.textContent = customerId;
    sessionBadgeEl.classList.add("is-active");
  } else {
    sessionBadgeEl.textContent = "Not signed in";
    sessionBadgeEl.classList.remove("is-active");
  }
}

function updateAuthUi() {
  const signedIn = Boolean(sessionCustomerId);
  logoutButton.hidden = !signedIn;
  loginButton.hidden = signedIn;
  usernameInput.disabled = signedIn;
  passwordInput.disabled = signedIn;
  setSessionBadge(sessionCustomerId, signedIn ? usernameInput.value.trim() || null : null);
}

function selectPersona(customerId, { updateQuestion = true } = {}) {
  selectedCustomerId = customerId;
  for (const chip of personaChipsEl.querySelectorAll(".persona-chip")) {
    chip.classList.toggle("is-selected", chip.dataset.customerId === customerId);
  }
  if (customerId) {
    personaHintEl.textContent = `Demo persona ${customerId}. Sign in as the matching user to ask questions.`;
    if (updateQuestion && DEMO_QUESTIONS[customerId]) {
      questionInput.value = DEMO_QUESTIONS[customerId];
    }
  } else {
    personaHintEl.textContent = "Pick a persona chip, then sign in with the matching demo username.";
  }
  setSessionBadge(sessionCustomerId, sessionCustomerId ? usernameInput.value.trim() || null : null);
}

function renderPersonas(personas) {
  personaChipsEl.innerHTML = "";
  const demoPersonas = personas
    .filter((persona) => DEMO_PERSONA_IDS.has(persona.customer_id))
    .sort((a, b) => a.customer_id.localeCompare(b.customer_id));

  if (!demoPersonas.length) {
    personaHintEl.textContent = "Run bfs-bot-seed to load C001–C007 customers.";
    return;
  }

  for (const persona of demoPersonas) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "persona-chip";
    button.dataset.customerId = persona.customer_id;
    button.setAttribute("role", "listitem");

    const id = document.createElement("span");
    id.className = "chip-id";
    id.textContent = `${persona.customer_id}${persona.name ? ` · ${persona.name}` : ""}`;

    const meta = document.createElement("span");
    meta.className = "chip-meta";
    const plan = persona.plan || "—";
    const status = persona.status || "—";
    meta.textContent = `${plan} plan · ${status}`;

    button.append(id, meta);
    button.addEventListener("click", () => selectPersona(persona.customer_id));
    personaChipsEl.append(button);
  }

  const active = sessionCustomerId || selectedCustomerId || demoPersonas[0].customer_id;
  selectPersona(active, { updateQuestion: !sessionCustomerId });
}

async function loadDemoCustomers() {
  try {
    const response = await fetch("/api/demo-customers");
    const payload = await response.json();
    const personas = payload.personas ?? [];
    renderPersonas(personas);
  } catch {
    personaHintEl.textContent = "Persona chips appear once the API and database are running.";
  }
}

async function loadSession() {
  try {
    const response = await fetch("/api/session");
    const payload = await response.json();
    sessionCustomerId = payload.customer_id || null;
    if (payload.username) {
      usernameInput.value = payload.username;
    }
    if (payload.demo_accounts?.length) {
      authHintEl.textContent =
        "Password for all accounts: demo123. " +
        payload.demo_accounts.map((account) => `${account.username}→${account.customer_id}`).join(" · ");
    }
    if (sessionCustomerId) {
      selectedCustomerId = sessionCustomerId;
    }
    updateAuthUi();
  } catch {
    authHintEl.textContent = "Demo login is available when the API is running.";
  }
}

function showSkeleton() {
  answerEl.innerHTML = `
    <div class="skeleton-answer" aria-busy="true" aria-label="Generating answer">
      <div class="skeleton-row"></div>
      <div class="skeleton-row"></div>
      <div class="skeleton-row"></div>
    </div>
  `;
  routeMetaEl.hidden = true;
  escalateBannerEl.hidden = true;
  dataCitationsEl.innerHTML = `<li class="skeleton-citation" aria-hidden="true"></li>`;
  policyCitationsEl.innerHTML = `<li class="skeleton-citation" aria-hidden="true"></li>`;
  traceEl.innerHTML = `
    <li class="trace-item skeleton-trace" aria-hidden="true"></li>
    <li class="trace-item skeleton-trace" aria-hidden="true"></li>
  `;
}

function renderCitationList(container, items, emptyLabel, renderItem) {
  container.innerHTML = "";
  if (!items?.length) {
    const item = document.createElement("li");
    item.textContent = emptyLabel;
    container.append(item);
    return;
  }
  for (const entry of items) {
    container.append(renderItem(entry));
  }
}

function renderResponse(payload) {
  answerGridEl.classList.remove("is-updating");
  void answerGridEl.offsetWidth;
  answerGridEl.classList.add("is-updating");

  answerEl.textContent = payload.answer || "No answer returned.";
  answerEl.classList.remove("error-text");

  routeMetaEl.hidden = false;
  routeBadgeEl.textContent = payload.route || "unknown";
  routeBadgeEl.dataset.route = payload.route || "";
  const confidence =
    typeof payload.confidence === "number" ? `${Math.round(payload.confidence * 100)}%` : "—";
  confidenceBadgeEl.textContent = `confidence ${confidence}`;
  resolvedMetaEl.textContent = payload.resolved_customer_id
    ? `scope ${payload.resolved_customer_id}`
    : "";

  if (payload.escalate) {
    escalateBannerEl.hidden = false;
    escalateDetailEl.textContent =
      "The supervisor flagged this case for human review. Do not treat the answer as final billing action.";
  } else {
    escalateBannerEl.hidden = true;
  }

  if (payload.redacted_customer_context) {
    contextEl.textContent = JSON.stringify(payload.redacted_customer_context, null, 2);
  } else {
    contextEl.textContent = "No customer context used.";
  }

  renderCitationList(
    dataCitationsEl,
    payload.data_citations,
    "No structured data citations.",
    (citation) => {
      const item = document.createElement("li");
      item.innerHTML = `<span class="cite-ref">${citation.ref}</span> — ${citation.detail} <span class="cite-source">(${citation.source})</span>`;
      return item;
    },
  );

  const policyItems =
    payload.policy_citations?.length > 0
      ? payload.policy_citations
      : (payload.citations || []).map((legacy) => ({
          doc_id: legacy.chunk_id || legacy.title,
          version: legacy.section || "",
          title: legacy.title,
          section: legacy.section,
        }));

  renderCitationList(policyCitationsEl, policyItems, "No policy citations.", (citation) => {
    const item = document.createElement("li");
    const title = citation.title || citation.doc_id;
    const version = citation.version ? ` v${citation.version}` : "";
    const section = citation.section ? ` · ${citation.section}` : "";
    item.textContent = `${title}${version}${section}`;
    return item;
  });

  traceEl.innerHTML = "";
  if (payload.trace?.length) {
    for (const step of payload.trace) {
      const item = document.createElement("li");
      item.className = "trace-item";

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
    item.textContent = "No trace returned.";
    traceEl.append(item);
  }
}

function renderError(message) {
  routeMetaEl.hidden = true;
  escalateBannerEl.hidden = true;
  answerEl.textContent = message;
  answerEl.classList.add("error-text");
  dataCitationsEl.innerHTML = `<li>No structured data citations.</li>`;
  policyCitationsEl.innerHTML = `<li>No policy citations.</li>`;
  traceEl.innerHTML = `<li class="trace-item">No trace yet.</li>`;
  contextEl.textContent = "No customer context used.";
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginButton.disabled = true;
  loginButton.textContent = "Signing in…";
  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: usernameInput.value.trim(),
        password: passwordInput.value,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Login failed");
    }
    sessionCustomerId = payload.customer_id;
    selectedCustomerId = payload.customer_id;
    passwordInput.value = "";
    selectPersona(payload.customer_id, { updateQuestion: true });
    updateAuthUi();
  } catch (error) {
    authHintEl.textContent =
      error instanceof Error ? error.message : "Unable to sign in with demo credentials.";
  } finally {
    loginButton.disabled = false;
    loginButton.textContent = "Sign in";
  }
});

logoutButton.addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  sessionCustomerId = null;
  usernameInput.value = "";
  passwordInput.value = "";
  updateAuthUi();
  await loadSession();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (isSubmitting) return;

  isSubmitting = true;
  answerEl.classList.remove("error-text");
  submitButton.disabled = true;
  submitButton.textContent = "Running…";
  submitButton.classList.add("is-loading");
  showSkeleton();

  try {
    const body = { question: questionInput.value.trim() };
    if (selectedCustomerId) {
      body.customer_id = selectedCustomerId;
    }

    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Request failed");
    }
    renderResponse(payload);
  } catch (error) {
    renderError(error instanceof Error ? error.message : "Unable to run the query.");
  } finally {
    isSubmitting = false;
    submitButton.disabled = false;
    submitButton.textContent = "Ask";
    submitButton.classList.remove("is-loading");
    questionInput.focus();
  }
});

questionInput.focus();
loadSession().then(() => loadDemoCustomers());
