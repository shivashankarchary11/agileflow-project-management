let projects = [], selectedProject = null, editingProject = null, currentUser = null;
const $ = id => document.getElementById(id);
async function api(url, options={}) {
  const res = await fetch(url, {headers:{"Content-Type":"application/json"}, ...options});
  const data = await res.json().catch(()=>({}));
  if(!res.ok) throw new Error(data.error || "Request failed");
  return data;
}
function notify(msg){$("notice").textContent=msg;$("notice").classList.remove("hidden");setTimeout(()=>$("notice").classList.add("hidden"),3200)}
async function load(){try{currentUser=await api("/api/me");$("newProjectBtn").classList.toggle("hidden",currentUser.role!=="Team Lead");projects=await api("/api/projects");renderProjects();renderStats();if(selectedProject){selectedProject=projects.find(p=>p.id===selectedProject.id)||null;renderDetail()}}catch(e){notify(e.message)}}
function renderStats(){let stories=projects.flatMap(p=>p.stories),tasks=stories.flatMap(s=>s.tasks),done=tasks.filter(t=>t.status==="Done").length;$("projectCount").textContent=projects.length;$("storyCount").textContent=stories.length;$("completedCount").textContent=done;$("progress").textContent=(tasks.length?Math.round(done/tasks.length*100):0)+"%"}
function renderProjects(){let q=$("search").value.toLowerCase();let list=projects.filter(p=>p.name.toLowerCase().includes(q));$("projectGrid").innerHTML=list.length?list.map(p=>{let ts=p.stories.flatMap(s=>s.tasks),done=ts.filter(t=>t.status==="Done").length,pct=ts.length?Math.round(done/ts.length*100):0;return `<article class="project-card" onclick="selectProject(${p.id})"><div class="card-top"><span class="pill">${esc(p.status)}</span><span class="muted">${p.deadline||"No deadline"}</span></div><h3>${esc(p.name)}</h3><p>${esc(p.description||"No description added.")}</p><div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div><div class="card-foot"><span>${p.stories.length} stories · ${ts.length} tasks</span><strong>${pct}%</strong></div></article>`}).join(""):'<div class="empty">No projects yet. Create your first project to get started.</div>'}
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function openProjectModal(p=null){editingProject=p;$("modalTitle").textContent=p?"Edit project":"New project";$("pName").value=p?.name||"";$("pDescription").value=p?.description||"";$("pStatus").value=p?.status||"Active";$("pDeadline").value=p?.deadline||"";$("modal").classList.remove("hidden")}
function closeModal(){$("modal").classList.add("hidden")}
$("projectForm").addEventListener("submit",async e=>{e.preventDefault();let body={name:$("pName").value,description:$("pDescription").value,status:$("pStatus").value,deadline:$("pDeadline").value};try{if(editingProject)await api(`/api/projects/${editingProject.id}`,{method:"PATCH",body:JSON.stringify(body)});else await api("/api/projects",{method:"POST",body:JSON.stringify(body)});closeModal();selectedProject=null;await load();notify("Project saved successfully.")}catch(err){notify(err.message)}});
async function selectProject(id){selectedProject=projects.find(p=>p.id===id);renderDetail();$("detail").scrollIntoView({behavior:"smooth",block:"start"})}
function renderDetail(){let p=selectedProject;if(!p){$("detail").classList.add("hidden");return}const lead=p.my_role==="Team Lead",writer=lead||p.my_role==="Member";$("detail").classList.remove("hidden");$("detail").innerHTML=`<div class="detail-head"><div><p class="eyebrow">PROJECT DETAILS · ${esc(p.my_role)}</p><h2>${esc(p.name)}</h2><p class="muted">${esc(p.description)}</p><p class="muted">Team: ${p.members.map(m=>esc(m.name)+" ("+esc(m.role)+")").join(", ")}</p></div><div class="actions">${lead?`<button class="small-btn" onclick="openProjectModal(projects.find(x=>x.id===${p.id}))">Edit project</button><button class="small-btn" onclick="manageMembers(${p.id})">＋ Add teammate</button><button class="small-btn" onclick="deleteProject(${p.id})">Delete</button>`:""}${writer?`<button class="primary" onclick="addStory(${p.id})">＋ Add story</button>`:""}</div></div><div>${p.stories.map(s=>`<div class="story"><div class="story-head"><div><h3>${esc(s.title)}</h3><p class="muted">${esc(s.description)} · ${esc(s.priority)} priority</p></div><div class="actions"><select aria-label="Story status" ${writer?`onchange="updateStory(${s.id},this.value)"`:"disabled"}><option ${s.status==="To Do"?"selected":""}>To Do</option><option ${s.status==="In Progress"?"selected":""}>In Progress</option><option ${s.status==="Done"?"selected":""}>Done</option></select>${writer?`<button class="small-btn" onclick="addTask(${s.id})">＋ Task</button>`:""}${lead?`<button class="small-btn" onclick="deleteStory(${s.id})">Delete</button>`:""}</div></div>${s.tasks.length?s.tasks.map(t=>`<div class="task"><span class="task-title">${esc(t.title)} <span class="muted">· ${esc(t.assigned_to||"Unassigned")}</span></span><select aria-label="Task status" ${writer?`onchange="updateTask(${t.id},this.value)"`:"disabled"}><option ${t.status==="To Do"?"selected":""}>To Do</option><option ${t.status==="In Progress"?"selected":""}>In Progress</option><option ${t.status==="Done"?"selected":""}>Done</option></select><span class="muted">${esc(t.due_date||"")}</span>${lead?`<button class="small-btn" onclick="deleteTask(${t.id})">Delete</button>`:""}</div>`).join(""):'<p class="muted">No tasks yet. Add a task to break down this story.</p>'}</div>`).join("")||'<div class="empty">No user stories yet. Add a story to this project.</div>'}</div>`}

async function refreshSelected(){await load()}
let entrySubmitAction = null;
function openEntryModal(config){
  $("entryModalTitle").textContent = config.title;
  $("entryModalHint").textContent = config.hint || "";
  $("entrySubmit").textContent = config.submitLabel || "Save";
  $("entryFields").innerHTML = config.fields.map(field => {
    const label = esc(field.label);
    const name = esc(field.name);
    const required = field.required ? "required" : "";
    const value = esc(field.value || "");
    if(field.type === "textarea"){
      return `<label>${label}<textarea name="${name}" rows="3" ${required} placeholder="${esc(field.placeholder || "")}">${value}</textarea></label>`;
    }
    if(field.type === "select"){
      return `<label>${label}<select name="${name}" ${required}>${field.options.map(option => {const optionValue=typeof option==="object"?option.value:option;const optionLabel=typeof option==="object"?option.label:option;return `<option value="${esc(optionValue)}" ${String(optionValue) === String(field.value ?? "") ? "selected" : ""}>${esc(optionLabel)}</option>`}).join("")}</select></label>`;
    }
    return `<label>${label}<input name="${name}" type="${field.type || "text"}" value="${value}" ${required} maxlength="${field.maxlength || 160}" placeholder="${esc(field.placeholder || "")}"></label>`;
  }).join("");
  entrySubmitAction = config.onSubmit;
  $("entryModal").classList.remove("hidden");
  const first = $("entryFields").querySelector("input, textarea, select");
  if(first) first.focus();
}
function closeEntryModal(){
  $("entryModal").classList.add("hidden");
  $("entryForm").reset();
  entrySubmitAction = null;
}
$("entryForm").addEventListener("submit", async event => {
  event.preventDefault();
  if(!entrySubmitAction) return;
  const values = Object.fromEntries(new FormData(event.currentTarget).entries());
  const submit = $("entrySubmit");
  submit.disabled = true;
  submit.textContent = "Saving…";
  try {
    await entrySubmitAction(values);
    closeEntryModal();
  } catch(error) {
    notify(error.message);
  } finally {
    submit.disabled = false;
    submit.textContent = "Save";
  }
});
$("entryModal").addEventListener("click", event => {
  if(event.target === $("entryModal")) closeEntryModal();
});
document.addEventListener("keydown", event => {
  if(event.key === "Escape" && !$("entryModal").classList.contains("hidden")) closeEntryModal();
});
async function manageMembers(projectId){
  openEntryModal({title:"Add teammate to project",hint:"The teammate must already have an AgileFlow account. They will see this project after signing in.",submitLabel:"Add teammate",fields:[{name:"email",label:"Teammate email",type:"email",placeholder:"teammate@example.com",required:true},{name:"role",label:"Project role",type:"select",value:"Member",options:["Member","Viewer"]}],onSubmit:async values=>{await api(`/api/projects/${projectId}/members`,{method:"POST",body:JSON.stringify(values)});await refreshSelected();notify("Teammate added to project.")}});
}
async function addStory(id){
  openEntryModal({
    title:"Create user story",
    hint:"Describe a feature or requirement for this project.",
    submitLabel:"Create story",
    fields:[
      {name:"title",label:"Story title",placeholder:"e.g. Customer can reset their password",required:true,maxlength:160},
      {name:"description",label:"Description",type:"textarea",placeholder:"Add details about what the user needs…"},
      {name:"priority",label:"Priority",type:"select",value:"Medium",options:["Low","Medium","High"]}
    ],
    onSubmit:async values=>{
      await api(`/api/projects/${id}/stories`,{method:"POST",body:JSON.stringify(values)});
      await refreshSelected();
      notify("User story created.");
    }
  });
}
async function addTask(id){
  openEntryModal({
    title:"Create task",
    hint:"Break this user story into an actionable task.",
    submitLabel:"Create task",
    fields:[
      {name:"title",label:"Task title",placeholder:"e.g. Build the password reset form",required:true,maxlength:160},
      {name:"assigned_to_id",label:"Assigned to",type:"select",value:"",options:[{value:"",label:"Unassigned"},...(selectedProject?.members||[]).map(m=>({value:String(m.id),label:m.name}))]},
      {name:"due_date",label:"Due date",type:"date"}
    ],
    onSubmit:async values=>{
      await api(`/api/stories/${id}/tasks`,{method:"POST",body:JSON.stringify(values)});
      await refreshSelected();
      notify("Task created.");
    }
  });
}
async function updateStory(id,status){try{await api(`/api/stories/${id}`,{method:"PATCH",body:JSON.stringify({status})});await refreshSelected()}catch(e){notify(e.message)}}
async function updateTask(id,status){try{await api(`/api/tasks/${id}`,{method:"PATCH",body:JSON.stringify({status})});await refreshSelected()}catch(e){notify(e.message)}}
async function deleteTask(id){if(!confirm("Delete this task?"))return;try{await api(`/api/tasks/${id}`,{method:"DELETE"});await refreshSelected()}catch(e){notify(e.message)}}
async function deleteStory(id){if(!confirm("Delete this story and all its tasks?"))return;try{await api(`/api/stories/${id}`,{method:"DELETE"});await refreshSelected()}catch(e){notify(e.message)}}
async function deleteProject(id){if(!confirm("Delete this project, its stories and tasks?"))return;try{await api(`/api/projects/${id}`,{method:"DELETE"});selectedProject=null;await load();notify("Project deleted.")}catch(e){notify(e.message)}}
async function generateReport(){try{let job=await api("/api/reports",{method:"POST"});notify("Report started. Checking status…");pollJob(job.job_id)}catch(e){notify(e.message)}}
async function pollJob(id){try{let job=await api(`/api/jobs/${id}`);if(job.status==="Completed"){let blob=new Blob([job.result],{type:"text/plain"}),a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=`project-report-${id}.txt`;a.click();URL.revokeObjectURL(a.href);notify("Report generated and downloaded.")}else if(job.status==="Failed"){notify("Report failed: "+job.error)}else{setTimeout(()=>pollJob(id),1000)}}catch(e){notify(e.message)}}
load();

async function logout(){
  try{await fetch('/auth/logout',{method:'POST'});window.location.href='/login';}
  catch(error){notify('Unable to log out. Please try again.');}
}
