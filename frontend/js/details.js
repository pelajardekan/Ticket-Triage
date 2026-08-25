import { api, formatDate, statusClass } from "./api.js";

const ticketCard = document.getElementById("ticket-card");

const ticketError = document.getElementById("ticket-error");

const ticketIdElement = document.getElementById("ticket-id");

const ticketStatus = document.getElementById("ticket-status");

const submittedOn = document.getElementById("submitted-on");

const ticketTitle = document.getElementById("ticket-title");

const ticketCategory = document.getElementById("ticket-category");

const ticketPriority = document.getElementById("ticket-priority");

const ticketDescription = document.getElementById("ticket-description");

const params = new URLSearchParams(window.location.search);

const ticketId = params.get("id");

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

function displayTicket(ticket) {
  const id = ticket.id ?? ticket.ticketId ?? "—";

  const category = getCategory(ticket);

  const priority = ticket.priority ?? "—";

  const status = ticket.status ?? "New";

  const submittedDate = getSubmittedDate(ticket);

  ticketIdElement.textContent = id;

  ticketStatus.textContent = status;

  ticketStatus.className = `badge ${statusClass(status)}`;

  submittedOn.textContent = submittedDate
    ? `Submitted On: ${formatDate(submittedDate)}`
    : "";

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
      ${message}
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

    /*
      Supports API returning:

      {
        id: "...",
        title: "..."
      }

      or:

      {
        ticket: {
          id: "...",
          title: "..."
        }
      }
    */

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

loadTicket();
