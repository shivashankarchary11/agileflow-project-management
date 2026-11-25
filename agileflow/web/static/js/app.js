// Dashboard: project list, project header/tabs/filters, and the active view.
import { get, post } from "./api.js";
import { renderBoard } from "./board.js";
import { chip, clear, debounce, h } from "./dom.js";
import { PRIORITIES, WORK_STATUSES, deleteProject, projectForm } from "./editors.js";
import { renderJobs, stopJobPolling } from "./jobs.js";
import { renderStories } from "./stories.js";
import { renderTeam } from "./team.js";
import { notify } from "./toast.js";

const userChip = document.getElementById("userChip");
const state = {
  me: { id: Number(userChip.dataset.userId), role: userChip.dataset.role },
  projects: [],
  projectQuery: "",
  currentId: null,
  project: null,
  view: "board", // board | stories | team | jobs
  filters: { q: "", priority: "", assignee_id: "", status: "" },
};

const $main = document.getElementById("main");
const $list = document.getElementById("projectList");
const ctx = { state, reload, reloadProjects };

// ---------- data loading ----------

async function loadProjects() {
  const params = new URLSearchParams({ limit: "200" });
  if (state.projectQuery) params.set("q", state.projectQuery);
  const data = await get(`/api/projects?${params}`);
  state.projects = data.items;
  renderProjectList();
}

/** Reload the list, then select ``selectId`` (or keep the current project, or the first one). */
async function reloadProjects(selectId) {
  await loadProjects();
  const wanted = selectId ?? state.currentId;
  const id = state.projects.some((p) => p.id === wanted) ? wanted : (state.projects[0]?.id ?? null);
  await selectProject(id);
}

async function selectProject(id) {
  if (id !== state.currentId) state.filters = { q: "", priority: "", assignee_id: "", status: "" };
  state.currentId = id;
  state.project = id ? await get(`/api/projects/${id}`) : null;
  if (state.view === "jobs" && id) state.view = "board";
  renderProjectList();
  renderMain();
}

/** Refresh after any change: project detail, sidebar counts, current view. */
async function reload() {
  if (state.currentId) state.project = await get(`/api/projects/${state.currentId}`);
  await loadProjects();
  renderMain();
}

// ---------- sidebar ----------

function renderProjectList() {
  clear($list);
  if (!state.projects.length) {
    $list.append(h("li", { class: "empty small" }, state.projectQuery ? "No matching projects." : "No projects yet."));
    return;
  }
  for (const p of state.projects) {
    const selected = p.id === state.currentId && state.view !== "jobs";
    $list.append(
      h(
        "li",
        {},
        h(
          "button",
          {
            class: `project-item${selected ? " selected" : ""}`,
            type: "button",
            "aria-current": selected ? "true" : null,
            onclick: async () => {
              state.view = state.view === "jobs" ? "board" : state.view;
              stopJobPolling();
              try {
                await selectProject(p.id);
              } catch (error) {
                notify.error(error.message);
              }
            },
          },
          h("span", { class: "project-name" }, p.name),
          h("span", { class: "muted small" }, `${p.status} · ${p.done_count}/${p.task_count} tasks done`),
        ),
      ),
    );
  }
}

// ---------- main area ----------

function renderMain() {
  if (state.view === "jobs") {
    renderJobs($main).catch((e) => notify.error(e.message));
    return;
  }
  stopJobPolling();
  const project = state.project;
  clear($main);
  if (!project) {
    $main.append(
      h(
        "div",
        { class: "empty big" },
        h("h1", {}, "Welcome to AgileFlow"),
        h(
          "p",
          {},
          state.me.role === "Team Lead"
            ? "Create your first project to start planning stories and tasks."
            : "You are not in any project yet. Ask a Team Lead to add you with your registered email.",
        ),
        state.me.role === "Team Lead"
          ? h("button", { class: "btn primary", type: "button", onclick: () => projectForm(ctx) }, "+ New project")
          : null,
      ),
    );
    return;
  }
  $main.append(projectHeader(project), h("div", { id: "view", class: "view" }));
  renderView();
}

function projectHeader(project) {
  const caps = project.capabilities;
  const pct = project.task_count ? Math.round((project.done_count / project.task_count) * 100) : 0;
  const bar = h("div", { class: "progress-fill" });
  bar.style.width = `${pct}%`;

  const tabs = [
    ["board", "Board"],
    ["stories", "Stories"],
    ["team", `Team (${project.members.length})`],
  ];

  return h(
    "section",
    { class: "project-header" },
    h(
      "div",
      { class: "project-title" },
      h(
        "div",
        {},
        h("h1", {}, project.name),
        project.description ? h("p", { class: "muted" }, project.description) : null,
        h("div", { class: "meta" }, chip(project.status), chip(project.deadline ? `Deadline ${project.deadline}` : "No deadline", "muted"), chip(`You: ${project.my_role}`, "info")),
      ),
      h(
        "div",
        { class: "project-actions" },
        caps["project.edit"] ? h("button", { class: "btn ghost", type: "button", onclick: () => projectForm(ctx, project) }, "Edit project") : null,
        caps["project.delete"] ? h("button", { class: "btn danger", type: "button", onclick: () => deleteProject(ctx, project) }, "Delete") : null,
      ),
    ),
    h(
      "div",
      { class: "stats" },
      stat("Stories", project.story_count),
      stat("Tasks", project.task_count),
      stat("Done", project.done_count),
      h("div", { class: "stat wide" }, h("span", { class: "stat-label" }, `Progress ${pct}%`), h("div", { class: "progress", role: "progressbar", "aria-valuenow": pct, "aria-valuemin": 0, "aria-valuemax": 100 }, bar)),
    ),
    h(
      "div",
      { class: "tabs", role: "tablist" },
      tabs.map(([key, label]) =>
        h(
          "button",
          {
            class: `tab${state.view === key ? " active" : ""}`,
            type: "button",
            role: "tab",
            "aria-selected": String(state.view === key),
            onclick: () => {
              state.view = key;
              renderMain();
            },
          },
          label,
        ),
      ),
    ),
    state.view === "team" ? null : filterBar(project),
  );
}

const stat = (label, value) => h("div", { class: "stat" }, h("span", { class: "stat-value" }, value), h("span", { class: "stat-label" }, label));

function filterBar(project) {
  const f = state.filters;
  const apply = () => renderView();
  const select = (name, label, items) =>
    h(
      "select",
      {
        "aria-label": label,
        onchange: (e) => {
          f[name] = e.target.value;
          apply();
        },
      },
      h("option", { value: "" }, label),
      items.map(([value, text]) => h("option", { value, selected: String(f[name]) === String(value) }, text)),
    );

  return h(
    "div",
    { class: "filters", role: "search" },
    h("input", {
      type: "search",
      placeholder: state.view === "board" ? "Search tasks or stories" : "Search stories and tasks",
      "aria-label": "Search",
      maxlength: 100,
      value: f.q,
      oninput: debounce((e) => {
        f.q = e.target.value.trim();
        apply();
      }),
    }),
    state.view === "stories" ? select("status", "Any status", WORK_STATUSES.map((s) => [s, s])) : null,
    select("priority", "Any priority", PRIORITIES.map((p) => [p, p])),
    select("assignee_id", "Anyone", project.members.map((m) => [m.id, m.name])),
    h(
      "button",
      {
        class: "btn ghost small",
        type: "button",
        onclick: () => {
          state.filters = { q: "", priority: "", assignee_id: "", status: "" };
          renderMain();
        },
      },
      "Clear",
    ),
  );
}

async function renderView() {
  const container = document.getElementById("view");
  if (!container) return;
  try {
    if (state.view === "board") await renderBoard(container, ctx);
    else if (state.view === "stories") await renderStories(container, ctx);
    else renderTeam(container, ctx);
  } catch (error) {
    notify.error(error.message);
    clear(container).append(h("p", { class: "empty" }, "Could not load this view."));
  }
}

// ---------- wiring ----------

document.getElementById("logoutBtn").addEventListener("click", async () => {
  try {
    await post("/auth/logout");
  } finally {
    window.location.href = "/login";
  }
});

document.getElementById("jobsNavBtn").addEventListener("click", () => {
  state.view = "jobs";
  renderProjectList();
  renderMain();
});

const newProjectBtn = document.getElementById("newProjectBtn");
if (state.me.role === "Team Lead") {
  newProjectBtn.hidden = false;
  newProjectBtn.addEventListener("click", () => projectForm(ctx));
}

document.getElementById("projectSearch").addEventListener(
  "input",
  debounce(async (event) => {
    state.projectQuery = event.target.value.trim();
    try {
      await loadProjects();
    } catch (error) {
      notify.error(error.message);
    }
  }),
);

reloadProjects().catch((error) => notify.error(error.message));
