import { api, esc, formatDate, setAdminKey, statusClass } from "./api.js";

const els = {
  banner: document.getElementById("banner"),
  stats: document.getElementById("stats"),
  rows: document.getElementById("rows"),
  category: document.getElementById("f-category"),
  status: document.getElementById("f-status"),
  email: document.getElementById("f-email"),
  q: document.getElementById("f-q"),
  apply: document.getElementById("apply"),
  clear: document.getElementById("clear"),
  refresh: document.getElementById("refresh"),
  adminKey: document.getElementById("admin-key"),
};

let reference = { categories: [], statuses: [], priorities: [] };

function setBanner(kind, message) {
  els.banner.innerHTML = message ? `<div class="notice ${kind}">${message}</div>` : "";
}

function methodShort(method) {
  return ({
    "azure-ai-language-custom": "AI custom model",
    "azure-ai-language-keyphrase": "AI key phrases",
    "keyword-rules": "keyword rules",
  })[method] || method || "unknown";
}

async function loadReference() {
  reference = await api.categories();
  reference.categories.forEach((c) => els.category.add(new Option(c, c)));
  reference.statuses.forEach((s) => els.status.add(new Option(s, s)));
}

async function loadHealth() {
  try {
    const h = await api.health();
    const warnings = (h.warnings || []).map((w) => `<li>${esc(w)}</li>`).join("");
    els.stats.innerHTML = `
      <div class="stat"><div class="n">${esc(h.stats?.total ?? 0)}</div><div class="k">Tickets</div></div>
      <div class="stat"><div class="n">${esc(h.storage)}</div><div class="k">Storage</div></div>
      <div class="stat"><div class="n">${esc(methodShort(h.classifierChain?.[0]))}</div><div class="k">Classifier</div></div>`;
    if (warnings) setBanner("warn", `<strong>Configuration notes</strong><ul style="margin:6px 0 0 18px;">${warnings}</ul>`);
  } catch {
    els.stats.innerHTML = "";
  }
}

function actionCell(ticket) {
  const statusOptions = reference.statuses
    .map((s) => `<option value="${esc(s)}"${s === ticket.status ? " selected" : ""}>${esc(s)}</option>`)
    .join("");
  const categoryOptions = reference.categories
    .map((c) => `<option value="${esc(c)}"${c === ticket.category ? " selected" : ""}>${esc(c)}</option>`)
    .join("");
  return `
    <div style="display:flex;flex-direction:column;gap:6px;">
      <select class="sm js-status" data-id="${esc(ticket.id)}">${statusOptions}</select>
      <select class="sm js-category" data-id="${esc(ticket.id)}">${categoryOptions}</select>
      <button class="sm js-save" data-id="${esc(ticket.id)}">Save</button>
    </div>`;
}

function detailCell(ticket) {
  const evidence = (ticket.classificationEvidence || []).map(esc).join(", ");
  const history = (ticket.statusHistory || [])
    .map((h) => `<li>${esc(h.status)} &middot; ${esc(formatDate(h.at))} &middot; ${esc(h.by)}${h.note ? ` &middot; ${esc(h.note)}` : ""}</li>`)
    .join("");
  return `
    <details class="row-detail">
      <summary>Details</summary>
      <div class="body">
        <p style="margin:0 0 8px;">${esc(ticket.description)}</p>
        <p class="muted" style="margin:0 0 4px;">
          Suggested <strong>${esc(ticket.suggestedCategory)}</strong> by ${esc(methodShort(ticket.classificationMethod))},
          confidence ${esc(ticket.classificationConfidence)}.
        </p>
        ${evidence ? `<p class="muted" style="margin:0 0 4px;">Signals: ${evidence}</p>` : ""}
        ${history ? `<ul class="muted" style="margin:6px 0 0 18px;padding:0;">${history}</ul>` : ""}
        <p class="mono muted" style="margin:8px 0 0;">${esc(ticket.id)}</p>
      </div>
    </details>`;
}

function renderRows(items) {
  if (!items.length) {
    els.rows.innerHTML = `<tr><td colspan="7" class="muted" style="padding:22px;">No tickets match these filters.</td></tr>`;
    return;
  }
  els.rows.innerHTML = items.map((t) => `
    <tr>
      <td class="muted" style="white-space:nowrap;">${esc(formatDate(t.createdAt))}</td>
      <td>${esc(t.name)}<div class="muted">${esc(t.email)}</div></td>
      <td>${esc(t.title)}${detailCell(t)}</td>
      <td><span class="pill cat">${esc(t.category)}</span></td>
      <td><span class="pill ${esc(String(t.priority).toLowerCase())}">${esc(t.priority)}</span></td>
      <td><span class="pill ${esc(statusClass(t.status))}">${esc(t.status)}</span></td>
      <td>${actionCell(t)}</td>
    </tr>`).join("");

  els.rows.querySelectorAll(".js-save").forEach((btn) => {
    btn.addEventListener("click", () => saveTicket(btn.dataset.id, btn));
  });
}

async function saveTicket(id, button) {
  const status = els.rows.querySelector(`.js-status[data-id="${CSS.escape(id)}"]`).value;
  const category = els.rows.querySelector(`.js-category[data-id="${CSS.escape(id)}"]`).value;

  button.disabled = true;
  button.textContent = "Saving...";
  try {
    setAdminKey(els.adminKey.value);
    await api.updateTicket(id, { status, category });
    setBanner("ok", "Ticket updated.");
    await Promise.all([load(), loadHealth()]);
  } catch (error) {
    setBanner("bad", esc(error.message));
    button.disabled = false;
    button.textContent = "Save";
  }
}

async function load() {
  els.rows.innerHTML = `<tr><td colspan="7" class="muted" style="padding:22px;">Loading tickets...</td></tr>`;
  try {
    const data = await api.listTickets({
      category: els.category.value,
      status: els.status.value,
      email: els.email.value,
      q: els.q.value,
    });
    renderRows(data.items || []);
  } catch (error) {
    els.rows.innerHTML = `<tr><td colspan="7" class="notice bad" style="margin:0;">${esc(error.message)}</td></tr>`;
  }
}

els.apply.addEventListener("click", load);
els.refresh.addEventListener("click", () => Promise.all([load(), loadHealth()]));
els.clear.addEventListener("click", () => {
  els.category.value = ""; els.status.value = ""; els.email.value = ""; els.q.value = "";
  load();
});
[els.email, els.q].forEach((input) => {
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") load(); });
});
els.adminKey.addEventListener("change", () => setAdminKey(els.adminKey.value));

(async function init() {
  try { await loadReference(); } catch { setBanner("warn", "Could not load reference lists."); }
  await Promise.all([load(), loadHealth()]);
})();
