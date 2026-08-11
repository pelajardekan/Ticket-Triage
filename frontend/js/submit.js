import { api, esc, formatDate } from "./api.js";

const form = document.getElementById("ticket-form");
const submitBtn = document.getElementById("submit-btn");
const resetBtn = document.getElementById("reset-btn");
const banner = document.getElementById("banner");
const result = document.getElementById("result");

function clearFieldErrors() {
  document.querySelectorAll(".field").forEach((f) => {
    f.classList.remove("invalid");
    const err = f.querySelector(".err");
    if (err) err.textContent = "";
  });
}

function showFieldErrors(fields) {
  Object.entries(fields || {}).forEach(([name, message]) => {
    const wrapper = document.querySelector(`.field[data-field="${name}"]`);
    if (!wrapper) return;
    wrapper.classList.add("invalid");
    const err = wrapper.querySelector(".err");
    if (err) err.textContent = message;
  });
}

function setBanner(kind, message) {
  banner.innerHTML = message ? `<div class="notice ${kind}">${esc(message)}</div>` : "";
}

/** Populate the category menu from the API so the list lives in one place. */
async function loadCategories() {
  try {
    const data = await api.categories();
    const select = document.getElementById("category");
    data.categories.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c;
      opt.textContent = c;
      select.appendChild(opt);
    });
  } catch {
    setBanner("warn", "Could not load the category list. You can still submit a ticket.");
  }
}

function methodLabel(method) {
  return ({
    "azure-ai-language-custom": "Azure AI Language, custom trained model",
    "azure-ai-language-keyphrase": "Azure AI Language, key phrase extraction",
    "keyword-rules": "Keyword rules (offline fallback)",
  })[method] || method;
}

function renderResult(ticket) {
  const auto = ticket.categorySource === "auto";
  const evidence = (ticket.classificationEvidence || []).map(esc).join(", ");
  result.innerHTML = `
    <div class="card result">
      <h2 style="margin:0 0 4px;font-size:1.1rem;">Ticket submitted</h2>
      <p class="muted" style="margin:0;">Keep this reference number for follow-up.</p>
      <dl>
        <dt>Reference</dt><dd class="mono">${esc(ticket.id)}</dd>
        <dt>Title</dt><dd>${esc(ticket.title)}</dd>
        <dt>Category</dt>
        <dd>
          <span class="pill cat">${esc(ticket.category)}</span>
          ${auto ? '<span class="muted"> suggested automatically</span>' : '<span class="muted"> chosen by you</span>'}
        </dd>
        <dt>Status</dt><dd><span class="pill new">${esc(ticket.status)}</span></dd>
        <dt>Priority</dt><dd>${esc(ticket.priority)}</dd>
        <dt>Submitted</dt><dd>${esc(formatDate(ticket.createdAt))}</dd>
        <dt>Classified by</dt>
        <dd>${esc(methodLabel(ticket.classificationMethod))}
            <span class="muted">(confidence ${esc(ticket.classificationConfidence)})</span></dd>
        ${evidence ? `<dt>Signals</dt><dd class="muted">${evidence}</dd>` : ""}
      </dl>
    </div>`;
  result.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFieldErrors();
  setBanner("", "");

  const payload = {
    name: document.getElementById("name").value,
    email: document.getElementById("email").value,
    title: document.getElementById("title").value,
    description: document.getElementById("description").value,
    priority: document.getElementById("priority").value,
    category: document.getElementById("category").value,
  };

  submitBtn.disabled = true;
  submitBtn.textContent = "Submitting...";
  try {
    const ticket = await api.createTicket(payload);
    renderResult(ticket);
    form.reset();
  } catch (error) {
    showFieldErrors(error.fields);
    setBanner("bad", error.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Submit ticket";
  }
});

resetBtn.addEventListener("click", () => {
  form.reset();
  clearFieldErrors();
  setBanner("", "");
  result.innerHTML = "";
});

loadCategories();
