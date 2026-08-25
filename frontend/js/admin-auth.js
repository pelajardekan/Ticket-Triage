import { api, getAdminKey, setAdminKey } from "./api.js";

async function requireAdminAccess() {
  if (!getAdminKey()) {
    window.location.replace("/admin/login");
    return;
  }

  try {
    await api.verifyAdmin();
    document.body.classList.remove("admin-protected");
  } catch {
    setAdminKey("");
    window.location.replace("/admin/login");
  }
}

requireAdminAccess();
