// Create/edit forms for projects, stories, tasks and teammates.
import { del, patch, post } from "./api.js";
import { confirmAction, openForm } from "./forms.js";
import { notify } from "./toast.js";

export const WORK_STATUSES = ["To Do", "In Progress", "Done"];
export const PRIORITIES = ["Low", "Medium", "High"];
export const PROJECT_STATUSES = ["Active", "On Hold", "Completed"];

const options = (list) => list.map((value) => ({ value, label: value }));

// ---------- projects ----------

export function projectForm(ctx, project = null) {
  openForm({
    title: project ? "Edit project" : "New project",
    submitLabel: project ? "Save changes" : "Create project",
    values: project ?? { status: "Active" },
    fields: [
      { name: "name", label: "Name", required: true, maxlength: 120 },
      { name: "description", label: "Description", type: "textarea", maxlength: 2000 },
      { name: "status", label: "Status", type: "select", options: options(PROJECT_STATUSES) },
      { name: "deadline", label: "Deadline", type: "date" },
    ],
    onSubmit: async (v) => {
      const body = { name: v.name, description: v.description, status: v.status, deadline: v.deadline || null };
      if (project) {
        await patch(`/api/projects/${project.id}`, body);
        notify.success("Project updated.");
        await ctx.reload();
      } else {
        const created = await post("/api/projects", body);
        notify.success("Project created.");
        await ctx.reloadProjects(created.id);
      }
    },
  });
}

export async function deleteProject(ctx, project) {
  if (!confirmAction(`Delete "${project.name}" with all its stories and tasks? This cannot be undone.`)) return;
  try {
    await del(`/api/projects/${project.id}`);
    notify.success("Project deleted.");
    await ctx.reloadProjects(null);
  } catch (error) {
    notify.error(error.message);
  }
}

// ---------- teammates ----------

export function memberForm(ctx) {
  const project = ctx.state.project;
  openForm({
    title: "Add teammate",
    submitLabel: "Add",
    values: { role: "Member" },
    fields: [
      { name: "email", label: "Registered email", type: "email", required: true, maxlength: 160 },
      {
        name: "role",
        label: "Role in this project",
        type: "select",
        options: [
          { value: "Member", label: "Member (can edit)" },
          { value: "Viewer", label: "Viewer (read only)" },
        ],
      },
    ],
    onSubmit: async (v) => {
      await post(`/api/projects/${project.id}/members`, { email: v.email, role: v.role });
      notify.success("Teammate added. They were notified by email.");
      await ctx.reload();
    },
  });
}

export async function removeMember(ctx, member) {
  if (!confirmAction(`Remove ${member.name} from this project? Their tasks become unassigned.`)) return;
  try {
    await del(`/api/projects/${ctx.state.project.id}/members/${member.id}`);
    notify.success(`${member.name} removed.`);
    await ctx.reload();
  } catch (error) {
    notify.error(error.message);
  }
}

// ---------- stories ----------

export function storyForm(ctx, story = null) {
  const project = ctx.state.project;
  openForm({
    title: story ? "Edit user story" : "New user story",
    submitLabel: story ? "Save changes" : "Add story",
    values: story ?? { priority: "Medium", status: "To Do" },
    fields: [
      { name: "title", label: "Title", required: true, maxlength: 160, placeholder: "As a user, I want…" },
      { name: "description", label: "Description", type: "textarea", maxlength: 2000 },
      { name: "priority", label: "Priority", type: "select", options: options(PRIORITIES) },
      { name: "status", label: "Status", type: "select", options: options(WORK_STATUSES) },
    ],
    onSubmit: async (v) => {
      if (story) await patch(`/api/stories/${story.id}`, v);
      else await post(`/api/projects/${project.id}/stories`, v);
      notify.success(story ? "Story updated." : "Story added.");
      await ctx.reload();
    },
  });
}

export async function deleteStory(ctx, story) {
  if (!confirmAction(`Delete the story "${story.title}" and all its tasks?`)) return;
  try {
    await del(`/api/stories/${story.id}`);
    notify.success("Story deleted.");
    await ctx.reload();
  } catch (error) {
    notify.error(error.message);
  }
}

// ---------- tasks ----------

function assigneeOptions(project) {
  return [{ value: "", label: "Unassigned" }, ...project.members.map((m) => ({ value: m.id, label: `${m.name} (${m.role})` }))];
}

/** Create a task under ``story``, or edit ``task`` (editing also lets you move it to another story). */
export function taskForm(ctx, story, task = null) {
  const project = ctx.state.project;
  const fields = [
    { name: "title", label: "Title", required: true, maxlength: 160 },
    { name: "description", label: "Description", type: "textarea", maxlength: 2000 },
    { name: "status", label: "Status", type: "select", options: options(WORK_STATUSES) },
    { name: "due_date", label: "Due date", type: "date" },
    { name: "assigned_to_id", label: "Assignee", type: "select", options: assigneeOptions(project) },
  ];
  if (task) {
    fields.push({
      name: "story_id",
      label: "Story",
      type: "select",
      options: project.stories.map((s) => ({ value: s.id, label: s.title })),
    });
  }
  openForm({
    title: task ? "Edit task" : `New task in “${story.title}”`,
    submitLabel: task ? "Save changes" : "Add task",
    values: task
      ? { ...task, assigned_to_id: task.assigned_to_id ?? "", due_date: task.due_date ?? "" }
      : { status: "To Do", assigned_to_id: "" },
    fields,
    onSubmit: async (v) => {
      const body = {
        title: v.title,
        description: v.description,
        status: v.status,
        due_date: v.due_date || null,
        assigned_to_id: v.assigned_to_id ? Number(v.assigned_to_id) : null,
      };
      if (task) {
        await patch(`/api/tasks/${task.id}`, body);
        if (Number(v.story_id) !== task.story_id) {
          await patch(`/api/tasks/${task.id}/move`, { story_id: Number(v.story_id) });
        }
        notify.success("Task updated.");
      } else {
        await post(`/api/stories/${story.id}/tasks`, body);
        notify.success("Task added.");
      }
      await ctx.reload();
    },
  });
}

export async function deleteTask(ctx, task) {
  if (!confirmAction(`Delete the task "${task.title}"?`)) return;
  try {
    await del(`/api/tasks/${task.id}`);
    notify.success("Task deleted.");
    await ctx.reload();
  } catch (error) {
    notify.error(error.message);
  }
}

// ---------- quick changes ----------

export async function quickPatch(ctx, url, body, message) {
  try {
    await patch(url, body);
    notify.success(message);
  } catch (error) {
    notify.error(error.message);
  }
  await ctx.reload();
}
