import { api, esc, formatDate, statusClass } from "./api.js";

const ticketCard = document.getElementById("ticket-card");

const ticketError = document.getElementById("ticket-error");

const ticketIdElement = document.getElementById("ticket-id");

const ticketStatus = document.getElementById("ticket-status");

const submittedOn = document.getElementById("submitted-on");

const ticketName = document.getElementById("ticket-name");

const ticketEmail = document.getElementById("ticket-email");

const ticketTitle = document.getElementById("ticket-title");

const ticketCategory = document.getElementById("ticket-category");

const ticketPriority = document.getElementById("ticket-priority");

const ticketDescription = document.getElementById("ticket-description");

const currentStatus = document.getElementById("current-status");

const newStatus = document.getElementById("new-status");

const updateStatusBtn = document.getElementById("update-status-btn");

const updateMessage = document.getElementById("update-message");

const params = new URLSearchParams(window.location.search);

const ticketId = params.get("id");

let loadedTicket = null;

function priorityClass(priority) {
  return String(priority || "")
    .trim()
    .toLowerCase();
}

function getCategory(ticket) {
  return ticket.category ?? ticket.suggestedCategory ?? "—";
}

function getSubmittedDate(ticket) {
  return ticket.createdAt ?? ticket.submittedAt ?? ticket.created_at ?? "";
}

async function loadStatuses() {
  try {
    const data = await api.categories();

    const statuses = data.statuses || [];

    newStatus.innerHTML = "";

    statuses.forEach((status) => {
      newStatus.add(new Option(status, status));
    });
  } catch (error) {
    console.error("Could not load statuses:", error);
  }
}

function displayTicket(ticket) {
  loadedTicket = ticket;

  const id = ticket.id ?? ticket.ticketId ?? "—";

  const category = getCategory(ticket);

  const priority = ticket.priority ?? "—";

  const status = ticket.status ?? "New";

  const submittedDate = getSubmittedDate(ticket);

  ticketIdElement.textContent = id;

  ticketStatus.textContent = status;

  ticketStatus.className = `badge ${statusClass(status)}`;

  currentStatus.textContent = status;

  currentStatus.className = `badge ${statusClass(status)}`;

  newStatus.value = status;

  submittedOn.textContent = submittedDate
    ? `Submitted On: ${formatDate(submittedDate)}`
    : "";

  ticketName.textContent = ticket.name ?? "—";

  ticketEmail.textContent = ticket.email ?? "—";

  ticketTitle.textContent = ticket.title ?? "—";

  ticketCategory.textContent = category;

  ticketPriority.textContent = priority;

  ticketPriority.className = `badge ${priorityClass(priority)}`;

  ticketDescription.textContent = ticket.description ?? "—";
}

function showError(message) {
  ticketCard.style.display = "none";

  ticketError.style.display = "block";

  ticketError.innerHTML = `
    <div class="form-notice error">
      ${esc(message)}
    </div>
  `;
}

async function loadTicket() {
  if (!ticketId) {
    showError("No ticket ID was provided.");

    return;
  }

  try {
    const data = await api.getTicket(ticketId);

    const ticket = data?.ticket ?? data;

    if (!ticket) {
      showError("Ticket not found.");

      return;
    }

    displayTicket(ticket);
  } catch (error) {
    console.error(error);

    if (error.status === 404) {
      showError("Ticket not found.");

      return;
    }

    showError(error.message || "Could not load the ticket.");
  }
}

async function updateStatus() {
  if (!loadedTicket) {
    return;
  }

  const status = newStatus.value;

  if (!status) {
    return;
  }

  if (status === loadedTicket.status) {
    updateMessage.innerHTML = `
      <div class="form-notice warning">
        The ticket is already ${esc(status)}.
      </div>
    `;

    return;
  }

  updateStatusBtn.disabled = true;

  updateStatusBtn.textContent = "Updating...";

  updateMessage.innerHTML = "";

  try {
    const updatedTicket = await api.updateTicket(ticketId, {
      status: status,
    });

    loadedTicket = updatedTicket;

    displayTicket(updatedTicket);

    updateMessage.innerHTML = `
      <div class="form-notice success">
        Status updated successfully.
      </div>
    `;
  } catch (error) {
    console.error(error);

    updateMessage.innerHTML = `
      <div class="form-notice error">
        ${esc(error.message || "Could not update the status.")}
      </div>
    `;
  } finally {
    updateStatusBtn.disabled = false;

    updateStatusBtn.textContent = "Update";
  }
}

updateStatusBtn?.addEventListener("click", updateStatus);

async function init() {
  await loadStatuses();

  await loadTicket();
}

init();
