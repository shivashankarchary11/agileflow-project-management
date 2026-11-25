// Team view: who is in the project and their role.
import { chip, clear, h } from "./dom.js";
import { memberForm, removeMember } from "./editors.js";

export function renderTeam(container, ctx) {
  const { project } = ctx.state;
  const canManage = project.capabilities["member.manage"];
  clear(container);
  if (canManage) {
    container.append(h("div", { class: "view-actions" }, h("button", { class: "btn primary", type: "button", onclick: () => memberForm(ctx) }, "+ Add teammate")));
  }
  container.append(
    h(
      "table",
      { class: "table" },
      h("thead", {}, h("tr", {}, h("th", {}, "Name"), h("th", {}, "Email"), h("th", {}, "Role"), canManage ? h("th", {}, "") : null)),
      h(
        "tbody",
        {},
        project.members.map((m) =>
          h(
            "tr",
            {},
            h("td", {}, m.name),
            h("td", {}, m.email),
            h("td", {}, chip(m.role)),
            canManage
              ? h("td", {}, m.id === project.owner_id ? null : h("button", { class: "btn danger small", type: "button", onclick: () => removeMember(ctx, m) }, "Remove"))
              : null,
          ),
        ),
      ),
    ),
  );
  if (canManage) {
    container.append(h("p", { class: "muted small" }, "Teammates must register first. Adding someone sends them an email notification."));
  }
}
