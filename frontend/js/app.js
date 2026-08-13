const tickets = [
  {
    id: "TKT-20261008-0001",
    title: "Cannot access campus Wi-Fi",
    category: "IT Support",
    priority: "Medium",
    status: "Categorised",
    submitted: "10 August 2026, 08:00 AM",
    name: "Fatiha Syuhada",
    email: "fasyy007@gmail.com",
    description:
      "I cannot connect to the campus Wi-Fi from my laptop. I have tried restarting but the issue continues.",
  },
  {
    id: "TKT-20261008-0002",
    title: "Course registration error",
    category: "Course registration",
    priority: "High",
    status: "In Progress",
    submitted: "10 August 2026, 08:05 AM",
    name: "Fatiha Syuhada",
    email: "fatihasyuhadazz@gmail.com",
    description: "I receive an error while trying to register for a course.",
  },
  {
    id: "TKT-20261008-0003",
    title: "Library book renewal issue",
    category: "Library Services",
    priority: "Low",
    status: "Resolved",
    submitted: "10 August 2026, 08:10 AM",
    name: "Fatiha Syuhada",
    email: "fatihasyuhadazz@gmail.com",
    description: "I am unable to renew a borrowed library book online.",
  },
];

// Menu Toggle for Sidebar
const menuToggle = document.getElementById("menuToggle");
const sidebar = document.querySelector(".sidebar");

menuToggle?.addEventListener("click", () => {
  sidebar.classList.toggle("collapsed");
});

// Load Sidebar
async function loadSidebar() {
  const container = document.getElementById("sidebar-container");

  if (!container) return;

  const type = container.dataset.sidebar;

  const sidebarFile =
    type === "admin"
      ? "../components/admin-sidebar.html"
      : "../components/sidebar.html";

  const response = await fetch(sidebarFile);
  const html = await response.text();

  container.innerHTML = html;

  setupSidebar();
}

// Load Topbar
async function loadTopbar() {
  const container = document.getElementById("topbar-container");

  if (!container) return;

  const response = await fetch("../components/topbar.html");
  const html = await response.text();

  container.innerHTML = html;

  const role = container.dataset.role || "student";
  const roleTag = document.getElementById("topbarRole");

  if (roleTag) {
    roleTag.textContent = role.toUpperCase();
    roleTag.classList.add(role);
  }
}

function setupSidebar() {
  const sidebar = document.querySelector(".sidebar");
  const menuToggle = document.getElementById("menuToggle");
  const appShell = document.querySelector(".app-shell");

  const isCollapsed = localStorage.getItem("sidebarCollapsed") === "true";

  if (isCollapsed) {
    sidebar.classList.add("collapsed");
    appShell.classList.add("sidebar-collapsed");
  }

  menuToggle?.addEventListener("click", () => {
    sidebar.classList.toggle("collapsed");
    appShell.classList.toggle("sidebar-collapsed");

    const collapsed = sidebar.classList.contains("collapsed");

    localStorage.setItem("sidebarCollapsed", collapsed);
  });

  setActiveSidebarLink();
}

function setActiveSidebarLink() {
  const currentPage = window.location.pathname.split("/").pop();

  const sideLinks = document.querySelectorAll(".side-link");

  sideLinks.forEach((link) => {
    const linkPage = link.getAttribute("href").split("/").pop();

    link.classList.remove("active");

    if (linkPage === currentPage) {
      link.classList.add("active");
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadSidebar();
  loadTopbar();
});

function badgeClass(value) {
  const v = value.toLowerCase();
  if (v.includes("in progress")) return "progress";
  return v.replace(/\s+/g, "-");
}

function renderTicketRows() {
  const body = document.querySelector("[data-ticket-body]");
  if (!body) return;
  const category = document.querySelector("#filterCategory")?.value || "All";
  const priority = document.querySelector("#filterPriority")?.value || "All";
  const status = document.querySelector("#filterStatus")?.value || "All";

  const filtered = tickets.filter(
    (t) =>
      (category === "All" || t.category === category) &&
      (priority === "All" || t.priority === priority) &&
      (status === "All" || t.status === status),
  );

  body.innerHTML = filtered
    .map(
      (t) => `
    <tr>
      <td>${t.id}</td>
      <td>${t.title}</td>
      <td>${t.category}</td>
      <td><span class="badge ${badgeClass(t.priority)}">${t.priority}</span></td>
      <td><span class="badge ${badgeClass(t.status)}">${t.status}</span></td>
      <td>${t.submitted}</td>
      <td><a class="ticket-link" href="${document.body.dataset.role === "admin" ? "ticket-details.html" : "ticket-details.html"}">View</a></td>
    </tr>
  `,
    )
    .join("");

  const count = document.querySelector("[data-ticket-count]");
  if (count)
    count.textContent = `Showing 1 to ${filtered.length} of ${filtered.length} tickets`;
}

function clearFilters() {
  ["filterCategory", "filterPriority", "filterStatus"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.value = "All";
  });
  renderTicketRows();
}

document.addEventListener("DOMContentLoaded", () => {
  renderTicketRows();
  ["filterCategory", "filterPriority", "filterStatus"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", renderTicketRows);
  });
  document
    .getElementById("clearFilters")
    ?.addEventListener("click", clearFilters);

  const desc = document.getElementById("description");
  const counter = document.getElementById("counter");
  if (desc && counter) {
    const update = () =>
      (counter.textContent = `${desc.value.length}/200 characters`);
    desc.addEventListener("input", update);
    update();
  }

  document.getElementById("ticketForm")?.addEventListener("submit", (e) => {
    e.preventDefault();
    window.location.href = "ticket-submitted.html";
  });

  document.getElementById("signinForm")?.addEventListener("submit", (e) => {
    e.preventDefault();
    window.location.href = "user/submit-ticket.html";
  });

  document.getElementById("signupForm")?.addEventListener("submit", (e) => {
    e.preventDefault();
    window.location.href = "signin.html";
  });
});
