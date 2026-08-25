import { api, esc, getAdminKey, setAdminKey } from "./api.js";

const form = document.getElementById("admin-login-form");
const keyInput = document.getElementById("admin-key");
const button = document.getElementById("admin-login-button");
const message = document.getElementById("admin-login-message");

async function verifyAdminKey(key) {
  setAdminKey(key);
  await api.verifyAdmin();
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  button.disabled = true;
  button.textContent = "Checking...";
  message.innerHTML = "";

  try {
    await verifyAdminKey(keyInput.value);
    window.location.replace("/admin");
  } catch (error) {
    setAdminKey("");
    message.innerHTML = `<div class="form-notice error">${esc(
      error.status === 401 || error.status === 403
        ? "The admin key is incorrect."
        : (error.message || "Could not verify admin access.")
    )}</div>`;
  } finally {
    button.disabled = false;
    button.textContent = "Log in as Admin";
  }
});

if (getAdminKey()) {
  verifyAdminKey(getAdminKey())
    .then(() => window.location.replace("/admin"))
    .catch(() => setAdminKey(""));
}
