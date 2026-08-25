import { api, esc, formatDate, getAdminKey, setAdminKey, statusClass } from "./api.js";

const ticketBody = document.querySelector("[data-ticket-body]");

const ticketCount = document.querySelector("[data-ticket-count]");

const filterCategory = document.getElementById("filterCategory");

const filterPriority = document.getElementById("filterPriority");

const filterStatus = document.getElementById("filterStatus");

const clearFilters = document.getElementById("clearFilters");

const previousPage = document.getElementById("previousPage");

const nextPage = document.getElementById("nextPage");

const pageNumbers = document.getElementById("pageNumbers");

const adminKeyInput = document.getElementById("admin-key");
const saveAdminKey = document.getElementById("save-admin-key");
const refreshTickets = document.getElementById("refresh-tickets");
const adminKeyMessage = document.getElementById("admin-key-message");

let tickets = [];
let filteredTickets = [];

let currentPage = 1;

const ticketsPerPage = 10;

function getCategory(ticket) {
  return ticket.category ?? ticket.suggestedCategory ?? "—";
}

function getPriority(ticket) {
  return ticket.priority ?? "—";
}

function getStatus(ticket) {
  return ticket.status ?? "New";
}

function getSubmittedDate(ticket) {
  return ticket.createdAt ?? ticket.submittedAt ?? ticket.created_at ?? "";
}

function priorityClass(priority) {
  return String(priority || "")
    .trim()
    .toLowerCase();
}

function renderPagination(totalPages) {
  pageNumbers.innerHTML = "";

  if (totalPages <= 1) {
    previousPage.disabled = true;
    nextPage.disabled = true;
    return;
  }

  const pages = [];

  if (totalPages <= 4) {
    for (let i = 1; i <= totalPages; i++) {
      pages.push(i);
    }
  } else {
    pages.push(1, 2, "...", totalPages - 1, totalPages);
  }

  pages.forEach((page) => {
    if (page === "...") {
      const dots = document.createElement("span");

      dots.className = "pagination-dots";

      dots.textContent = "...";

      pageNumbers.appendChild(dots);

      return;
    }

    const button = document.createElement("button");

    button.textContent = page;

    if (page === currentPage) {
      button.classList.add("current");
    }

    button.addEventListener("click", () => {
      currentPage = page;

      renderTickets();
    });

    pageNumbers.appendChild(button);
  });

  previousPage.disabled = currentPage === 1;

  nextPage.disabled = currentPage === totalPages;
}

function renderTickets() {
  ticketBody.innerHTML = "";

  const totalTickets = filteredTickets.length;

  if (totalTickets === 0) {
    ticketBody.innerHTML = `
      <tr>
        <td
          colspan="8"
          style="text-align:center; padding:32px;"
        >
          No tickets found.
        </td>
      </tr>
    `;

    ticketCount.textContent = "Showing 0 tickets";

    pageNumbers.innerHTML = "";

    previousPage.disabled = true;
    nextPage.disabled = true;

    return;
  }

  const totalPages = Math.ceil(totalTickets / ticketsPerPage);

  if (currentPage > totalPages) {
    currentPage = totalPages;
  }

  const startIndex = (currentPage - 1) * ticketsPerPage;

  const endIndex = Math.min(startIndex + ticketsPerPage, totalTickets);

  const ticketsToDisplay = filteredTickets.slice(startIndex, endIndex);

  ticketsToDisplay.forEach((ticket) => {
    const id = ticket.id ?? ticket.ticketId ?? "";

    const category = getCategory(ticket);

    const priority = getPriority(ticket);

    const status = getStatus(ticket);

    const submittedAt = getSubmittedDate(ticket);

    const row = document.createElement("tr");

    row.innerHTML = `

      <td style="white-space:nowrap;">
        ${esc(id)}
      </td>


      <td>
        <div style="font-weight:600;">
          ${esc(ticket.name ?? "—")}
        </div>

        <div
          style="
            font-size:13px;
            color:#6b7280;
            margin-top:3px;
          "
        >
          ${esc(ticket.email ?? "—")}
        </div>
      </td>


      <td>
        ${esc(ticket.title ?? "—")}
      </td>


      <td
        style="
          color:#315db7;
          font-weight:700;
        "
      >
        ${esc(category)}
      </td>


      <td>
        <span
          class="badge ${esc(priorityClass(priority))}"
        >
          ${esc(priority)}
        </span>
      </td>


      <td>
        <span
          class="badge ${esc(statusClass(status))}"
        >
          ${esc(status)}
        </span>
      </td>


      <td>
        ${esc(formatDate(submittedAt) || "—")}
      </td>


      <td>

        <a
          class="btn-outline"
          href="/admin/details?id=${encodeURIComponent(id)}"
        >
          View
        </a>

      </td>
    `;

    ticketBody.appendChild(row);
  });

  ticketCount.textContent = `Showing ${startIndex + 1} to ${endIndex} of ${totalTickets} tickets`;

  renderPagination(totalPages);
}

function applyFilters() {
  const category = filterCategory.value;

  const priority = filterPriority.value;

  const status = filterStatus.value;

  filteredTickets = tickets.filter((ticket) => {
    const categoryMatches =
      category === "All" || getCategory(ticket) === category;

    const priorityMatches =
      priority === "All" || getPriority(ticket) === priority;

    const statusMatches = status === "All" || getStatus(ticket) === status;

    return categoryMatches && priorityMatches && statusMatches;
  });

  currentPage = 1;

  renderTickets();
}

async function loadReferenceData() {
  try {
    const data = await api.categories();

    (data.categories || []).forEach((category) => {
      filterCategory.add(new Option(category, category));
    });

    (data.statuses || []).forEach((status) => {
      filterStatus.add(new Option(status, status));
    });
  } catch (error) {
    console.error("Could not load categories/statuses:", error);
  }
}

async function loadTickets() {
  try {
    ticketCount.textContent = "Loading tickets...";

    const data = await api.listTickets();

    tickets = data.items || [];

    filteredTickets = [...tickets];

    renderTickets();
  } catch (error) {
    console.error(error);

    ticketBody.innerHTML = `
      <tr>
        <td
          colspan="8"
          style="text-align:center; padding:32px;"
        >
          Could not load tickets.
        </td>
      </tr>
    `;

    const message = (error.status === 401 || error.status === 403)
      ? "Admin access was denied. Enter the ADMIN_API_KEY above and try again."
      : (error.message || "Could not load tickets.");

    ticketCount.textContent = message;
  }
}

async function applyAdminKey() {
  setAdminKey(adminKeyInput?.value || "");
  if (adminKeyMessage) {
    adminKeyMessage.innerHTML = `<div class="form-notice success">Admin key applied for this browser tab.</div>`;
  }
  await loadTickets();
}

if (adminKeyInput) adminKeyInput.value = getAdminKey();
saveAdminKey?.addEventListener("click", applyAdminKey);
refreshTickets?.addEventListener("click", loadTickets);
adminKeyInput?.addEventListener("keydown", (event) => {
  if (event.key === "Enter") applyAdminKey();
});

filterCategory?.addEventListener("change", applyFilters);

filterPriority?.addEventListener("change", applyFilters);

filterStatus?.addEventListener("change", applyFilters);

clearFilters?.addEventListener("click", () => {
  filterCategory.value = "All";
  filterPriority.value = "All";
  filterStatus.value = "All";

  applyFilters();
});

previousPage?.addEventListener("click", () => {
  if (currentPage > 1) {
    currentPage--;

    renderTickets();
  }
});

nextPage?.addEventListener("click", () => {
  const totalPages = Math.ceil(filteredTickets.length / ticketsPerPage);

  if (currentPage < totalPages) {
    currentPage++;

    renderTickets();
  }
});

async function init() {
  await loadReferenceData();

  await loadTickets();
}

init();
