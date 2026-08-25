/* Thin wrapper over the /api routes. Everything else talks to this. */

const API_BASE = "/api";

/** Remembered only for the current browser tab so admin detail pages can reuse it. */
let adminKey = "";
try { adminKey = sessionStorage.getItem("ticketTriageAdminKey") || ""; } catch {}
export function setAdminKey(value) {
  adminKey = (value || "").trim();
  try {
    if (adminKey) sessionStorage.setItem("ticketTriageAdminKey", adminKey);
    else sessionStorage.removeItem("ticketTriageAdminKey");
  } catch {}
}
export function getAdminKey() { return adminKey; }

async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (adminKey) headers["x-admin-key"] = adminKey;

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch (networkError) {
    throw new Error("Cannot reach the API. Is the function app running?");
  }

  const text = await response.text();
  let body = null;
  if (text) {
    try { body = JSON.parse(text); } catch { body = { error: text }; }
  }

  if (!response.ok) {
    const err = new Error((body && body.error) || `Request failed (${response.status})`);
    err.status = response.status;
    err.fields = (body && body.fields) || {};
    throw err;
  }
  return body;
}

export const api = {
  health: () => request("/health"),
  verifyAdmin: () => request("/admin/verify"),
  categories: () => request("/categories"),
  createTicket: (payload) => request("/tickets", { method: "POST", body: JSON.stringify(payload) }),
  listTickets: (filters = {}) => {
    const qs = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => { if (v) qs.append(k, v); });
    const suffix = qs.toString() ? `?${qs}` : "";
    return request(`/tickets${suffix}`);
  },
  getTicket: (id) => request(`/tickets/${encodeURIComponent(id)}`),
  updateTicket: (id, payload) =>
    request(`/tickets/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(payload) }),
};

/* ---- shared view helpers ---- */

export function statusClass(status) {
  return ({
    "New": "new",
    "Categorised": "categorised",
    "In Progress": "progress",
    "Resolved": "resolved",
  })[status] || "cat";
}

export function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

/** Always escape values before putting them in innerHTML. */
export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}
