// Kanban board: three columns, drag a card to change its status.
import { get } from "./api.js";
import { chip, clear, h, todayISO } from "./dom.js";
import { WORK_STATUSES, quickPatch, taskForm } from "./editors.js";

function filterQuery(filters) {
  const params = new URLSearchParams();
  for (const key of ["q", "priority", "assignee_id"]) if (filters[key]) params.set(key, filters[key]);
  return params.toString();
}

function card(ctx, task) {
  const { project } = ctx.state;
  const canEdit = project.capabilities["task.edit"];
  const overdue = task.due_date && task.status !== "Done" && task.due_date < todayISO();
  const story = project.stories.find((s) => s.id === task.story_id);

  const el = h(
    "article",
    {
      class: `card prio-${task.story_priority.toLowerCase()}`,
      draggable: canEdit ? "true" : null,
      dataset: { taskId: task.id },
      ondragstart: (event) => {
        event.dataTransfer.setData("text/plain", String(task.id));
        event.dataTransfer.effectAllowed = "move";
        el.classList.add("dragging");
      },
      ondragend: () => el.classList.remove("dragging"),
    },
    h("h4", {}, task.title),
    h("p", { class: "muted small" }, `Story: ${task.story_title}`),
    h(
      "div",
      { class: "meta" },
      chip(task.story_priority, `prio-${task.story_priority.toLowerCase()}`),
      task.assigned_to ? chip(`👤 ${task.assigned_to}`) : chip("Unassigned", "muted"),
      task.due_date ? chip(`Due ${task.due_date}`, overdue ? "danger" : "") : null,
    ),
    canEdit
      ? h(
          "div",
          { class: "card-actions" },
          h(
            "select",
            {
              "aria-label": `Move “${task.title}” to column`,
              onchange: (event) =>
                quickPatch(ctx, `/api/tasks/${task.id}/move`, { status: event.target.value }, `Moved to ${event.target.value}.`),
            },
            WORK_STATUSES.map((s) => h("option", { value: s, selected: s === task.status }, s)),
          ),
          h(
            "button",
            { class: "btn ghost small", type: "button", onclick: () => story && taskForm(ctx, story, story.tasks.find((t) => t.id === task.id)) },
            "Edit",
          ),
        )
      : null,
  );
  return el;
}

function column(ctx, status, tasks) {
  const canEdit = ctx.state.project.capabilities["task.edit"];
  const body = h("div", { class: "column-body" }, tasks.length ? tasks.map((t) => card(ctx, t)) : h("p", { class: "empty small" }, "No tasks"));
  const el = h(
    "section",
    {
      class: "column",
      dataset: { status },
      "aria-label": `${status} column`,
      ondragover: (event) => {
        if (!canEdit) return;
        event.preventDefault();
        el.classList.add("drop-target");
      },
      ondragleave: () => el.classList.remove("drop-target"),
      ondrop: (event) => {
        event.preventDefault();
        el.classList.remove("drop-target");
        const id = Number(event.dataTransfer.getData("text/plain"));
        const dropped = tasks.find((t) => t.id === id);
        if (dropped) return; // already in this column
        if (id) quickPatch(ctx, `/api/tasks/${id}/move`, { status }, `Moved to ${status}.`);
      },
    },
    h("header", { class: "column-head" }, h("h3", {}, status), h("span", { class: "count" }, tasks.length)),
    body,
  );
  return el;
}

export async function renderBoard(container, ctx) {
  const { project, filters } = ctx.state;
  const query = filterQuery(filters);
  const data = await get(`/api/projects/${project.id}/board${query ? `?${query}` : ""}`);
  clear(container);
  if (!project.stories.length) {
    container.append(h("p", { class: "empty" }, "No stories yet. Open the Stories tab to add your first user story."));
    return;
  }
  container.append(h("div", { class: "board" }, WORK_STATUSES.map((s) => column(ctx, s, data.columns[s] ?? []))));
}
