const { LOG_URL, INSIGHTS_URL } = window.CONFIG;
const TIMEOUT_MS = 40000;
const STARTING = "The service is starting up after being idle. This can take up to a minute.";

const app = document.getElementById("app");

class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function api(base, path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  let response;
  try {
    response = await fetch(base + path, {
      method: options.method || "GET",
      headers: options.body ? { "Content-Type": "application/json" } : undefined,
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });
  } catch {
    throw new ApiError("unreachable", 0, null);
  } finally {
    clearTimeout(timer);
  }
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    throw new ApiError((body && body.error) || `HTTP ${response.status}`, response.status, body);
  }
  return body;
}

function isStarting(err) {
  return err.status === 0 || ([502, 503, 504].includes(err.status) && !(err.body && err.body.error));
}

async function withRetry(fn) {
  try {
    return await fn();
  } catch (err) {
    if (!(err instanceof ApiError) || !isStarting(err)) throw err;
    showMessage(`${STARTING} Retrying…`, false);
    await sleep(5000);
    return fn();
  }
}

function explain(err) {
  if (err instanceof ApiError && isStarting(err)) return { text: `${STARTING} Please try again.`, retry: true };
  if (err instanceof ApiError && err.message === "log_unavailable") {
    return { text: "Hackathon data is unavailable right now because the log service is down.", retry: true };
  }
  return { text: err.message, retry: false };
}

function showMessage(text, retry) {
  const old = document.querySelector(".error.global");
  if (old) old.remove();
  const box = document.createElement("p");
  box.className = "error global";
  box.textContent = text + " ";
  if (retry) {
    const button = document.createElement("a");
    button.className = "btn";
    button.href = location.hash || "#/";
    button.textContent = "Try again";
    button.onclick = (event) => {
      event.preventDefault();
      route();
    };
    box.appendChild(button);
  }
  const target = document.querySelector(".page-head") || app.firstElementChild;
  if (target && target.classList.contains("page-head")) target.after(box);
  else app.prepend(box);
}

function showError(err) {
  const { text, retry } = explain(err);
  showMessage(text, retry);
}

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function dates(h) {
  return `${esc(h.start_date)}${h.end_date !== h.start_date ? ` → ${esc(h.end_date)}` : ""}`;
}

async function viewDashboard() {
  const hackathons = await withRetry(() => api(LOG_URL, "/api/hackathons"));
  const deadlines = hackathons.filter((h) => ["overdue", "urgent", "soon", "later"].includes(h.urgency)).length;
  const attended = hackathons.filter((h) => h.status === "attended").length;
  const applied = hackathons.filter((h) => h.status === "applied").length;

  const cards = hackathons
    .map((h) => {
      let tag = "";
      if (["overdue", "urgent"].includes(h.urgency)) tag = '<span class="badge tag-priority">High priority</span>';
      else if (h.mode === "in_person") tag = '<span class="badge tag-meeting">In person</span>';
      const apply = ["overdue", "urgent", "soon", "later"].includes(h.urgency)
        ? `<span class="urgency ${esc(h.urgency)}">Apply by ${esc(h.application_deadline)}</span>`
        : "";
      return `
      <a class="task-card" href="#/hackathon/${h.id}">
        <div class="task-top">
          <span class="badge ${esc(h.status)}">${esc(h.status)}</span>
          ${tag}
        </div>
        <h3>${esc(h.name)}</h3>
        <div class="task-meta">
          <span>${esc(h.location || "Location TBD")} · ${esc(h.mode.replace("_", " "))}</span>
          <span>${dates(h)}</span>
          ${apply}
        </div>
        <span class="task-action">Open entry</span>
      </a>`;
    })
    .join("");

  app.innerHTML = `
<div class="dash">
  <aside class="dash-left">
    <div class="panel panel-tight">
      <p class="hello">Hi there</p>
      <p class="hello-sub">Your hackathon journal at a glance.</p>
      <div class="hero-metric">
        <span class="metric-value">${hackathons.length}</span>
        <span class="metric-label">entries logged</span>
      </div>
    </div>

    <div class="activity-card">
      <h3>Journal activity</h3>
      <div class="activity-stats">
        <div><strong>${attended}</strong><span>Attended</span></div>
        <div><strong>${applied}</strong><span>Applied</span></div>
        <div><strong>${deadlines}</strong><span>Deadlines</span></div>
      </div>
    </div>
  </aside>

  <section class="dash-center">
    <div class="section-title">
      <h2>Your hackathons</h2>
      <a href="#/new">+ Add</a>
    </div>
    ${
      hackathons.length
        ? `<div class="task-stack">${cards}</div>`
        : `<div class="empty-state">
      <strong>Nothing here yet</strong>
      <p>No hackathons logged. <a href="#/new">Add your first entry</a>.</p>
    </div>`
    }
  </section>

  <aside class="dash-right">
    <div class="side-card">
      <h3>Quick actions</h3>
      <ul class="quick-list">
        <li><a href="#/new">Add a hackathon<span class="chev">›</span></a></li>
        <li><a href="#/insights">View insights<span class="chev">›</span></a></li>
        <li><a href="#/reflection/new">Write a reflection<span class="chev">›</span></a></li>
      </ul>
    </div>

    <div class="side-card">
      <h3>Focus</h3>
      <div class="voice-note">
        <div class="wave" aria-hidden="true">
          <span></span><span></span><span></span><span></span><span></span><span></span><span></span>
        </div>
        <p>${deadlines ? `${deadlines} deadline${deadlines !== 1 ? "s" : ""} need attention` : "All clear, no urgent deadlines"}</p>
      </div>
    </div>
  </aside>
</div>`;
}

function viewNew() {
  app.innerHTML = `
<div class="panel content-panel">
  <div class="page-head">
    <p class="page-kicker">New entry</p>
    <h1>Add a <span class="highlight">hackathon</span></h1>
    <p class="page-lead">Name, place, deadlines, and a few notes — then it’s on your dashboard.</p>
  </div>
  <form class="form-panel" id="new-form">
    <label>Name <input name="name" required></label>
    <label>Location <input name="location"></label>
    <label>Mode
      <select name="mode">
        <option value="in_person">in_person</option>
        <option value="online">online</option>
        <option value="hybrid">hybrid</option>
      </select>
    </label>
    <label>Start date <input type="date" name="start_date" required></label>
    <label>End date <input type="date" name="end_date" required></label>
    <label>Application deadline (optional)
      <input type="date" name="application_deadline">
    </label>
    <label class="check">
      <input type="checkbox" name="travel_funded"> Travel funded
    </label>
    <label>Notes <textarea name="notes" rows="3"></textarea></label>
    <button type="submit">Save entry</button>
  </form>
</div>`;
  document.getElementById("new-form").onsubmit = async (event) => {
    event.preventDefault();
    try {
      const created = await api(LOG_URL, "/api/hackathons", { method: "POST", body: formData(event.target) });
      location.hash = `#/hackathon/${created.id}`;
    } catch (err) {
      showError(err);
    }
  };
}

async function viewDetail(id) {
  const h = await withRetry(() => api(LOG_URL, `/api/hackathons/${id}`));
  const projects =
    h.projects
      .map(
        (p) => `
    <div class="card">
      <strong>${esc(p.name)}</strong> <span class="badge">${esc(p.result)}</span>
      <div class="project-tech">
        ${p.technologies.length ? esc(p.technologies.join(" · ")) : "no technologies listed"}
      </div>
    </div>`
      )
      .join("") || '<p class="muted">No projects yet.</p>';

  app.innerHTML = `
<div class="panel content-panel">
  <div class="page-head">
    <p class="page-kicker">Hackathon entry</p>
    <div class="detail-header">
      <h1>${esc(h.name)}</h1>
      <div class="detail-tags">
        <span class="badge ${esc(h.status)}">${esc(h.status)}</span>
        <span class="muted">${esc(h.mode)}${h.location ? ` · ${esc(h.location)}` : ""}</span>
      </div>
    </div>
  </div>

  <div class="meta-row">
    <div class="meta-chip">
      <span class="chip-label">When</span>
      <strong>${dates(h)}</strong>
    </div>
    <div class="meta-chip">
      <span class="chip-label">Apply by</span>
      <strong>${esc(h.application_deadline || "—")}</strong>
    </div>
    <div class="meta-chip">
      <span class="chip-label">Travel</span>
      <strong>${h.travel_funded ? "Funded" : "Not funded"}</strong>
    </div>
  </div>

  ${h.notes ? `<p class="notes">${esc(h.notes)}</p>` : ""}

  <section class="section-block">
    <h2><span class="label">Status</span>Change status</h2>
    ${
      h.next_statuses.length
        ? `<form class="inline" id="status-form">
      <select name="status">${h.next_statuses.map((s) => `<option value="${esc(s)}">${esc(s)}</option>`).join("")}</select>
      <button type="submit">Update</button>
    </form>`
        : '<p class="muted">This status is final.</p>'
    }
  </section>

  <section class="section-block">
    <h2><span class="label">Crew</span>Teammates</h2>
    ${
      h.teammates.length
        ? `<ul class="team-list">${h.teammates.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>`
        : '<p class="muted">None yet.</p>'
    }
    <form class="inline" id="teammate-form">
      <input name="name" placeholder="Teammate name" required>
      <button type="submit">Add teammate</button>
    </form>
  </section>

  <section class="section-block">
    <h2><span class="label">Builds</span>Projects</h2>
    ${projects}
    ${
      h.status === "attended"
        ? `<form class="form-panel" id="project-form">
      <label>Project name <input name="name" required></label>
      <label>Result
        <select name="result">${h.results.map((r) => `<option value="${esc(r)}">${esc(r)}</option>`).join("")}</select>
      </label>
      <label>Technologies (comma separated) <input name="technologies" placeholder="Python, Flask"></label>
      <button type="submit">Add project</button>
    </form>`
        : '<p class="muted">Projects can be added once the status is "attended".</p>'
    }
  </section>

  <a class="back-link" href="#/">← Back to dashboard</a>
</div>`;

  bind("status-form", `/api/hackathons/${id}/status`);
  bind("teammate-form", `/api/hackathons/${id}/teammates`);
  bind("project-form", `/api/hackathons/${id}/projects`);
}

function bind(formId, path) {
  const form = document.getElementById(formId);
  if (!form) return;
  form.onsubmit = async (event) => {
    event.preventDefault();
    try {
      await api(LOG_URL, path, { method: "POST", body: formData(form) });
      route();
    } catch (err) {
      showError(err);
    }
  };
}

async function viewInsights() {
  let data;
  let logDown = false;
  try {
    data = await withRetry(() => api(INSIGHTS_URL, "/api/summary"));
  } catch (err) {
    if (!(err instanceof ApiError) || err.message !== "log_unavailable") throw err;
    data = err.body;
    logDown = true;
  }
  const stats = data.stats || { win_rate_percent: "–", attended: "–", projects: "–", won: "–", top_technologies: [], top_teammates: [] };

  const reflections =
    data.reflections
      .map(
        (r) => `
  <div class="card reflection-card">
    <strong>${esc(r.hackathon_name || `Hackathon #${r.hackathon_id}`)}</strong>
    ${r.went_well ? `<p class="reflection-line"><span>Went well</span>${esc(r.went_well)}</p>` : ""}
    ${r.went_badly ? `<p class="reflection-line"><span>Went badly</span>${esc(r.went_badly)}</p>` : ""}
    ${r.lesson ? `<p class="reflection-line"><span>Lesson</span>${esc(r.lesson)}</p>` : ""}
  </div>`
      )
      .join("") || '<p class="muted">No reflections yet.</p>';

  app.innerHTML = `
<div class="insights-layout">
  <aside class="insights-hero">
    <div class="score-card">
      <p class="page-kicker">Patterns & prep</p>
      <p class="hello">Your insights</p>
      <p class="hello-sub">Wins, gaps, and checklists after every build.</p>

      <div class="score-ring" aria-hidden="true"></div>
      <div class="hero-metric score-metric">
        <span class="metric-value">${stats.win_rate_percent}%</span>
        <span class="metric-label">win rate</span>
      </div>

      <div class="score-strip">
        <div><strong>${stats.attended}</strong><span>Attended</span></div>
        <div><strong>${stats.projects}</strong><span>Projects</span></div>
        <div><strong>${stats.won}</strong><span>Wins</span></div>
      </div>
    </div>
  </aside>

  <div class="panel insights-main">
  <h2><span class="label">Stack</span>Most used technologies</h2>
  ${
    stats.top_technologies.length
      ? `<ul class="tech-list">${stats.top_technologies.map(([name, count]) => `<li>${esc(name)} <span class="muted">×${count}</span></li>`).join("")}</ul>`
      : '<p class="muted">Add projects to attended hackathons to see this.</p>'
  }

  <h2><span class="label">People</span>Most frequent teammates</h2>
  ${
    stats.top_teammates.length
      ? `<ul class="team-list">${stats.top_teammates.map(([name, count]) => `<li>${esc(name)} <span class="muted">×${count}</span></li>`).join("")}</ul>`
      : '<p class="muted">Add teammates to attended hackathons to see this.</p>'
  }

  <h2><span class="label">Blind spots</span>Technologies you haven't used yet</h2>
  ${
    data.gaps.length
      ? `<div class="gap-pills">${data.gaps.map((g) => `<span class="gap-pill">${esc(g)}</span>`).join("")}</div>`
      : logDown ? '<p class="muted">Unavailable while the log service is down.</p>' : "<p class=\"muted\">You've used them all.</p>"
  }

  <h2><span class="label">Before you go</span>Prep checklists</h2>
  ${
    data.upcoming.length
      ? `<ul class="plain-list">${data.upcoming.map((h) => `<li><a href="#/checklist/${h.id}">${esc(h.name)}</a> <span class="badge ${esc(h.status)}">${esc(h.status)}</span></li>`).join("")}</ul>`
      : '<p class="muted">No upcoming hackathons.</p>'
  }

  <h2><span class="label">After action</span>Reflections</h2>
  <p><a class="btn" href="#/reflection/new">Write a reflection</a></p>
  ${reflections}
  </div>
</div>`;

  if (logDown) {
    showMessage("Stats, gaps and checklists need the log service, which is unavailable right now. Your saved reflections are still shown.", true);
  }
}

async function viewChecklist(id) {
  const data = await withRetry(() => api(INSIGHTS_URL, `/api/checklist/${id}`));
  const h = data.hackathon;
  app.innerHTML = `
<div class="panel content-panel">
  <div class="page-head">
    <p class="page-kicker">Prep list</p>
    <h1>Checklist for <span class="highlight">${esc(h.name)}</span></h1>
    <p class="page-lead">${esc(h.mode)} · tick these off before you ship.</p>
  </div>
  <ul class="check-list">${data.items.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>
  <a class="back-link" href="#/insights">← Back to insights</a>
</div>`;
}

async function viewNewReflection() {
  const hackathons = await withRetry(() => api(LOG_URL, "/api/hackathons"));
  const attended = hackathons.filter((h) => h.status === "attended");
  app.innerHTML = `
<div class="panel content-panel">
  <div class="page-head">
    <p class="page-kicker">After action</p>
    <h1>Write a <span class="highlight">reflection</span></h1>
    <p class="page-lead">Capture the highs, the messes, and the lesson for next time.</p>
  </div>
  ${
    attended.length
      ? `<form class="form-panel" id="reflection-form">
    <label>Hackathon
      <select name="hackathon_id">${attended.map((h) => `<option value="${h.id}">${esc(h.name)}</option>`).join("")}</select>
    </label>
    <label>What went well <textarea name="went_well" rows="3"></textarea></label>
    <label>What went badly <textarea name="went_badly" rows="3"></textarea></label>
    <label>Lesson for next time <textarea name="lesson" rows="3"></textarea></label>
    <button type="submit">Save reflection</button>
  </form>`
      : `<div class="empty-state">
    <strong>Nothing to reflect on yet</strong>
    <p class="muted">You need an attended hackathon first.</p>
  </div>`
  }
</div>`;
  const form = document.getElementById("reflection-form");
  if (form) {
    form.onsubmit = async (event) => {
      event.preventDefault();
      try {
        await api(INSIGHTS_URL, "/api/reflections", { method: "POST", body: formData(form) });
        location.hash = "#/insights";
      } catch (err) {
        showError(err);
      }
    };
  }
}

function setActiveNav(hash) {
  const section = /^#\/(insights|checklist|reflection)/.test(hash) ? "insights" : hash === "#/new" ? "" : "log";
  document.querySelectorAll("[data-nav]").forEach((a) => a.classList.toggle("is-active", a.dataset.nav === section));
}

async function route() {
  const hash = location.hash || "#/";
  setActiveNav(hash);
  const detail = hash.match(/^#\/hackathon\/(\d+)$/);
  const checklist = hash.match(/^#\/checklist\/(\d+)$/);
  try {
    if (detail) await viewDetail(detail[1]);
    else if (checklist) await viewChecklist(checklist[1]);
    else if (hash === "#/new") viewNew();
    else if (hash === "#/insights") await viewInsights();
    else if (hash === "#/reflection/new") await viewNewReflection();
    else await viewDashboard();
  } catch (err) {
    app.innerHTML = "";
    showError(err);
  }
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", route);
route();
