// Toast notifications shown after every action (success, error or info).
import { h } from "./dom.js";

const DURATIONS = { success: 3500, info: 4000, error: 7000 };

export function toast(message, type = "info") {
  const container = document.getElementById("toasts");
  if (!container) return;
  const node = h(
    "div",
    { class: `toast ${type}`, role: type === "error" ? "alert" : "status" },
    h("span", { class: "toast-icon", "aria-hidden": "true" }, type === "success" ? "✓" : type === "error" ? "!" : "i"),
    h("span", { class: "toast-text" }, message),
    h("button", { class: "toast-close", type: "button", "aria-label": "Dismiss", onclick: () => node.remove() }, "×"),
  );
  container.append(node);
  setTimeout(() => node.remove(), DURATIONS[type] ?? DURATIONS.info);
}

export const notify = {
  success: (message) => toast(message, "success"),
  error: (message) => toast(message, "error"),
  info: (message) => toast(message, "info"),
};
