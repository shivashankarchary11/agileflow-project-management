// "Reports & jobs" panel: start a report, watch background jobs, download, retry failures.
import { get, post } from "./api.js";
import { chip, clear, h } from "./dom.js";
import { notify } from "./toast.js";

const POLL_MS = 2000;
const MAX_POLLS = 90; // stop after ~3 minutes so we never poll forever
let pollGeneration = 0;

export function stopJobPolling() {
  pollGeneration += 1;
}

const STATUS_KIND = { Queued: "info", Running: "info", Completed: "ok", Failed: "danger" };

async function download(job) {
  try {
    const full = await get(`/api/jobs/${job.id}`);
    const url = URL.createObjectURL(new Blob([full.result], { type: "text/plain" }));
    const link = h("a", { href: url, download: `progress-report-${job.id}.txt` });
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    notify.success("Report downloaded.");
  } catch (error) {
    notify.error(error.message);
  }
}

async function retry(job, container) {
  try {
    await post(`/api/jobs/${job.id}/retry`);
    notify.info("Job re-queued.");
  } catch (error) {
    notify.error(error.message);
  }
  await renderJobs(container);
}

function jobRow(job, container) {
  const waiting = job.status === "Queued" && job.attempts > 0;
  return h(
    "li",
    { class: "job-row" },
    h(
      "div",
      { class: "job-main" },
      h("strong", {}, `#${job.id} ${job.summary}`),
      h("span", { class: "muted small" }, `Created ${new Date(job.created_at).toLocaleString()}`),
      job.error ? h("p", { class: "job-error small" }, `Last error: ${job.error}`) : null,
      waiting ? h("p", { class: "muted small" }, `Will retry at ${new Date(job.next_run_at).toLocaleTimeString()}`) : null,
    ),
    h("div", { class: "job-side" },
      chip(job.status, STATUS_KIND[job.status]),
      chip(`attempt ${job.attempts}/${job.max_attempts}`, "muted"),
      job.status === "Completed" && job.type === "progress_report" && job.has_result
        ? h("button", { class: "btn small", type: "button", onclick: () => download(job) }, "Download")
        : null,
      job.status === "Failed" ? h("button", { class: "btn small", type: "button", onclick: () => retry(job, container) }, "Retry") : null,
    ),
  );
}

const isActive = (job) => job.status === "Queued" || job.status === "Running";
const signature = (items) => items.map((j) => `${j.id}:${j.status}:${j.attempts}`).join("|");

export async function renderJobs(container, pollCount = 0) {
  const generation = ++pollGeneration;
  const data = await get("/api/jobs?limit=30");
  if (generation !== pollGeneration) return;

  container.dataset.signature = signature(data.items);
  clear(container);
  container.append(
    h("header", { class: "view-head" },
      h("h1", {}, "Reports & jobs"),
      h("button", {
        class: "btn primary",
        type: "button",
        onclick: async () => {
          try {
            await post("/api/reports");
            notify.info("Report started. It runs in the background.");
          } catch (error) {
            notify.error(error.message);
          }
          await renderJobs(container);
        },
      }, "Generate progress report"),
    ),
    h("p", { class: "muted" }, "Reports and email notifications run in the background. Failed jobs retry automatically with a growing delay; you can also retry them by hand."),
    data.items.length
      ? h("ul", { class: "job-list" }, data.items.map((j) => jobRow(j, container)))
      : h("p", { class: "empty" }, "No jobs yet. Generate a report to see one."),
  );

  if (data.items.some(isActive)) schedulePoll(container, generation, pollCount + 1);
}

function schedulePoll(container, generation, count) {
  if (count > MAX_POLLS) return; // give up quietly; the user can refresh the panel
  setTimeout(async () => {
    if (generation !== pollGeneration) return; // user left the panel or it was re-rendered
    try {
      const data = await get("/api/jobs?limit=30");
      if (generation !== pollGeneration) return;
      if (signature(data.items) !== container.dataset.signature) {
        const wasActive = container.querySelector(".chip.info") !== null;
        await renderJobs(container, count);
        if (wasActive && !data.items.some(isActive)) notify.success("Background jobs finished.");
        return;
      }
    } catch {
      /* transient error: try again on the next tick */
    }
    schedulePoll(container, generation, count + 1);
  }, POLL_MS);
}
