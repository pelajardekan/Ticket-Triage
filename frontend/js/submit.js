import { api, esc, formatDate, statusClass } from "./api.js";

const form = document.getElementById("ticket-form");
const submitBtn = document.getElementById("submit-btn");
const banner = document.getElementById("banner");
const description = document.getElementById("description");
const counter = document.getElementById("counter");

const submitView = document.getElementById("submit-view");
const successView = document.getElementById("success-view");
const submittedTicketDetails = document.getElementById(
  "submitted-ticket-details"
);
const submitAnotherBtn = document.getElementById("submit-another-btn");


function clearFieldErrors() {
  document.querySelectorAll(".form-group[data-field]").forEach((group) => {
    group.classList.remove("invalid");
    const error = group.querySelector(".field-error");
    if (error) error.textContent = "";
  });
}

function showFieldErrors(fields = {}) {
  Object.entries(fields).forEach(([name, message]) => {
    const group = document.querySelector(`.form-group[data-field="${name}"]`);
    if (!group) return;

    group.classList.add("invalid");
    const error = group.querySelector(".field-error");
    if (error) error.textContent = message;
  });
}

function setBanner(kind, message) {
  if (!banner) return;
  banner.innerHTML = message
    ? `<div class="form-notice ${kind}" role="alert">${esc(message)}</div>`
    : "";
}

function updateCounter() {
  if (!description || !counter) return;
  counter.textContent = `${description.value.length}/${description.maxLength} characters`;
}


function priorityClass(priority) {
  return String(priority || "")
    .trim()
    .toLowerCase() || "medium";
}

function classificationMethodLabel(method) {
  return ({
    "azure-ai-language-custom": "Azure AI Language custom model",
    "azure-ai-language-keyphrase": "Azure AI Language key phrase extraction",
    "keyword-rules": "Keyword rules fallback",
  })[method] || method || "Not reported";
}


function showSubmittedTicket(ticket) {
  const id =
    ticket.id ??
    ticket.ticketId ??
    "—";

  if (id !== "—") {
    const url = new URL(window.location.href);
    url.searchParams.set("id", id);

    window.history.pushState({}, "", url);
  }

  const category =
    ticket.category ??
    ticket.suggestedCategory ??
    "—";

  const priority =
    ticket.priority ??
    "—";

  const status =
    ticket.status ??
    "New";

  const submittedAt =
    ticket.createdAt ??
    ticket.submittedAt ??
    ticket.created_at ??
    "";

  const classificationMethod = classificationMethodLabel(
    ticket.classificationMethod
  );
  const confidenceValue = Number(ticket.classificationConfidence);
  const confidence = Number.isFinite(confidenceValue)
    ? `${Math.round(confidenceValue * 100)}%`
    : "Not reported";
  const evidence = Array.isArray(ticket.classificationEvidence)
    ? ticket.classificationEvidence.join(", ")
    : "";
  const categoryNote = ticket.categorySource === "auto"
    ? "Suggested automatically"
    : "Selected by requester";

  submittedTicketDetails.innerHTML = `
    <strong>Ticket ID</strong>
    <span>${esc(id)}</span>

    <strong>Category</strong>
    <span style="color: #315db7; font-weight: 700">
      ${esc(category)} (${esc(categoryNote)})
    </span>

    <strong>Priority</strong>
    <span>
      <span class="badge ${esc(priorityClass(priority))}">
        ${esc(priority)}
      </span>
    </span>

    <strong>Status</strong>
    <span>
      <span class="badge ${esc(statusClass(status))}">
        ${esc(status)}
      </span>
    </span>

    <strong>Submitted On</strong>
    <span>
      ${esc(formatDate(submittedAt) || "Just now")}
    </span>

    <strong>Classified By</strong>
    <span>${esc(classificationMethod)}</span>

    <strong>Confidence</strong>
    <span>${esc(confidence)}</span>

    ${evidence ? `
      <strong>Classification Signals</strong>
      <span>${esc(evidence)}</span>
    ` : ""}
  `;

  submitView.hidden = true;
  successView.hidden = false;
}


async function loadCategories() {
  const select = document.getElementById("category");
  if (!select) return;

  try {
    const data = await api.categories();
    const categories = Array.isArray(data?.categories) ? data.categories : [];

    categories.forEach((category) => {
      const option = document.createElement("option");
      option.value = category;
      option.textContent = category;
      select.appendChild(option);
    });
  } catch (error) {
    setBanner(
      "warning",
      "Could not load the category list. You can still submit and let the system auto-detect it.",
    );
  }
}

form?.addEventListener("reset", () => {
  setTimeout(() => {
    clearFieldErrors();
    setBanner("", "");
    updateCounter();
  }, 0);
});

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFieldErrors();
  setBanner("", "");

  if (!form.checkValidity()) {
    form.reportValidity();
    return;
  }

  const payload = {
    name: document.getElementById("name").value.trim(),
    email: document.getElementById("email").value.trim(),
    title: document.getElementById("title").value.trim(),
    description: description.value.trim(),
    priority: document.getElementById("priority").value,
    category: document.getElementById("category").value,
  };

  submitBtn.disabled = true;
  submitBtn.textContent = "Submitting...";

  try {
    const ticket = await api.createTicket(payload);

    showSubmittedTicket(ticket);
  } catch (error) {
    showFieldErrors(error.fields);
    setBanner("error", error.message || "Could not submit the ticket.");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Submit";
  }
});


submitAnotherBtn?.addEventListener("click", () => {
  form.reset();

  clearFieldErrors();
  setBanner("", "");

  updateCounter();

  successView.hidden = true;
  submitView.hidden = false;

  const url = new URL(window.location.href);
  url.searchParams.delete("id");
  window.history.pushState({}, "", url);

  window.scrollTo({
    top: 0,
    behavior: "smooth"
  });
});


description?.addEventListener("input", updateCounter);
updateCounter();
loadCategories();
