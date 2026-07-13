// API_BASE comes from config.js, loaded before this file.

// Everything below is in-memory only, per CLAUDE.md Phase 1: nothing persisted,
// all lost on refresh.
const state = {
  resumeText: null,
  initiatives: [], // each gets _story, _qaPairs, _studyByConcept, _visited attached as generated
  resumeQA: null,
  view: "upload", // upload | dashboard | detail | resume-qa
  currentIndex: null,
  currentTab: "study",
  selectedConcept: null,
};

const sidebarEl = document.getElementById("sidebar");
const mainEl = document.getElementById("main-content");

function escapeHTML(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

async function postJSON(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Request to ${path} failed (${res.status})`);
  }
  return res.json();
}

// ---------- Navigation ----------

function goHome() {
  state.view = "dashboard";
  render();
}

function goToInitiative(index, tab = "study") {
  state.currentIndex = index;
  state.currentTab = tab;
  state.selectedConcept = null;
  state.initiatives[index]._visited = true;
  state.view = "detail";
  render();
}

function goToResumeQA() {
  state.view = "resume-qa";
  render();
}

function startOver() {
  state.resumeText = null;
  state.initiatives = [];
  state.resumeQA = null;
  state.view = "upload";
  state.currentIndex = null;
  state.currentTab = "study";
  state.selectedConcept = null;
  render();
}

// ---------- Render: sidebar ----------

function renderSidebar() {
  if (state.view === "upload") {
    sidebarEl.innerHTML = `
      <div>
        <h1 class="brand-title">Interview Prep</h1>
        <p class="brand-sub">Upload a resume to get started</p>
      </div>
    `;
    return;
  }

  const total = state.initiatives.length;
  const visited = state.initiatives.filter((i) => i._visited).length;
  const pct = total ? Math.round((visited / total) * 100) : 0;

  const byCompany = new Map();
  state.initiatives.forEach((initiative, index) => {
    const key = initiative.company || "Other";
    if (!byCompany.has(key)) byCompany.set(key, []);
    byCompany.get(key).push({ initiative, index });
  });

  const groups = [...byCompany.entries()]
    .map(([company, items]) => {
      const timeframe = items[0].initiative.timeframe;
      const label = timeframe ? `${company} · ${timeframe}` : company;
      const links = items
        .map(
          ({ initiative, index }) => `
          <button class="nav-item ${state.view === "detail" && state.currentIndex === index ? "active" : ""}"
                  data-action="nav-initiative" data-index="${index}">
            ${escapeHTML(initiative.title)}
          </button>`
        )
        .join("");
      return `<div class="nav-group"><p class="nav-group-label">${escapeHTML(label)}</p>${links}</div>`;
    })
    .join("");

  sidebarEl.innerHTML = `
    <div>
      <h1 class="brand-title">Interview Prep</h1>
      <p class="brand-sub">${total} initiative${total === 1 ? "" : "s"} found</p>
    </div>

    <div class="progress-block">
      <p class="progress-label">${visited} / ${total} reviewed</p>
      <div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div>
    </div>

    <button class="nav-item home ${state.view === "dashboard" ? "active" : ""}" data-action="nav-home">
      Dashboard
    </button>

    ${groups}

    <button class="nav-item resume-qa ${state.view === "resume-qa" ? "active" : ""}" data-action="nav-resume-qa">
      Resume-wide Q&amp;A
    </button>

    <div class="sidebar-spacer"></div>
    <button class="start-over-link" data-action="start-over">Start over</button>
  `;
}

// ---------- Render: upload view ----------

function renderUploadView() {
  mainEl.innerHTML = `
    <h2 class="view-heading">Upload your resume</h2>
    <p class="view-subheading">We'll extract your projects and the concepts worth studying for each.</p>

    <form id="upload-form" class="upload-card">
      <label for="resume-file">Resume PDF</label>
      <input type="file" id="resume-file" accept="application/pdf" required />
      <button type="submit" id="upload-btn" class="btn btn-primary">Upload &amp; analyze</button>
    </form>
    <p id="upload-status" class="status"></p>
  `;

  const form = document.getElementById("upload-form");
  const btn = document.getElementById("upload-btn");
  const statusEl = document.getElementById("upload-status");
  const fileInput = document.getElementById("resume-file");

  const setStatus = (msg, isError = false) => {
    statusEl.textContent = msg;
    statusEl.classList.toggle("error", isError);
  };

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const file = fileInput.files[0];
    if (!file) return;

    btn.disabled = true;
    try {
      setStatus("Uploading and extracting text...");
      const formData = new FormData();
      formData.append("file", file);
      const uploadRes = await fetch(`${API_BASE}/upload`, { method: "POST", body: formData });
      if (!uploadRes.ok) {
        const detail = await uploadRes.json().catch(() => ({}));
        throw new Error(detail.detail || "Upload failed");
      }
      const { text } = await uploadRes.json();
      state.resumeText = text;

      setStatus("Analyzing initiatives with Groq...");
      const extracted = await postJSON("/extract", { text });
      state.initiatives = extracted.initiatives.map((i) => ({
        ...i,
        _story: null,
        _qaPairs: null,
        _studyByConcept: {},
        _visited: false,
      }));

      state.view = "dashboard";
      render();
    } catch (err) {
      setStatus(err.message, true);
      btn.disabled = false;
    }
  });
}

// ---------- Render: dashboard view ----------

function renderDashboardView() {
  const cards = state.initiatives
    .map((initiative, index) => {
      const meta = [initiative.company, initiative.timeframe].filter(Boolean).join(" · ");
      const tags = (initiative.tags || [])
        .map((tag) => `<span class="pill">${escapeHTML(tag)}</span>`)
        .join("");
      return `
        <button class="card" data-action="nav-initiative" data-index="${index}">
          <p class="card-eyebrow">Initiative ${index + 1}</p>
          <h3 class="card-title">${escapeHTML(initiative.title)}</h3>
          <p class="card-meta">${escapeHTML(meta)}</p>
          <p class="card-description">${escapeHTML(initiative.description)}</p>
          <div class="pill-row">${tags}</div>
        </button>
      `;
    })
    .join("");

  mainEl.innerHTML = `
    <h2 class="view-heading">Dashboard</h2>
    <p class="view-subheading">Click an initiative to study its concepts, build your story, and prep Q&amp;A.</p>

    <div class="info-box">
      Each initiative has two prep modes plus per-concept study: <strong>Study</strong>
      (a 6-dimension deep dive on each concept), <strong>Story</strong> (how to narrate the
      project out loud), and <strong>Q&amp;A</strong> (likely interview questions with strong
      answers). Nothing here is saved — it's regenerated live from Groq each session.
    </div>

    <div class="grid">${cards}</div>
  `;
}

// ---------- Render: detail view ----------

function renderDetailView() {
  const initiative = state.initiatives[state.currentIndex];
  const meta = [initiative.company, initiative.timeframe].filter(Boolean).join(" · ");
  const tags = (initiative.tags || [])
    .map((tag) => `<span class="pill">${escapeHTML(tag)}</span>`)
    .join("");

  mainEl.innerHTML = `
    <div class="detail-header">
      <button class="back-link" data-action="nav-home">&larr; Back to dashboard</button>
      <h2 class="detail-title">${escapeHTML(initiative.title)}</h2>
      <p class="detail-meta">${escapeHTML(meta)}</p>
      <p class="detail-description">${escapeHTML(initiative.description)}</p>
      <div class="pill-row">${tags}</div>
    </div>

    <div class="tab-bar">
      <button class="tab-btn ${state.currentTab === "study" ? "active" : ""}" data-action="select-tab" data-tab="study">Study</button>
      <button class="tab-btn ${state.currentTab === "story" ? "active" : ""}" data-action="select-tab" data-tab="story">Story</button>
      <button class="tab-btn ${state.currentTab === "qa" ? "active" : ""}" data-action="select-tab" data-tab="qa">Q&amp;A</button>
    </div>

    <div class="tab-panel" id="tab-panel"></div>
  `;

  renderTabPanel(initiative);
}

function renderTabPanel(initiative) {
  const panel = document.getElementById("tab-panel");

  if (state.currentTab === "study") {
    const concepts = initiative.concepts || [];
    const pills = concepts
      .map(
        (c) => `<button class="pill clickable ${state.selectedConcept === c ? "selected" : ""}"
                        data-action="select-concept" data-concept="${escapeHTML(c)}">${escapeHTML(c)}</button>`
      )
      .join("");

    let body = `<div class="empty-panel">Pick a concept above to see its study deep dive.</div>`;
    if (state.selectedConcept) {
      const cached = initiative._studyByConcept[state.selectedConcept];
      if (cached === "loading") {
        body = `<div class="empty-panel">Generating study notes for &quot;${escapeHTML(state.selectedConcept)}&quot;...</div>`;
      } else if (cached === "error") {
        body = `<div class="empty-panel">Failed to generate study notes. Try again.</div>`;
      } else if (cached) {
        body = renderStudyContent(cached);
      }
    }

    panel.innerHTML = `<div class="pill-row">${pills}</div><div class="content-box">${body}</div>`;
    return;
  }

  if (state.currentTab === "story") {
    if (!initiative._story) {
      panel.innerHTML = `
        <div class="empty-panel">
          No story generated yet for this session.
          <button class="btn btn-primary" data-action="generate-story">Generate story</button>
        </div>`;
    } else if (initiative._story === "loading") {
      panel.innerHTML = `<div class="empty-panel">Generating story...</div>`;
    } else if (initiative._story === "error") {
      panel.innerHTML = `<div class="empty-panel">Failed to generate story. <button class="btn btn-ghost" data-action="generate-story">Retry</button></div>`;
    } else {
      const s = initiative._story;
      const sections = [
        ["Objective", s.objective],
        ["Data", s.data],
        ["Methodology", s.methodology],
        ["Results", s.results],
        ["Challenges", s.challenges],
        ["Future scope", s.future_scope],
      ];
      panel.innerHTML = `
        <div class="content-box">
          ${sections.map(([label, text]) => `<h4>${label}</h4><p>${escapeHTML(text)}</p>`).join("")}
        </div>
        <button class="btn btn-ghost" data-action="generate-story">Regenerate</button>
      `;
    }
    return;
  }

  if (state.currentTab === "qa") {
    if (!initiative._qaPairs) {
      panel.innerHTML = `
        <div class="empty-panel">
          No Q&amp;A generated yet for this session.
          <button class="btn btn-primary" data-action="generate-qa">Generate Q&amp;A</button>
        </div>`;
    } else if (initiative._qaPairs === "loading") {
      panel.innerHTML = `<div class="empty-panel">Generating Q&amp;A...</div>`;
    } else if (initiative._qaPairs === "error") {
      panel.innerHTML = `<div class="empty-panel">Failed to generate Q&amp;A. <button class="btn btn-ghost" data-action="generate-qa">Retry</button></div>`;
    } else {
      panel.innerHTML = `
        <div class="content-box">${renderQAPairs(initiative._qaPairs)}</div>
        <button class="btn btn-ghost" data-action="generate-qa">Regenerate</button>
      `;
    }
  }
}

function renderStudyContent(data) {
  const sections = [
    ["Explanation", data.explanation],
    ["Why it matters", data.why_it_matters],
    ["How it works", data.how_it_works],
    ["Trade-offs", data.trade_offs],
    ["Common pitfalls", data.common_pitfalls],
    ["Interview angle", data.interview_angle],
  ];
  return sections.map(([label, text]) => `<h4>${label}</h4><p>${escapeHTML(text)}</p>`).join("");
}

function renderQAPairs(pairs) {
  return pairs
    .map(
      (pair) => `
      <div class="qa-item">
        <div class="q">${escapeHTML(pair.question)}</div>
        <div class="a">${escapeHTML(pair.answer)}</div>
      </div>`
    )
    .join("");
}

// ---------- Render: resume Q&A view ----------

function renderResumeQAView() {
  let body;
  if (!state.resumeQA) {
    body = `
      <div class="empty-panel">
        No resume-wide Q&amp;A generated yet for this session.
        <button class="btn btn-primary" data-action="generate-resume-qa">Generate</button>
      </div>`;
  } else if (state.resumeQA === "loading") {
    body = `<div class="empty-panel">Generating resume-wide Q&amp;A...</div>`;
  } else if (state.resumeQA === "error") {
    body = `<div class="empty-panel">Failed to generate. <button class="btn btn-ghost" data-action="generate-resume-qa">Retry</button></div>`;
  } else {
    body = `
      <div class="content-box">${renderQAPairs(state.resumeQA)}</div>
      <button class="btn btn-ghost" data-action="generate-resume-qa">Regenerate</button>
    `;
  }

  mainEl.innerHTML = `
    <h2 class="view-heading">Resume-wide Q&amp;A</h2>
    <p class="view-subheading">Technical questions that span multiple projects, based on your full resume text.</p>
    ${body}
  `;
}

// ---------- Top-level render ----------

function render() {
  renderSidebar();
  if (state.view === "upload") renderUploadView();
  else if (state.view === "dashboard") renderDashboardView();
  else if (state.view === "detail") renderDetailView();
  else if (state.view === "resume-qa") renderResumeQAView();
}

// ---------- Delegated actions ----------

document.getElementById("app").addEventListener("click", async (e) => {
  const target = e.target.closest("[data-action]");
  if (!target) return;
  const action = target.dataset.action;

  if (action === "nav-home") return goHome();
  if (action === "nav-resume-qa") return goToResumeQA();
  if (action === "start-over") return startOver();
  if (action === "nav-initiative") return goToInitiative(Number(target.dataset.index));

  if (action === "select-tab") {
    state.currentTab = target.dataset.tab;
    state.selectedConcept = null;
    return render();
  }

  if (action === "select-concept") {
    const initiative = state.initiatives[state.currentIndex];
    const concept = target.dataset.concept;
    state.selectedConcept = concept;
    if (!initiative._studyByConcept[concept] || initiative._studyByConcept[concept] === "error") {
      initiative._studyByConcept[concept] = "loading";
      render();
      try {
        const data = await postJSON("/study", { concept, context: initiative.description });
        initiative._studyByConcept[concept] = data;
      } catch {
        initiative._studyByConcept[concept] = "error";
      }
      render();
    } else {
      render();
    }
    return;
  }

  if (action === "generate-story") {
    const initiative = state.initiatives[state.currentIndex];
    initiative._story = "loading";
    render();
    try {
      initiative._story = await postJSON("/story", initiative);
    } catch {
      initiative._story = "error";
    }
    return render();
  }

  if (action === "generate-qa") {
    const initiative = state.initiatives[state.currentIndex];
    initiative._qaPairs = "loading";
    render();
    try {
      const data = await postJSON("/project-qa", initiative);
      initiative._qaPairs = data.qa_pairs;
    } catch {
      initiative._qaPairs = "error";
    }
    return render();
  }

  if (action === "generate-resume-qa") {
    state.resumeQA = "loading";
    render();
    try {
      const data = await postJSON("/resume-qa", { resume_text: state.resumeText });
      state.resumeQA = data.qa_pairs;
    } catch {
      state.resumeQA = "error";
    }
    return render();
  }
});

render();
