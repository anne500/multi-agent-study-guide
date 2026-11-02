"use strict";
const $ = id => document.getElementById(id);
let token = "", selected = localStorage.getItem("v17-session"), current = null, sending = false, dialogAction = "revise";
const busy = record => ["queued", "running"].includes(record.job_status);
const pretty = value => JSON.stringify(value, null, 2);
function notice(message, error = false) { $("notice").textContent = message; $("notice").hidden = !message; $("notice").classList.toggle("error", error); }
async function api(path, payload) {
  const options = payload === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json", "X-Review-Token": token }, body: JSON.stringify(payload) };
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}
function node(tag, className, text) { const element = document.createElement(tag); if (className) element.className = className; if (text !== undefined) element.textContent = text; return element; }
function choose(id) { selected = id; current = null; id ? localStorage.setItem("v17-session", id) : localStorage.removeItem("v17-session"); $("create-view").hidden = !!id; $("session-view").hidden = !id; if (!id) $("goal").focus(); return refresh(); }
async function refresh() {
  try {
    const items = await api("/api/sessions");
    $("sessions").replaceChildren();
    if (!items.length) $("sessions").append(node("p", "muted", "Your first session starts here."));
    for (const item of items) {
      const button = node("button", `session-item${item.id === selected ? " selected" : ""}`);
      button.append(node("strong", "", item.goal), node("small", "", `${item.offline ? "Offline" : "Ollama"} · ${item.job_status.replaceAll("_", " ")}`));
      button.onclick = () => choose(item.id); $("sessions").append(button);
    }
    if (selected) { const id = selected; const record = await api(`/api/sessions/${id}`); if (id === selected) { current = record; render(record); } }
  } catch (error) { notice(error.message, true); }
}
function taskLabel(task) {
  const a = task.arguments;
  if (task.agent === "calculator") return `Calculate ${a.expression}`;
  if (task.agent === "converter") return `Convert ${a.value} ${a.from_unit} to ${a.to_unit}`;
  return `Search approved documents for: ${a.query}`;
}
function render(record) {
  $("create-view").hidden = true; $("session-view").hidden = false;
  $("session-goal").textContent = record.goal;
  $("session-mode").textContent = `${record.offline ? "OFFLINE PLANNING" : "OLLAMA + LANGGRAPH"} / ${record.job_status.replaceAll("_", " ")}`;
  $("session-id").textContent = `Session ${record.id}`;
  $("export").href = `/api/sessions/${record.id}/export`;
  const snapshot = record.snapshot, state = snapshot?.state, review = snapshot?.review;
  const stages = ["plan_review", "content_review", "final_review"];
  $("gate-steps").replaceChildren(...stages.map((gate, index) => node("div", `gate-step${review?.gate === gate ? " current" : state?.approvals?.[gate] ? " done" : ""}`, `${index + 1}. ${["Plan review", "Content review", "Final review"][index]}`)));
  $("revision").textContent = `Revision ${state?.revision || 0} / 3`;
  $("tasks").replaceChildren();
  for (const task of state?.plan?.tasks || []) {
    const result = state.results[task.task_id], article = node("article", "task"), heading = node("div", "task-heading");
    heading.append(node("h3", "", `${task.task_id} / ${task.agent}`), node("span", "pill", result?.status || "Pending approval"));
    article.append(heading, node("p", "original", `Original request: ${task.instruction}`), node("p", "approved-task", taskLabel(task)), node("pre", "", pretty(task.arguments)));
    if (task.depends_on.length) article.append(node("p", "hint", `Depends on: ${task.depends_on.join(", ")}`));
    if (result) article.append(node("p", `result ${result.status === "failed" ? "failed" : ""}`, result.content));
    $("tasks").append(article);
  }
  if (!state?.plan?.tasks?.length) $("tasks").append(node("p", "hint", "Planning is in progress. The first review gate will appear here."));
  const assessments = state?.assessment || []; $("evidence-panel").hidden = !assessments.length;
  $("assessment").replaceChildren(...assessments.map(text => node("li", "", text)));
  const sources = Object.entries(state?.sources || {}); $("sources-panel").hidden = !sources.length; $("sources").replaceChildren();
  for (const [id, source] of sources) { const entry = node("div", "source"); entry.append(node("strong", "", `[${id}] ${source.title} | ${source.heading}`), node("p", "", source.text), node("p", "hint", source.path)); $("sources").append(entry); }
  $("details").textContent = pretty({ plan: state?.plan, approvals: state?.approvals, audit: state?.audit, trace: state?.trace });
  const metric = snapshot?.metrics || {}; $("metrics").replaceChildren();
  for (const [label, value] of [["Completed tasks", `${metric.tasks_completed || 0} / ${metric.tasks_planned || 0}`], ["Tool attempts", `${state?.executions || 0} / 8`], ["Model attempts", metric.model_attempts || 0], ["Revisions", state?.revision || 0]]) { const row = node("div"); row.append(node("dt", "", label), node("dd", "", String(value))); $("metrics").append(row); }
  const descriptions = { plan_review: ["Check the plan", "Review specialists and task arguments. Approval allows the planned tools to run."], content_review: ["Check the results", "Inspect each result and its evidence. Revise or reject incomplete content."], final_review: ["Give final approval", "Review the evidence questions and confirm this session is ready to finish."] };
  const fallback = busy(record) ? ["Working on your session", record.offline ? "The local workflow is running. This page updates automatically." : "The model may take several minutes to plan. This page updates automatically."] : record.error ? ["Session needs attention", record.error] : [record.job_status === "approved" ? "Session approved" : "Session ended", "Your results and review history are saved locally."];
  const [title, description] = !busy(record) && review && record.job_status === "awaiting_review" ? descriptions[review.gate] : fallback;
  $("gate-heading").textContent = title; $("gate-description").textContent = description; $("review-message").textContent = state?.message || "";
  $("review-actions").hidden = record.job_status !== "awaiting_review" || !review;
  $("recover").hidden = !["error", "recovery_required"].includes(record.job_status);
  for (const id of ["approve", "revise", "reject", "recover"]) $(id).disabled = sending || busy(record);
}
async function sendDecision(action, note = "", plan = null) {
  if (!current?.snapshot?.review || sending) return;
  const id = selected, reviewId = current.snapshot.review.review_id;
  const payload = { request_id: crypto.randomUUID().replaceAll("-", ""), decision: { review_id: reviewId, action, note, plan } };
  sending = true; render(current);
  try { await api(`/api/sessions/${id}/review`, payload); $("decision-dialog").close(); notice("Decision submitted. The saved session will update shortly."); }
  catch (error) { if ($("decision-dialog").open) $("dialog-error").textContent = error.message; else notice(error.message, true); }
  finally { sending = false; await refresh(); }
}
$("create-form").onsubmit = async event => {
  event.preventDefault(); if (sending) return; sending = true; $("create").disabled = true;
  try { const record = await api("/api/sessions", { goal: $("goal").value.trim(), offline: $("offline").checked }); notice("Session created. Review the plan before approving execution."); await choose(record.id); }
  catch (error) { notice(error.message, true); }
  finally { sending = false; $("create").disabled = false; if (current) render(current); }
};
$("offline").onchange = () => { $("mode-help").textContent = $("offline").checked ? "Uses the deterministic planner and approved local tools." : "Uses your local Ollama model to select a plan. A model call may take several minutes."; };
$("new-session").onclick = () => { notice(""); choose(null); };
$("refresh").onclick = refresh;
$("leave").onclick = () => { choose(null); notice("Session saved. Select it in the sidebar to continue from its current review gate."); };
$("approve").onclick = () => sendDecision("approve");
for (const action of ["revise", "reject"]) $(action).onclick = () => { dialogAction = action; $("dialog-title").textContent = action === "revise" ? "Revise the plan" : "Reject this session"; $("dialog-help").textContent = action === "revise" ? "The replacement plan returns to plan review before changed tasks execute." : "This ends the session and records your reason."; $("plan-editor").hidden = action !== "revise"; $("replacement").value = pretty(current.snapshot.state.plan); $("reason").value = ""; $("dialog-error").textContent = ""; $("decision-dialog").showModal(); };
$("cancel-dialog").onclick = () => $("decision-dialog").close();
$("decision-form").onsubmit = event => { event.preventDefault(); if (sending) return; try { const plan = dialogAction === "revise" ? JSON.parse($("replacement").value) : null; if (!$("reason").value.trim()) throw new Error("Please enter a reason."); sendDecision(dialogAction, $("reason").value.trim(), plan); } catch (error) { $("dialog-error").textContent = error.message; } };
$("recover").onclick = async () => { try { await api(`/api/sessions/${selected}/recover`, {}); notice("Saved checkpoint inspected. No workflow nodes were executed."); await refresh(); } catch (error) { notice(error.message, true); } };
async function start() { try { token = (await api("/api/bootstrap")).token; await choose(selected); } catch (error) { notice(error.message, true); } }
start();
setInterval(() => { if (!$("decision-dialog").open && !sending) refresh(); }, 1800);
