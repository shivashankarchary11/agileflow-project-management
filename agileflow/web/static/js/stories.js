// Stories view: each story with its tasks, filterable, editable and re-orderable.
import { get } from "./api.js";
import { chip, clear, h, todayISO } from "./dom.js";
import {
  WORK_STATUSES,
  deleteStory,
  deleteTask,
  quickPatch,
  storyForm,
  taskForm,
} from "./editors.js";

function filterQuery(filters) {
  const params = new URLSearchParams({ limit: "200" });
  for (const key of ["q", "status", "priority", "assignee_id"]) if (filters[key]) params.set(key, filters[key]);
  return params.toString();
}

function statusSelect(label, current, onChange, disabled) {
  return h(
    "select",
    { "aria-label": label, disabled: disabled ? "" : null, onchange: (event) => onChange(event.target.value) },
    WORK_STATUSES.map((s) => h("option", { value: s, selected: s === current }, s)),
  );
}

function moveButtons(position, last, onMove, label) {
  return [
    h("button", { class: "icon-btn", type: "button", title: `Move ${label} up`, "aria-label": `Move ${label} up`, disabled: position <= 0 ? "" : null, onclick: () => onMove(position - 1) }, "↑"),
    h("button", { class: "icon-btn", type: "button", title: `Move ${label} down`, "aria-label": `Move ${label} down`, disabled: position >= last ? "" : null, onclick: () => onMove(position + 1) }, "↓"),
  ];
}

function taskRow(ctx, story, task, lastPosition) {
  const caps = ctx.state.project.capabilities;
  const overdue = task.due_date && task.status !== "Done" && task.due_date < todayISO();
  return h(
    "li",
    { class: `task-row${task.status === "Done" ? " done" : ""}` },
    statusSelect(
      `Status of ${task.title}`,
      task.status,
      (status) => quickPatch(ctx, `/api/tasks/${task.id}`, { status }, `Task marked ${status}.`),
      !caps["task.edit"],
    ),
    h("span", { class: "task-title" }, task.title),
    task.assigned_to ? chip(`👤 ${task.assigned_to}`) : chip("Unassigned", "muted"),
    task.due_date ? chip(`Due ${task.due_date}`, overdue ? "danger" : "") : null,
    caps["task.edit"]
      ? h(
          "span",
          { class: "row-actions" },
          moveButtons(task.position, lastPosition, (position) => quickPatch(ctx, `/api/tasks/${task.id}/move`, { position }, "Task reordered."), "task"),
          h("button", { class: "btn ghost small", type: "button", onclick: () => taskForm(ctx, story, task) }, "Edit"),
          caps["task.delete"] ? h("button", { class: "btn danger small", type: "button", onclick: () => deleteTask(ctx, task) }, "Delete") : null,
        )
      : null,
  );
}

function storyBlock(ctx, story) {
  const { project } = ctx.state;
  const caps = project.capabilities;
  const lastTask = story.tasks.length - 1;
  const done = story.tasks.filter((t) => t.status === "Done").length;
  return h(
    "article",
    { class: `story prio-${story.priority.toLowerCase()}` },
    h(
      "header",
      { class: "story-head" },
      h("div", {}, h("h3", {}, story.title), story.description ? h("p", { class: "muted" }, story.description) : null),
      h(
        "div",
        { class: "story-tools" },
        chip(story.priority, `prio-${story.priority.toLowerCase()}`),
        chip(`${done}/${story.tasks.length} tasks done`),
        statusSelect(`Status of story ${story.title}`, story.status, (status) => quickPatch(ctx, `/api/stories/${story.id}`, { status }, `Story marked ${status}.`), !caps["story.edit"]),
        caps["story.edit"]
          ? [
              moveButtons(story.position, project.story_count - 1, (position) => quickPatch(ctx, `/api/stories/${story.id}/move`, { position }, "Story reordered."), "story"),
              h("button", { class: "btn ghost small", type: "button", onclick: () => storyForm(ctx, story) }, "Edit"),
            ]
          : null,
        caps["story.delete"] ? h("button", { class: "btn danger small", type: "button", onclick: () => deleteStory(ctx, story) }, "Delete") : null,
      ),
    ),
    story.tasks.length
      ? h("ul", { class: "task-list" }, story.tasks.map((t) => taskRow(ctx, story, t, lastTask)))
      : h("p", { class: "empty small" }, "No tasks yet."),
    caps["task.create"] ? h("button", { class: "btn small", type: "button", onclick: () => taskForm(ctx, story) }, "+ Add task") : null,
  );
}

export async function renderStories(container, ctx) {
  const { project, filters } = ctx.state;
  const data = await get(`/api/projects/${project.id}/stories?${filterQuery(filters)}`);
  clear(container);
  if (project.capabilities["story.create"]) {
    container.append(h("div", { class: "view-actions" }, h("button", { class: "btn primary", type: "button", onclick: () => storyForm(ctx) }, "+ New user story")));
  }
  if (!data.items.length) {
    container.append(h("p", { class: "empty" }, project.story_count ? "No stories match these filters." : "No user stories yet."));
    return;
  }
  // Element.append() does not flatten arrays (it would print "[object HTMLElement]"), so spread them.
  container.append(...data.items.map((s) => storyBlock(ctx, s)));
}
