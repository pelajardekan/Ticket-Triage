// Function to load sidebar and topbar
const menuToggle = document.getElementById("menuToggle");
const sidebar = document.querySelector(".sidebar");

menuToggle?.addEventListener("click", () => {
  sidebar.classList.toggle("collapsed");
});

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

async function loadTopbar() {
  const container = document.getElementById("topbar-container");

  if (!container) return;

  const response = await fetch("../components/topbar.html");
  const html = await response.text();

  container.innerHTML = html;

  const role = container.dataset.role || "student";
  const roleTag = document.getElementById("topbarRole");

  if (roleTag && role === "admin") {
    roleTag.textContent = role.toUpperCase();
    roleTag.classList.add(role);
    roleTag.hidden = false;
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

  document.getElementById("adminLogout")?.addEventListener("click", () => {
    try { sessionStorage.removeItem("ticketTriageAdminKey"); } catch {}
    window.location.assign("/submit");
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
