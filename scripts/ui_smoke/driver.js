// In-page UI test driver. Injected into the app's HTML pages by scripts/ui_smoke/run.mjs; reports to /__test__/report.
// Not part of the application: it only exists while the smoke test runs.
(() => {
  const rpt = (obj) => fetch("/__test__/report", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(obj), keepalive: true }).catch(() => {});
  const check = (label, ok, extra = "") => rpt({ type: "check", label, ok: !!ok, extra: String(extra ?? "") });

  // ---- capture every error the page produces (JS exceptions, rejections, CSP violations, console.error) ----
  window.addEventListener("error", (e) => rpt({ type: "error", text: "EXCEPTION: " + e.message + " @" + (e.filename || "") }));
  window.addEventListener("unhandledrejection", (e) => rpt({ type: "error", text: "REJECTION: " + (e.reason?.message ?? e.reason) }));
  document.addEventListener("securitypolicyviolation", (e) => rpt({ type: "error", text: "CSP: " + e.violatedDirective + " blocked " + e.blockedURI }));
  const origError = console.error;
  console.error = (...a) => { rpt({ type: "error", text: "CONSOLE: " + a.join(" ") }); origError.apply(console, a); };

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => [...document.querySelectorAll(s)];
  async function waitFor(fn, ms = 8000) {
    const end = Date.now() + ms;
    while (Date.now() < end) { try { if (fn()) return true; } catch {} await sleep(80); }
    return false;
  }
  const fill = (sel, value) => {
    const el = $(sel); if (!el) throw new Error("no field " + sel);
    el.value = value; el.dispatchEvent(new Event("input", { bubbles: true })); el.dispatchEvent(new Event("change", { bubbles: true }));
  };
  const click = (sel) => { const el = $(sel); if (!el) throw new Error("no element " + sel); el.click(); };
  const clickText = (sel, text) => {
    const el = $$(sel).find((e) => e.textContent.trim().includes(text)); if (!el) throw new Error("no " + sel + " containing '" + text + "'"); el.click();
  };
  const toast = (needle) => waitFor(() => $$(".toast").some((t) => t.textContent.includes(needle)));
  const submitDialog = () => click("#formDialog button[type=submit]");
  const phase = () => localStorage.getItem("af_phase") || "start";
  const setPhase = (p) => localStorage.setItem("af_phase", p);

  async function registerFlow() {
    check("register page shows the role select", !!$("select[name=role]"));
    fill("input[name=name]", "Lena Lead"); fill("input[name=email]", "lena@example.com");
    fill("input[name=password]", "password-123"); fill("select[name=role]", "Team Lead");
    setPhase("dashboard");
    click("#authForm button[type=submit]");
  }

  async function dashboardFlow() {
    check("registration redirected to the dashboard", location.pathname === "/");
    check("user chip shows name and role", await waitFor(() => $("#userChip")?.textContent.includes("Lena Lead") && $("#userChip").textContent.includes("Team Lead")));
    check("Team Lead sees the '+ New' project button", !$("#newProjectBtn").hidden);
    check("empty state shown before any project", await waitFor(() => $("#main h1")?.textContent.includes("Welcome")));

    // ---- project ----
    click("#newProjectBtn");
    check("project dialog opens", await waitFor(() => $("#formDialog").open));
    fill("#formDialog input[name=name]", "Apollo"); fill("#formDialog textarea[name=description]", "Moon mission"); fill("#formDialog input[name=deadline]", "2031-05-05");
    submitDialog();
    check("toast: Project created", await toast("Project created"));
    check("project header renders", await waitFor(() => $(".project-header h1")?.textContent === "Apollo"));
    check("deadline chip shows the date", $(".project-header .meta")?.textContent.includes("2031-05-05"));
    check("project appears in the sidebar", $("#projectList")?.textContent.includes("Apollo"));

    // ---- story + tasks ----
    clickText(".tab", "Stories");
    await waitFor(() => $(".view-actions button"));
    clickText(".view-actions button", "New user story");
    fill("#formDialog input[name=title]", "As a user I can sign in"); fill("#formDialog select[name=priority]", "High");
    submitDialog();
    check("toast: Story added", await toast("Story added"));
    check("story block rendered", await waitFor(() => $(".story h3")?.textContent === "As a user I can sign in"));
    for (const title of ["Build login form", "Write API"]) {
      clickText(".story button", "Add task");
      fill("#formDialog input[name=title]", title);
      submitDialog();
      check("toast: Task added (" + title + ")", await toast("Task added"));
      await waitFor(() => $$(".task-title").some((t) => t.textContent === title));
    }
    check("two tasks listed under the story", $$(".task-row").length === 2);

    // ---- board + drag and drop ----
    clickText(".tab", "Board");
    check("board shows 2 cards in To Do", await waitFor(() => $$('.column[data-status="To Do"] .card').length === 2));
    const card = $$(".card").find((c) => c.textContent.includes("Build login form"));
    const col = $('.column[data-status="In Progress"]');
    const dt = new DataTransfer();
    card.dispatchEvent(new DragEvent("dragstart", { dataTransfer: dt, bubbles: true }));
    col.dispatchEvent(new DragEvent("dragover", { dataTransfer: dt, bubbles: true, cancelable: true }));
    col.dispatchEvent(new DragEvent("drop", { dataTransfer: dt, bubbles: true, cancelable: true }));
    check("toast after drag: Moved to In Progress", await toast("Moved to In Progress"));
    check("card now sits in the In Progress column", await waitFor(() => $$('.column[data-status="In Progress"] .card').some((c) => c.textContent.includes("Build login form"))));
    const sel = $('.column[data-status="In Progress"] .card select');
    sel.value = "Done"; sel.dispatchEvent(new Event("change", { bubbles: true }));
    check("select fallback moves the card to Done", await waitFor(() => $$('.column[data-status="Done"] .card').length === 1));
    check("progress shows 50%", await waitFor(() => $(".stats")?.textContent.includes("Progress 50%")));

    // ---- filters / search ----
    fill(".filters input[type=search]", "zzz-nothing");
    check("search with no match empties the board", await waitFor(() => $$(".card").length === 0));
    clickText(".filters button", "Clear");
    check("clearing the filter restores the cards", await waitFor(() => $$(".card").length === 2));
    fill(".filters input[type=search]", "api");
    check("search 'api' finds only the 'Write API' card", await waitFor(() => $$(".card").length === 1 && $(".card h4").textContent === "Write API"));
    clickText(".filters button", "Clear");
    await waitFor(() => $$(".card").length === 2);

    // ---- edit forms ----
    clickText(".tab", "Stories");
    await waitFor(() => $(".story"));
    clickText(".story-tools button", "Edit");
    fill("#formDialog input[name=title]", "Sign-in story (renamed)");
    submitDialog();
    check("toast: Story updated", await toast("Story updated"));
    check("story title changed in the UI", await waitFor(() => $(".story h3")?.textContent === "Sign-in story (renamed)"));
    clickText(".task-row button", "Edit");
    fill("#formDialog input[name=due_date]", "2031-06-01");
    submitDialog();
    check("toast: Task updated", await toast("Task updated"));
    check("task due date shown", await waitFor(() => $(".task-row")?.textContent.includes("Due 2031-06-01")));

    // reorder buttons
    const firstTitle = () => $$(".task-title")[0]?.textContent;
    const before = firstTitle();
    const downBtn = $(".task-row button[aria-label='Move task down']");
    downBtn.click();
    check("toast: Task reordered", await toast("Task reordered"));
    check("task order changed after clicking down", await waitFor(() => firstTitle() && firstTitle() !== before));
    await waitFor(() => $$(".task-row").length === 2 && $(".task-row button.btn.ghost"));

    // ---- validation: empty title is blocked inline ----
    clickText(".task-row button", "Edit");
    fill("#formDialog input[name=title]", "");
    submitDialog();
    check("empty title blocked with an inline message", await waitFor(() => !$("#formDialog .form-error").hidden));
    click("#formDialog .btn.ghost");

    // ---- add a task through a server-side validation error (bad assignee can't be chosen in UI; use long title) ----
    // (server-side validation toast path) - 161 chars title
    clickText(".story button", "Add task");
    fill("#formDialog input[name=title]", "x".repeat(161));
    submitDialog();
    check("server validation error shown inline and as an error toast", (await waitFor(() => !$("#formDialog .form-error").hidden)) && (await toast("at most 160")));
    click("#formDialog .btn.ghost");

    // ---- XSS: hostile project name must render as text, not execute ----
    click("#newProjectBtn");
    fill("#formDialog input[name=name]", "<img src=x onerror=window.__pwned=1>");
    submitDialog();
    await waitFor(() => $(".project-header h1")?.textContent.includes("<img"));
    check("hostile name shown literally as text", $(".project-header h1")?.textContent === "<img src=x onerror=window.__pwned=1>");
    await sleep(400);
    check("no injected script ran (window.__pwned undefined)", typeof window.__pwned === "undefined");
    check("no <img> element was created from user text", !$(".project-header h1 img") && !$("#projectList img"));

    // ---- team view ----
    clickText(".tab", "Team");
    check("team view lists the lead", await waitFor(() => $(".table")?.textContent.includes("Lena Lead")));
    check("team view offers 'Add teammate' to the lead", !!$$(".view-actions button").find((b) => b.textContent.includes("Add teammate")));

    // ---- add-teammate error path, edit project, delete project ----
    clickText(".view-actions button", "Add teammate");
    fill("#formDialog input[name=email]", "nobody@example.com");
    submitDialog();
    check("add-teammate with an unknown email shows an inline error", await waitFor(() => !$("#formDialog .form-error").hidden && $("#formDialog .form-error").textContent.includes("No registered user")));
    check("...and an error toast", await toast("No registered user"));
    click("#formDialog .btn.ghost");

    window.confirm = () => true; // headless: auto-accept the delete confirmation
    clickText(".project-actions button", "Delete");
    check("toast: Project deleted", await toast("Project deleted"));
    check("deleted project is gone and Apollo is selected", await waitFor(() => $(".project-header h1")?.textContent === "Apollo" && !$("#projectList").textContent.includes("<img")));

    clickText(".project-actions button", "Edit project");
    fill("#formDialog input[name=name]", "Apollo 11");
    fill("#formDialog select[name=status]", "On Hold");
    submitDialog();
    check("toast: Project updated", await toast("Project updated"));
    check("project name and status updated in the header", await waitFor(() => $(".project-header h1")?.textContent === "Apollo 11" && $(".project-header .meta")?.textContent.includes("On Hold")));

    // ---- reports & jobs ----
    click("#jobsNavBtn");
    await waitFor(() => $("#main h1")?.textContent === "Reports & jobs");
    clickText("#main button", "Generate progress report");
    check("toast: report started", await toast("Report started"));
    check("job completes in the background (chip turns Completed)", await waitFor(() => $(".job-row .chip.ok")?.textContent === "Completed", 20000));
    check("Download button appears for the finished report", await waitFor(() => $$(".job-row button").some((b) => b.textContent === "Download")));

    // ---- log out ----
    setPhase("loggedout");
    click("#logoutBtn");
  }

  (async () => {
    try {
      if (document.readyState === "loading") await new Promise((r) => document.addEventListener("DOMContentLoaded", r));
      const p = phase(), path = location.pathname;
      if (path === "/register" && p === "start") await registerFlow();
      else if (path === "/" && p === "dashboard") await dashboardFlow();
      else if (path === "/login" && p === "loggedout") { check("logout returned to the login page", true); setPhase("verify"); location.href = "/"; }
      else if (path === "/login" && p === "verify") { check("dashboard is protected after logout (redirected to /login)", true); rpt({ type: "done" }); }
      else rpt({ type: "unexpected", text: "phase=" + p + " path=" + path });
    } catch (err) {
      rpt({ type: "fatal", text: err.message + "\n" + (err.stack ?? "") });
      rpt({ type: "done" });
    }
  })();
})();
