// Login / register page.
import { api } from "./api.js";
import { notify } from "./toast.js";

const form = document.getElementById("authForm");
const errorBox = document.getElementById("authError");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const mode = form.dataset.mode;
  const data = Object.fromEntries(new FormData(form).entries());
  errorBox.hidden = true;

  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    await api("POST", mode === "register" ? "/auth/register" : "/auth/login", data);
    notify.success(mode === "register" ? "Account created. Welcome!" : "Signed in.");
    window.location.href = "/";
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.hidden = false;
    notify.error(error.message);
    button.disabled = false;
  }
});
