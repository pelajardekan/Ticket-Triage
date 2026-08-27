import { api, esc, formatDate, setAdminKey } from "./api.js";

const userBody = document.querySelector("[data-user-body]");
const userCount = document.querySelector("[data-user-count]");
const userSearch = document.getElementById("userSearch");
const clearUserSearch = document.getElementById("clearUserSearch");

let users = [];

function renderUsers() {
  const needle = (userSearch?.value || "").trim().toLowerCase();
  const filtered = users.filter((user) => {
    if (!needle) return true;
    const name = String(user.name || "").toLowerCase();
    const email = String(user.email || "").toLowerCase();
    return name.includes(needle) || email.includes(needle);
  });

  userBody.innerHTML = "";

  if (filtered.length === 0) {
    userBody.innerHTML = `
      <tr>
        <td colspan="4" style="text-align:center; padding:32px;">
          No users found.
        </td>
      </tr>
    `;
    userCount.textContent = "Showing 0 users";
    return;
  }

  filtered.forEach((user) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td style="font-weight:600;">${esc(user.name || "—")}</td>
      <td>${esc(user.email || "—")}</td>
      <td>${esc(user.ticketCount ?? 0)}</td>
      <td>${esc(formatDate(user.lastSubmittedAt) || "—")}</td>
    `;
    userBody.appendChild(row);
  });

  userCount.textContent = `Showing ${filtered.length} of ${users.length} users`;
}

async function loadUsers() {
  try {
    userCount.textContent = "Loading users...";
    const data = await api.listUsers();
    users = data.items || [];
    renderUsers();
  } catch (error) {
    console.error(error);
    userBody.innerHTML = `
      <tr>
        <td colspan="4" style="text-align:center; padding:32px;">
          Could not load users.
        </td>
      </tr>
    `;
    const message = (error.status === 401 || error.status === 403)
      ? "Admin access expired. Redirecting to Admin Login."
      : (error.message || "Could not load users.");
    userCount.textContent = message;
    if (error.status === 401 || error.status === 403) {
      setAdminKey("");
      window.location.replace("/admin/login");
    }
  }
}

userSearch?.addEventListener("input", renderUsers);

clearUserSearch?.addEventListener("click", () => {
  if (userSearch) userSearch.value = "";
  renderUsers();
});

loadUsers();
