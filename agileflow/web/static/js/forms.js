// Generic modal form built on the native <dialog> element.
import { clear, h } from "./dom.js";
import { notify } from "./toast.js";

function fieldControl(field, value) {
  const common = {
    name: field.name,
    required: field.required,
    maxlength: field.maxlength,
    placeholder: field.placeholder,
  };
  if (field.type === "textarea") return h("textarea", { ...common, rows: 3 }, value ?? "");
  if (field.type === "select") {
    return h(
      "select",
      { name: field.name },
      field.options.map((o) => h("option", { value: o.value, selected: String(o.value) === String(value ?? "") }, o.label)),
    );
  }
  return h("input", { ...common, type: field.type ?? "text", value: value ?? "" });
}

/**
 * Open a modal form.
 * fields: [{name, label, type: text|textarea|select|date|email, required, options, maxlength}]
 * onSubmit(values) may throw; the message is shown in the form and as a toast.
 */
export function openForm({ title, fields, values = {}, submitLabel = "Save", onSubmit }) {
  const dialog = document.getElementById("formDialog");
  clear(dialog);

  const errorBox = h("p", { class: "form-error", role: "alert", hidden: true });
  const submit = h("button", { type: "submit", class: "btn primary" }, submitLabel);
  const form = h(
    "form",
    { novalidate: true },
    h("h2", { id: "formDialogTitle" }, title),
    fields.map((f) => h("label", {}, f.label, fieldControl(f, values[f.name]))),
    errorBox,
    h(
      "div",
      { class: "dialog-actions" },
      h("button", { type: "button", class: "btn ghost", onclick: () => dialog.close() }, "Cancel"),
      submit,
    ),
  );

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorBox.hidden = true;
    const result = {};
    for (const f of fields) result[f.name] = form.elements[f.name].value.trim();
    const missing = fields.find((f) => f.required && !result[f.name]);
    if (missing) {
      errorBox.textContent = `${missing.label} is required.`;
      errorBox.hidden = false;
      return;
    }
    submit.disabled = true;
    try {
      await onSubmit(result);
      dialog.close();
    } catch (error) {
      errorBox.textContent = error.message;
      errorBox.hidden = false;
      notify.error(error.message);
    } finally {
      submit.disabled = false;
    }
  });

  dialog.append(form);
  dialog.showModal();
  form.querySelector("input, textarea, select")?.focus();
}

export function confirmAction(message) {
  return window.confirm(message);
}
