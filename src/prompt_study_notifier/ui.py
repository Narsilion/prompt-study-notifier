from __future__ import annotations

import json

from prompt_study_notifier.schemas import SettingsRecord, TemplateRecord


def _shared_styles() -> str:
    return """
      :root {
        --bg-top: #f6efe1;
        --bg-bottom: #ddeaf1;
        --surface: rgba(255, 253, 248, 0.84);
        --ink: #18222f;
        --muted: #61717f;
        --accent: #bb5a34;
        --accent-strong: #8e3f20;
        --line: rgba(24, 34, 47, 0.09);
        --shadow: 0 24px 70px rgba(24, 34, 47, 0.14);
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        color: var(--ink);
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
        background:
          radial-gradient(circle at top left, rgba(255,255,255,0.75), transparent 30%),
          radial-gradient(circle at right, rgba(187,90,52,0.16), transparent 28%),
          linear-gradient(160deg, var(--bg-top), var(--bg-bottom));
      }
      .page {
        width: min(1240px, calc(100vw - 28px));
        margin: 18px auto 42px;
      }
      .nav {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        padding: 14px 18px;
        border-radius: 22px;
        border: 1px solid var(--line);
        background: rgba(255,255,255,0.58);
        backdrop-filter: blur(10px);
        box-shadow: var(--shadow);
      }
      .nav-brand {
        font-weight: 700;
        letter-spacing: 0.04em;
      }
      .nav-links {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
      }
      .nav-link {
        display: inline-flex;
        align-items: center;
        padding: 9px 14px;
        border-radius: 999px;
        color: var(--ink);
        text-decoration: none;
        background: rgba(24,34,47,0.06);
      }
      .nav-link[data-active="true"] {
        background: linear-gradient(135deg, var(--accent), var(--accent-strong));
        color: white;
      }
      .hero {
        margin-top: 18px;
        padding: 26px;
        border-radius: 28px;
        background:
          linear-gradient(135deg, rgba(24,34,47,0.96), rgba(44,63,81,0.92)),
          linear-gradient(135deg, rgba(187,90,52,0.46), rgba(255,255,255,0.08));
        color: #f8f3ec;
        box-shadow: var(--shadow);
      }
      .hero h1 {
        margin: 10px 0 8px;
        font-family: "Palatino", "Book Antiqua", serif;
        font-size: clamp(40px, 6vw, 68px);
        line-height: 0.95;
      }
      .hero p { margin: 0; max-width: 820px; color: rgba(248,243,236,0.82); }
      .hero-actions { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 18px; }
      .chip {
        display: inline-flex;
        align-items: center;
        padding: 7px 12px;
        border-radius: 999px;
        border: 1px solid rgba(255,255,255,0.14);
        background: rgba(255,255,255,0.08);
        font-size: 14px;
      }
      .layout {
        display: grid;
        gap: 18px;
        margin-top: 18px;
      }
      .layout-dashboard {
        grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.75fr);
      }
      .layout-dashboard.schedules-collapsed {
        grid-template-columns: minmax(0, 1fr) 200px;
      }
      .layout-templates {
        grid-template-columns: minmax(340px, 0.95fr) minmax(0, 1.05fr);
      }
      .column {
        display: grid;
        gap: 18px;
        align-content: start;
      }
      .panel {
        padding: 20px;
        border-radius: 24px;
        border: 1px solid var(--line);
        background: var(--surface);
        backdrop-filter: blur(10px);
        box-shadow: var(--shadow);
      }
      .panel h2 {
        margin: 0 0 14px;
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        color: var(--muted);
      }
      .result-title {
        margin: 0 0 8px;
        font-size: clamp(32px, 4vw, 52px);
        line-height: 1.02;
        font-family: "Palatino", "Book Antiqua", serif;
      }
      .summary { margin: 0; color: var(--muted); font-size: 18px; line-height: 1.6; }
      .result-meta {
        margin: 6px 0 10px;
        font-size: 13px;
        color: var(--muted);
        letter-spacing: 0.02em;
      }
      .cards { display: grid; gap: 14px; margin-top: 16px; }
      .card {
        padding: 18px;
        border-radius: 20px;
        background: rgba(255,255,255,0.68);
        border: 1px solid var(--line);
      }
      .card-header,
      .inline-row {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
      }
      .card h3 { margin: 0 0 8px; font-size: 28px; }
      .card p { margin: 6px 0; line-height: 1.55; }
      .inline-row p {
        margin: 0;
        flex: 1;
      }
      .card-meta { margin-top: 10px; }
      .pronounce-button {
        padding: 8px 14px;
        background: rgba(24,34,47,0.08);
        color: var(--ink);
        flex-shrink: 0;
      }
      .pronounce-button:disabled {
        cursor: not-allowed;
        opacity: 0.6;
      }
      .muted { color: var(--muted); }
      .list { display: grid; gap: 10px; }
      .list-item {
        padding: 14px;
        border-radius: 18px;
        background: rgba(255,255,255,0.62);
        border: 1px solid var(--line);
      }
      .field {
        display: grid;
        gap: 6px;
      }
      .field-heading {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }
      .field-label {
        font-size: 13px;
        font-weight: 600;
        color: var(--muted);
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }
      .help-link {
        appearance: none;
        border: 0;
        padding: 0;
        background: transparent;
        color: var(--accent-strong);
        font: inherit;
        font-size: 13px;
        font-weight: 600;
        text-decoration: underline;
        cursor: pointer;
      }
      form { display: grid; gap: 10px; }
      input, textarea, select {
        width: 100%;
        padding: 12px 14px;
        border-radius: 14px;
        border: 1px solid rgba(24,34,47,0.12);
        font: inherit;
        background: rgba(255,255,255,0.92);
      }
      textarea { min-height: 96px; resize: vertical; }
      button {
        appearance: none;
        border: 0;
        border-radius: 999px;
        padding: 12px 16px;
        background: linear-gradient(135deg, var(--accent), var(--accent-strong));
        color: white;
        font: inherit;
        font-weight: 600;
        cursor: pointer;
      }
      button.secondary {
        background: rgba(24,34,47,0.08);
        color: var(--ink);
      }
      .actions { display: flex; gap: 10px; flex-wrap: wrap; }
      .two-up {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
      }
      pre {
        margin: 0;
        padding: 14px;
        border-radius: 16px;
        background: rgba(24,34,47,0.06);
        overflow: auto;
        white-space: pre-wrap;
      }
      .status {
        display: inline-flex;
        padding: 4px 10px;
        border-radius: 999px;
        background: rgba(24,34,47,0.08);
        font-size: 13px;
      }
      .run-progress {
        display: grid;
        gap: 8px;
        margin-top: 12px;
      }
      .run-progress-label {
        font-size: 13px;
        color: var(--muted);
      }
      .run-progress-bar {
        position: relative;
        height: 6px;
        overflow: hidden;
        border-radius: 999px;
        background: rgba(24,34,47,0.1);
      }
      .run-progress-bar::after {
        content: "";
        position: absolute;
        inset: 0;
        width: 38%;
        border-radius: inherit;
        background: linear-gradient(90deg, var(--accent), var(--accent-strong));
        animation: run-progress-slide 1.1s ease-in-out infinite;
      }
      @keyframes run-progress-slide {
        0% { transform: translateX(-115%); }
        100% { transform: translateX(280%); }
      }
      .page-title {
        margin: 0;
        font-family: "Palatino", "Book Antiqua", serif;
        font-size: clamp(34px, 5vw, 50px);
        line-height: 1;
      }
      .page-intro {
        margin: 10px 0 0;
        color: var(--muted);
        line-height: 1.6;
      }
      dialog.help-dialog {
        width: min(560px, calc(100vw - 24px));
        border: 1px solid var(--line);
        border-radius: 24px;
        padding: 0;
        background: rgba(255, 253, 248, 0.98);
        box-shadow: var(--shadow);
      }
      dialog.help-dialog::backdrop {
        background: rgba(24, 34, 47, 0.4);
      }
      .help-dialog-body {
        padding: 22px;
        display: grid;
        gap: 14px;
      }
      .help-dialog-body h3 {
        margin: 0;
        font-size: 22px;
        font-family: "Palatino", "Book Antiqua", serif;
      }
      .help-dialog-body p {
        margin: 0;
        line-height: 1.6;
      }
      @media (max-width: 980px) {
        .layout-dashboard,
        .layout-templates { grid-template-columns: 1fr; }
        .two-up { grid-template-columns: 1fr; }
        .nav { flex-direction: column; align-items: stretch; }
        .card-header,
        .inline-row { flex-direction: column; }
      }
    """


def _shell(title: str, navigation_active: str, body: str, *, settings_json: str) -> str:
    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <style>
{_shared_styles()}
    </style>
  </head>
  <body>
    <main class="page">
      <nav class="nav">
        <div class="nav-brand">Prompt Study Notifier</div>
        <div class="nav-links">
          <a class="nav-link" data-active="{str(navigation_active == 'dashboard').lower()}" href="/">Dashboard</a>
          <a class="nav-link" data-active="{str(navigation_active == 'templates').lower()}" href="/templates">Templates</a>
        </div>
      </nav>
      <script>
        const settings = __SETTINGS_JSON__;
        const helpContent = {{
          scheduleVariables: {{
            title: "Schedule Variables",
            body: "Use this when the selected template contains placeholders such as topic or difficulty. Enter a JSON object whose keys match the variable names expected by the template. Leave it empty only when the template does not use variables.",
          }},
          systemPrompt: {{
            title: "System Prompt",
            body: "This sets the tutor's stable behavior. Put long-lived instructions here: tone, accuracy rules, output discipline, and what the assistant should optimize for across every run of the template.",
          }},
          userPromptTemplate: {{
            title: "User Prompt Template",
            body: "This defines the actual exercise to generate. Put the task here, including placeholders such as topic or case_name. Change this field when you want different kinds of results from the same template.",
          }},
          templateVariables: {{
            title: "Variable Definitions",
            body: "Describe the variables the template can use. Enter a JSON array of objects, for example items with name, label, and example fields. These definitions help you remember which values to supply later in a schedule.",
          }},
          scheduleActive: {{
            title: "Active",
            body: "Active controls whether the scheduler is allowed to run this schedule automatically. When it is off, the schedule stays saved but no automatic runs are triggered until you turn it back on or use Run Now manually.",
          }},
        }};
      </script>
      <script>

      function escapeHtml(value) {{
        return String(value ?? "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;");
      }}

      function parseJsonField(text, fallback) {{
        if (!text.trim()) {{
          return fallback;
        }}
        return JSON.parse(text);
      }}

      function validateCronExpression(value) {{
        const normalized = String(value ?? "").trim().replaceAll(/\\s+/g, " ");
        if (!normalized) {{
          return "Cron Expression is required.";
        }}
        const fields = normalized.split(" ");
        if (fields.length !== 5) {{
          return "Cron Expression must have 5 space-separated fields, for example */30 * * * *";
        }}
        return null;
      }}

      function formatDateTime(value, timeZone) {{
        if (!value) {{
          return "-";
        }}
        try {{
          return new Intl.DateTimeFormat(undefined, {{
            dateStyle: "medium",
            timeStyle: "short",
            timeZone,
          }}).format(new Date(value));
        }} catch {{
          return value;
        }}
      }}

      function formatGenerationDuration(value) {{
        const seconds = Number(value);
        if (!Number.isFinite(seconds) || seconds < 0) {{
          return "";
        }}
        if (seconds < 1) {{
          return `${{Math.round(seconds * 1000)}} ms`;
        }}
        if (seconds < 10) {{
          return `${{seconds.toFixed(1)}} s`;
        }}
        if (seconds < 60) {{
          return `${{Math.round(seconds)}} s`;
        }}
        const minutes = Math.floor(seconds / 60);
        const remainder = Math.round(seconds % 60);
        return `${{minutes}}m ${{remainder}}s`;
      }}

      async function fetchJson(path, options) {{
        const response = await fetch(path, {{
          headers: {{ "Content-Type": "application/json" }},
          ...options,
        }});
        if (!response.ok) {{
          const text = await response.text();
          throw new Error(text || `Request failed: ${{response.status}}`);
        }}
        return response.json();
      }}

      function showHelp(topic) {{
        const dialog = document.getElementById("helpDialog");
        const title = document.getElementById("helpDialogTitle");
        const body = document.getElementById("helpDialogBody");
        const entry = helpContent[topic];
        if (!dialog || !title || !body || !entry) {{
          return;
        }}
        title.textContent = entry.title;
        body.textContent = entry.body;
        if (typeof dialog.showModal === "function") {{
          dialog.showModal();
        }}
      }}

      function speechSupported() {{
        return "speechSynthesis" in window && typeof SpeechSynthesisUtterance !== "undefined";
      }}

      function updatePronounceButtons(root) {{
        if (!root) {{
          return;
        }}
        const supported = speechSupported();
        root.querySelectorAll("[data-pronounce-text]").forEach((button) => {{
          const text = String(button.dataset.pronounceText || "").trim();
          button.disabled = !supported || !text;
          if (!supported) {{
            button.title = "Pronunciation is not supported in this browser.";
          }} else if (!text) {{
            button.title = "Nothing to pronounce.";
          }} else {{
            button.title = "";
          }}
        }});
      }}

      function speakFromButton(button) {{
        if (!button || button.disabled) {{
          return;
        }}
        const text = String(button.dataset.pronounceText || "").trim();
        if (!text || !speechSupported()) {{
          return;
        }}
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 0.95;
        window.speechSynthesis.speak(utterance);
      }}
      </script>
{body}
      <dialog id="helpDialog" class="help-dialog">
        <div class="help-dialog-body">
          <h3 id="helpDialogTitle"></h3>
          <p id="helpDialogBody"></p>
          <div class="actions">
            <button class="secondary" type="button" onclick="document.getElementById('helpDialog').close()">Close</button>
          </div>
        </div>
      </dialog>
    </main>
  </body>
</html>
"""
    return html.replace("__SETTINGS_JSON__", settings_json)


def _template_list_markup(templates: list[TemplateRecord]) -> str:
    if not templates:
        return '<p class="muted">No templates yet.</p>'
    cards: list[str] = []
    for template in templates:
        cards.append(
            f"""
            <article class="list-item">
              <div class="actions">
                <p><strong>{_escape_html(template.name)}</strong></p>
                <button class="secondary" type="button" data-edit-template-id="{template.id}">Edit</button>
              </div>
              <p class="muted">{_escape_html(template.description or "")}</p>
              <p class="muted">Variables: {_escape_html(", ".join(template.variable_names) or "none")}</p>
            </article>
            """
        )
    return "".join(cards)


def _escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _model_options_markup(settings: SettingsRecord) -> str:
    return "".join(
        f'<option value="{_escape_html(model)}"{(" selected" if model == settings.active_model else "")}>{_escape_html(model)}</option>'
        for model in settings.available_models
    )


def render_dashboard(settings: SettingsRecord) -> str:
    settings_json = json.dumps(settings.model_dump())
    model_options_markup = _model_options_markup(settings)
    body = """
      <section class="hero">
        <div class="chip">Live Prompt Study Dashboard</div>
        <h1>Prompt Study Notifier</h1>
        <p>Schedule reusable prompts, generate structured study sessions, and let the open browser tab refresh itself when new material arrives.</p>
        <div class="hero-actions">
          <button id="enableNotificationsButton" class="secondary" type="button">Enable Browser Notifications</button>
          <span class="chip" id="connectionStatus">Connecting…</span>
          <span class="chip" id="runtimeInfo"></span>
        </div>
        <form id="modelForm" style="margin-top:16px; display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
          <select id="modelInput" name="active_model">__MODEL_OPTIONS__</select>
          <button type="submit">Save Model</button>
        </form>
      </section>

      <section class="layout layout-dashboard" id="dashboardLayout">
        <div class="column">
          <section class="panel">
            <h2>Latest Result</h2>
            <div id="latestResult">
              <p class="muted">No generated session yet.</p>
            </div>
          </section>

          <section class="panel">
            <div class="actions" style="justify-content:space-between; align-items:center; margin-bottom:14px;">
              <h2 style="margin:0;">Recent History</h2>
              <div class="actions">
                <button id="toggleHistoryButton" class="secondary" type="button">Collapse</button>
                <button id="clearHistoryButton" class="secondary" type="button">Clear History</button>
              </div>
            </div>
            <div id="historyPanelContent">
              <div id="historyList" class="list">
                <p class="muted">No sessions yet.</p>
              </div>
            </div>
          </section>
        </div>

        <div class="column" id="schedulesColumn">
          <section class="panel" id="schedulesPanel">
            <div class="actions" style="justify-content:space-between; align-items:center; margin-bottom:14px;">
              <h2 style="margin:0;">Schedules</h2>
              <button id="toggleSchedulesButton" class="secondary" type="button">Collapse</button>
            </div>
            <div id="schedulesPanelContent">
              <div class="actions" style="justify-content:space-between; align-items:center; margin-bottom:14px;">
                <h2 style="margin:0;">Schedule Editor</h2>
                <button id="toggleScheduleEditorButton" class="secondary" type="button">Collapse</button>
              </div>
              <div id="scheduleEditorContent">
                <form id="scheduleForm">
                  <input type="hidden" name="schedule_id">
                  <label class="field">
                    <span class="field-label">Schedule Name</span>
                    <input name="name" placeholder="Schedule name" required>
                  </label>
                  <label class="field">
                    <span class="field-label">Template</span>
                    <select name="template_id" required></select>
                  </label>
                  <label class="field">
                    <span class="field-label">Cron Expression</span>
                    <input name="cron_expr" placeholder="Cron expression, e.g. */30 * * * *" required>
                  </label>
                  <label class="field">
                    <span class="field-label">Timezone</span>
                    <input name="timezone" value="Europe/Belgrade" required>
                  </label>
                  <label class="field">
                    <span class="field-heading">
                      <span class="field-label">Variables</span>
                      <button class="help-link" type="button" onclick="showHelp('scheduleVariables')">How to use this</button>
                    </span>
                    <textarea name="variables" placeholder='Variables JSON, e.g. {"target_language":"Spanish","topic":"restaurant conversations","focus_area":"polite requests","difficulty":"A2"}'></textarea>
                  </label>
                  <div class="two-up">
                    <label>
                      <input type="checkbox" name="is_active" checked> Active
                      <button class="help-link" type="button" onclick="showHelp('scheduleActive')">What is this?</button>
                    </label>
                    <label><input type="checkbox" name="notification_enabled" checked> Browser notification</label>
                  </div>
                  <div class="actions">
                    <button id="saveScheduleButton" type="submit">Save Schedule</button>
                    <button id="cancelScheduleEditButton" class="secondary" type="button">Cancel Edit</button>
                  </div>
                </form>
              </div>
              <div id="schedulesList" class="list" style="margin-top:16px;"></div>
            </div>
          </section>
        </div>
      </section>

      <script>
        const state = { settings, schedules: [], sessions: [], templates: [], manualRunsInFlight: [] };
        const latestResultEl = document.getElementById("latestResult");
        const dashboardLayoutEl = document.getElementById("dashboardLayout");
        const historyListEl = document.getElementById("historyList");
        const historyPanelContentEl = document.getElementById("historyPanelContent");
        const schedulesListEl = document.getElementById("schedulesList");
        const schedulesPanelContentEl = document.getElementById("schedulesPanelContent");
        const scheduleEditorContentEl = document.getElementById("scheduleEditorContent");
        const scheduleForm = document.getElementById("scheduleForm");
        const connectionStatus = document.getElementById("connectionStatus");
        const runtimeInfo = document.getElementById("runtimeInfo");
        const modelForm = document.getElementById("modelForm");
        const modelInput = document.getElementById("modelInput");
        const saveScheduleButton = document.getElementById("saveScheduleButton");
        const cancelScheduleEditButton = document.getElementById("cancelScheduleEditButton");
        const toggleHistoryButton = document.getElementById("toggleHistoryButton");
        const toggleSchedulesButton = document.getElementById("toggleSchedulesButton");
        const toggleScheduleEditorButton = document.getElementById("toggleScheduleEditorButton");
        const clearHistoryButton = document.getElementById("clearHistoryButton");
        let liveSocket = null;
        let liveReconnectTimer = null;
        let liveConnectTimeout = null;

        function renderRuntimeInfo() {
          runtimeInfo.textContent = `${state.settings.active_model} on ${state.settings.host}:${state.settings.port}`;
          modelInput.innerHTML = (state.settings.available_models || []).map((model) => `
            <option value="${escapeHtml(model)}">${escapeHtml(model)}</option>
          `).join("");
          modelInput.value = state.settings.active_model;
        }

        function renderLatest() {
          const latest = state.sessions[0];
          if (!latest) {
            latestResultEl.innerHTML = '<p class="muted">No generated session yet.</p>';
            return;
          }
          if (latest.status !== "success" || !latest.render_payload) {
            latestResultEl.innerHTML = `
              <span class="status">Failed</span>
              <p class="summary">${escapeHtml(latest.error_text || "Generation failed.")}</p>
            `;
            return;
          }
          const payload = latest.render_payload;
          const cards = payload.items.map((item) => `
            <article class="card">
              <div class="card-header">
                <h3>${escapeHtml(item.term)}</h3>
                <button class="secondary pronounce-button" type="button" data-pronounce-text="${escapeHtml(item.term || "")}">
                  Pronounce term
                </button>
              </div>
              <p><strong>Translation:</strong> ${escapeHtml(item.translation || "-")}</p>
              <p><strong>Explanation:</strong> ${escapeHtml(item.explanation || "-")}</p>
              <div class="inline-row">
                <p><strong>Example:</strong> ${escapeHtml(item.example_source || "-")}</p>
                <button class="secondary pronounce-button" type="button" data-pronounce-text="${escapeHtml(item.example_source || "")}">
                  Pronounce example
                </button>
              </div>
              <p><strong>Example translation:</strong> ${escapeHtml(item.example_target || "-")}</p>
              <p><strong>Notes:</strong> ${escapeHtml(item.notes || "-")}</p>
              <p class="muted card-meta">${escapeHtml((item.tags || []).join(", "))}</p>
            </article>
          `).join("");
          latestResultEl.innerHTML = `
            <h3 class="result-title">${escapeHtml(payload.title)}</h3>
            <p class="result-meta">${escapeHtml(formatDateTime(latest.generated_at, Intl.DateTimeFormat().resolvedOptions().timeZone))}${latest.generation_seconds != null ? ` | generated in ${escapeHtml(formatGenerationDuration(latest.generation_seconds))}` : ""}</p>
            <p class="summary">${escapeHtml(payload.summary)}</p>
            ${payload.focus_hint ? `<p><strong>Focus:</strong> ${escapeHtml(payload.focus_hint)}</p>` : ""}
            <div class="cards">${cards}</div>
          `;
          updatePronounceButtons(latestResultEl);
        }

        function renderHistory() {
          if (!state.sessions.length) {
            historyListEl.innerHTML = '<p class="muted">No sessions yet.</p>';
            return;
          }
          historyListEl.innerHTML = state.sessions.map((session) => `
            <article class="list-item">
              <div class="actions">
                <span class="status">${escapeHtml(session.status)}</span>
                <button class="secondary" type="button" data-session-id="${session.id}">Open</button>
                <button class="secondary" type="button" data-delete-session-id="${session.id}">Remove</button>
              </div>
              <p><strong>${escapeHtml(session.render_payload?.title || session.error_text || "Untitled session")}</strong></p>
              <p class="muted">${escapeHtml(formatDateTime(session.generated_at, Intl.DateTimeFormat().resolvedOptions().timeZone))}</p>
            </article>
          `).join("");
        }

        function renderSchedules() {
          const select = scheduleForm.elements.template_id;
          select.innerHTML = state.templates.map((template) => `
            <option value="${template.id}">${escapeHtml(template.name)}</option>
          `).join("");
          schedulesListEl.innerHTML = state.schedules.map((schedule) => `
            <article class="list-item">
              <p><strong>${escapeHtml(schedule.name)}</strong></p>
              <p class="muted">${escapeHtml(schedule.cron_expr)} | next: ${escapeHtml(formatDateTime(schedule.next_run_at, schedule.timezone))}${schedule.timezone ? ` (${escapeHtml(schedule.timezone)})` : ""}</p>
              <div class="actions">
                <span class="status">${schedule.is_active ? "active" : "paused"}</span>
                <button class="secondary" type="button" data-edit-schedule-id="${schedule.id}">Edit</button>
                <button class="secondary" type="button" data-toggle-schedule-id="${schedule.id}">${schedule.is_active ? "Pause" : "Resume"}</button>
                <button class="secondary" type="button" data-delete-schedule-id="${schedule.id}">Delete</button>
                <button class="secondary" type="button" data-run-now="${schedule.id}" ${state.manualRunsInFlight.includes(schedule.id) ? 'disabled aria-busy="true"' : ""}>${state.manualRunsInFlight.includes(schedule.id) ? "Running..." : "Run Now"}</button>
              </div>
              ${state.manualRunsInFlight.includes(schedule.id) ? `
                <div class="run-progress" aria-live="polite">
                  <div class="run-progress-label">Generating study session...</div>
                  <div class="run-progress-bar" role="progressbar" aria-label="Generating study session"></div>
                </div>
              ` : ""}
            </article>
          `).join("") || '<p class="muted">No schedules yet.</p>';
        }

        function setManualRunInFlight(scheduleId, inFlight) {
          const active = new Set(state.manualRunsInFlight);
          if (inFlight) {
            active.add(scheduleId);
          } else {
            active.delete(scheduleId);
          }
          state.manualRunsInFlight = Array.from(active);
        }

        function setHistoryCollapsed(collapsed) {
          historyPanelContentEl.style.display = collapsed ? "none" : "";
          toggleHistoryButton.textContent = collapsed ? "Expand" : "Collapse";
          toggleHistoryButton.dataset.collapsed = collapsed ? "true" : "false";
        }

        function setSchedulesCollapsed(collapsed) {
          schedulesPanelContentEl.style.display = collapsed ? "none" : "";
          toggleSchedulesButton.textContent = collapsed ? "Expand" : "Collapse";
          toggleSchedulesButton.dataset.collapsed = collapsed ? "true" : "false";
          dashboardLayoutEl.classList.toggle("schedules-collapsed", collapsed);
        }

        function setScheduleEditorCollapsed(collapsed) {
          scheduleEditorContentEl.style.display = collapsed ? "none" : "";
          toggleScheduleEditorButton.textContent = collapsed ? "Expand" : "Collapse";
          toggleScheduleEditorButton.dataset.collapsed = collapsed ? "true" : "false";
        }

        function resetScheduleForm() {
          scheduleForm.reset();
          scheduleForm.elements.schedule_id.value = "";
          scheduleForm.elements.timezone.value = "Europe/Belgrade";
          scheduleForm.elements.is_active.checked = true;
          scheduleForm.elements.notification_enabled.checked = true;
          saveScheduleButton.textContent = "Save Schedule";
          cancelScheduleEditButton.style.display = "none";
        }

        function loadScheduleIntoForm(scheduleId) {
          const schedule = state.schedules.find((item) => item.id === scheduleId);
          if (!schedule) {
            return;
          }
          scheduleForm.elements.schedule_id.value = String(schedule.id);
          scheduleForm.elements.name.value = schedule.name || "";
          scheduleForm.elements.template_id.value = String(schedule.template_id);
          scheduleForm.elements.cron_expr.value = schedule.cron_expr || "";
          scheduleForm.elements.timezone.value = schedule.timezone || "Europe/Belgrade";
          scheduleForm.elements.variables.value = JSON.stringify(schedule.variables || {}, null, 2);
          scheduleForm.elements.is_active.checked = Boolean(schedule.is_active);
          scheduleForm.elements.notification_enabled.checked = Boolean(schedule.notification_enabled);
          saveScheduleButton.textContent = "Update Schedule";
          cancelScheduleEditButton.style.display = "";
          setSchedulesCollapsed(false);
          setScheduleEditorCollapsed(false);
          scheduleForm.scrollIntoView({ behavior: "smooth", block: "start" });
        }

        async function loadAll() {
          const [appSettings, templates, schedules, sessions] = await Promise.all([
            fetchJson("/api/settings"),
            fetchJson("/api/templates"),
            fetchJson("/api/schedules"),
            fetchJson("/api/sessions?limit=20"),
          ]);
          if (appSettings && Array.isArray(appSettings.available_models) && appSettings.active_model) {
            state.settings = appSettings;
          }
          state.templates = templates;
          state.schedules = schedules;
          state.sessions = await Promise.all(sessions.map((session) => fetchJson(`/api/sessions/${session.id}`)));
          renderRuntimeInfo();
          renderSchedules();
          renderHistory();
          renderLatest();
        }

        modelForm.addEventListener("submit", async (event) => {
          event.preventDefault();
          state.settings = await fetchJson("/api/settings", {
            method: "PUT",
            body: JSON.stringify({ active_model: modelInput.value.trim() }),
          });
          renderRuntimeInfo();
        });

        scheduleForm.addEventListener("submit", async (event) => {
          event.preventDefault();
          const form = new FormData(scheduleForm);
          const scheduleId = form.get("schedule_id");
          const cronExpr = String(form.get("cron_expr") || "").trim();
          const timezone = String(form.get("timezone") || "").trim();
          const cronError = validateCronExpression(cronExpr);
          if (cronError) {
            window.alert(cronError);
            scheduleForm.elements.cron_expr.focus();
            return;
          }
          const payload = {
            name: String(form.get("name") || "").trim(),
            template_id: Number(form.get("template_id")),
            variables: parseJsonField(form.get("variables"), {}),
            cron_expr: cronExpr,
            timezone,
            is_active: form.get("is_active") === "on",
            notification_enabled: form.get("notification_enabled") === "on",
          };
          await fetchJson(scheduleId ? `/api/schedules/${scheduleId}` : "/api/schedules", {
            method: scheduleId ? "PUT" : "POST",
            body: JSON.stringify(payload),
          });
          resetScheduleForm();
          await loadAll();
        });

        cancelScheduleEditButton.addEventListener("click", () => {
          resetScheduleForm();
        });

        historyListEl.addEventListener("click", async (event) => {
          const deleteButton = event.target.closest("[data-delete-session-id]");
          if (deleteButton) {
            const sessionId = Number(deleteButton.dataset.deleteSessionId);
            await fetchJson(`/api/sessions/${sessionId}`, { method: "DELETE" });
            state.sessions = state.sessions.filter((item) => item.id !== sessionId);
            renderHistory();
            renderLatest();
            return;
          }
          const button = event.target.closest("[data-session-id]");
          if (!button) return;
          const session = await fetchJson(`/api/sessions/${button.dataset.sessionId}`);
          state.sessions = [session, ...state.sessions.filter((item) => item.id !== session.id)];
          renderHistory();
          renderLatest();
        });

        toggleHistoryButton.addEventListener("click", () => {
          const collapsed = toggleHistoryButton.dataset.collapsed === "true";
          setHistoryCollapsed(!collapsed);
        });

        toggleSchedulesButton.addEventListener("click", () => {
          const collapsed = toggleSchedulesButton.dataset.collapsed === "true";
          setSchedulesCollapsed(!collapsed);
        });

        toggleScheduleEditorButton.addEventListener("click", () => {
          const collapsed = toggleScheduleEditorButton.dataset.collapsed === "true";
          setScheduleEditorCollapsed(!collapsed);
        });

        clearHistoryButton.addEventListener("click", async () => {
          if (!window.confirm("Delete all generated session history?")) {
            return;
          }
          await fetchJson("/api/sessions", { method: "DELETE" });
          state.sessions = [];
          renderHistory();
          renderLatest();
        });

        latestResultEl.addEventListener("click", (event) => {
          const button = event.target.closest("[data-pronounce-text]");
          if (!button) {
            return;
          }
          speakFromButton(button);
        });

        schedulesListEl.addEventListener("click", async (event) => {
          const editButton = event.target.closest("[data-edit-schedule-id]");
          if (editButton) {
            loadScheduleIntoForm(Number(editButton.dataset.editScheduleId));
            return;
          }
          const toggleButton = event.target.closest("[data-toggle-schedule-id]");
          if (toggleButton) {
            const scheduleId = Number(toggleButton.dataset.toggleScheduleId);
            const schedule = state.schedules.find((item) => item.id === scheduleId);
            if (!schedule) {
              return;
            }
            await fetchJson(`/api/schedules/${scheduleId}`, {
              method: "PUT",
              body: JSON.stringify({
                name: schedule.name,
                template_id: schedule.template_id,
                variables: schedule.variables || {},
                cron_expr: schedule.cron_expr,
                timezone: schedule.timezone,
                is_active: !schedule.is_active,
                notification_enabled: schedule.notification_enabled,
              }),
            });
            await loadAll();
            if (scheduleForm.elements.schedule_id.value === String(scheduleId)) {
              loadScheduleIntoForm(scheduleId);
            }
            return;
          }
          const deleteButton = event.target.closest("[data-delete-schedule-id]");
          if (deleteButton) {
            const scheduleId = Number(deleteButton.dataset.deleteScheduleId);
            if (!window.confirm("Delete this schedule and its generated history?")) {
              return;
            }
            await fetchJson(`/api/schedules/${scheduleId}`, { method: "DELETE" });
            if (scheduleForm.elements.schedule_id.value === String(scheduleId)) {
              resetScheduleForm();
            }
            await loadAll();
            return;
          }
          const button = event.target.closest("[data-run-now]");
          if (!button) return;
          const scheduleId = Number(button.dataset.runNow);
          setManualRunInFlight(scheduleId, true);
          renderSchedules();
          try {
            await fetchJson(`/api/schedules/${scheduleId}/run-now`, { method: "POST" });
          } catch (error) {
            setManualRunInFlight(scheduleId, false);
            renderSchedules();
            throw error;
          }
        });

        document.getElementById("enableNotificationsButton").addEventListener("click", async () => {
          if (!("Notification" in window)) {
            alert("This browser does not support notifications.");
            return;
          }
          await Notification.requestPermission();
        });

        function notifyBrowser(session) {
          if (Notification.permission !== "granted" || session.status !== "success" || !session.render_payload) {
            return;
          }
          const notification = new Notification(session.render_payload.title, {
            body: session.render_payload.summary,
          });
          notification.onclick = () => {
            window.focus();
            state.sessions = [session, ...state.sessions.filter((item) => item.id !== session.id)];
            renderHistory();
            renderLatest();
          };
        }

        function scheduleLiveReconnect(delay = 1500) {
          if (liveReconnectTimer !== null) {
            return;
          }
          connectionStatus.textContent = "Reconnecting…";
          liveReconnectTimer = window.setTimeout(() => {
            liveReconnectTimer = null;
            connectLive();
          }, delay);
        }

        function connectLive() {
          if (liveSocket && (liveSocket.readyState === WebSocket.OPEN || liveSocket.readyState === WebSocket.CONNECTING)) {
            return;
          }
          window.clearTimeout(liveConnectTimeout);
          connectionStatus.textContent = "Connecting…";
          const protocol = window.location.protocol === "https:" ? "wss" : "ws";
          const socket = new WebSocket(`${protocol}://${window.location.host}/api/live`);
          liveSocket = socket;
          liveConnectTimeout = window.setTimeout(() => {
            if (socket.readyState === WebSocket.CONNECTING) {
              connectionStatus.textContent = "Live timeout";
              socket.close();
            }
          }, 5000);
          socket.onopen = () => {
            window.clearTimeout(liveConnectTimeout);
            connectionStatus.textContent = "Live connected";
          };
          socket.onerror = () => {
            connectionStatus.textContent = "Live error";
          };
          socket.onclose = () => {
            window.clearTimeout(liveConnectTimeout);
            if (liveSocket === socket) {
              liveSocket = null;
            }
            scheduleLiveReconnect();
          };
          socket.onmessage = (event) => {
            const payload = JSON.parse(event.data);
            if (payload.type === "session.created") {
              const session = payload.session;
              setManualRunInFlight(payload.schedule.id, false);
              state.sessions = [session, ...state.sessions.filter((item) => item.id !== session.id)].slice(0, 20);
              state.schedules = state.schedules.map((schedule) =>
                schedule.id === payload.schedule.id ? payload.schedule : schedule
              );
              renderSchedules();
              renderHistory();
              renderLatest();
              if (payload.run_source !== "manual" && payload.schedule?.notification_enabled) {
                notifyBrowser(session);
              }
            }
          };
        }

        renderRuntimeInfo();
        setHistoryCollapsed(true);
        setSchedulesCollapsed(false);
        setScheduleEditorCollapsed(true);
        resetScheduleForm();
        loadAll().then(connectLive).catch((error) => {
          connectionStatus.textContent = "Load failed";
          latestResultEl.innerHTML = `<pre>${escapeHtml(error.message)}</pre>`;
        });
      </script>
    """
    return _shell(
        "Prompt Study Notifier",
        "dashboard",
        body.replace("__MODEL_OPTIONS__", model_options_markup),
        settings_json=settings_json,
    )


def render_templates_page(settings: SettingsRecord, templates: list[TemplateRecord]) -> str:
    settings_json = json.dumps(settings.model_dump())
    templates_json = json.dumps([template.model_dump(mode="json") for template in templates])
    templates_markup = _template_list_markup(templates)
    body = """
      <section class="panel" style="margin-top:18px;">
        <h1 class="page-title">Templates</h1>
        <p class="page-intro">Create, edit, preview, and review reusable prompt templates separately from the live study dashboard.</p>
      </section>

      <section class="layout layout-templates">
        <div class="column">
          <section class="panel">
            <h2>Template Editor</h2>
            <form id="templateForm">
              <input type="hidden" name="template_id">
              <label class="field">
                <span class="field-label">Template Name</span>
                <input name="name" placeholder="Template name" required>
              </label>
              <label class="field">
                <span class="field-label">Description</span>
                <textarea name="description" placeholder="Description"></textarea>
              </label>
              <label class="field">
                <span class="field-heading">
                  <span class="field-label">System Prompt</span>
                  <button class="help-link" type="button" onclick="showHelp('systemPrompt')">What is this?</button>
                </span>
                <textarea name="system_prompt" placeholder="System prompt" required></textarea>
              </label>
              <label class="field">
                <span class="field-heading">
                  <span class="field-label">User Prompt Template</span>
                  <button class="help-link" type="button" onclick="showHelp('userPromptTemplate')">What is this?</button>
                </span>
                <textarea name="user_prompt_template" placeholder="User prompt template with variables like {topic}" required></textarea>
              </label>
              <label class="field">
                <span class="field-heading">
                  <span class="field-label">Variable Definitions</span>
                  <button class="help-link" type="button" onclick="showHelp('templateVariables')">How to use this</button>
                </span>
                <textarea name="variables" placeholder='Variable definitions JSON, e.g. [{"name":"topic","label":"Topic"}]'></textarea>
              </label>
              <div class="actions">
                <button id="saveTemplateButton" type="submit">Save Template</button>
                <button id="cancelTemplateEditButton" class="secondary" type="button">Cancel Edit</button>
                <button id="previewPromptButton" class="secondary" type="button">Preview Prompt</button>
              </div>
            </form>
            <div id="templatePreview" style="margin-top:12px;"></div>
          </section>
        </div>

        <div class="column">
          <section class="panel">
            <h2>Existing Templates</h2>
            <div id="templatesList" class="list">
              __TEMPLATES_MARKUP__
            </div>
          </section>
        </div>
      </section>

      <script>
        const state = { settings, templates: __INITIAL_TEMPLATES__ };
        const templateForm = document.getElementById("templateForm");
        const templatesListEl = document.getElementById("templatesList");
        const templatePreview = document.getElementById("templatePreview");
        const saveTemplateButton = document.getElementById("saveTemplateButton");
        const cancelTemplateEditButton = document.getElementById("cancelTemplateEditButton");

        function renderTemplates() {
          templatesListEl.innerHTML = state.templates.map((template) => `
            <article class="list-item">
              <div class="actions">
                <p><strong>${escapeHtml(template.name)}</strong></p>
                <button class="secondary" type="button" data-edit-template-id="${template.id}">Edit</button>
                <button class="secondary" type="button" data-delete-template-id="${template.id}">Delete</button>
              </div>
              <p class="muted">${escapeHtml(template.description || "")}</p>
              <p class="muted">Variables: ${escapeHtml(template.variable_names.join(", ") || "none")}</p>
            </article>
          `).join("") || '<p class="muted">No templates yet.</p>';
        }

        function resetTemplateForm() {
          templateForm.reset();
          templateForm.elements.template_id.value = "";
          templatePreview.innerHTML = "";
          saveTemplateButton.textContent = "Save Template";
          cancelTemplateEditButton.style.display = "none";
        }

        function loadTemplateIntoForm(templateId) {
          const template = state.templates.find((item) => item.id === templateId);
          if (!template) {
            return;
          }
          templateForm.elements.template_id.value = String(template.id);
          templateForm.elements.name.value = template.name || "";
          templateForm.elements.description.value = template.description || "";
          templateForm.elements.system_prompt.value = template.system_prompt || "";
          templateForm.elements.user_prompt_template.value = template.user_prompt_template || "";
          templateForm.elements.variables.value = JSON.stringify(template.variables || [], null, 2);
          saveTemplateButton.textContent = "Update Template";
          cancelTemplateEditButton.style.display = "";
          templateForm.scrollIntoView({ behavior: "smooth", block: "start" });
        }

        async function loadAll() {
          state.templates = await fetchJson("/api/templates");
          renderTemplates();
        }

        templateForm.addEventListener("submit", async (event) => {
          event.preventDefault();
          const form = new FormData(templateForm);
          const templateId = form.get("template_id");
          const payload = {
            name: form.get("name"),
            description: form.get("description") || null,
            system_prompt: form.get("system_prompt"),
            user_prompt_template: form.get("user_prompt_template"),
            output_schema_version: "v1",
            is_active: true,
            variables: parseJsonField(form.get("variables"), []),
          };
          await fetchJson(templateId ? `/api/templates/${templateId}` : "/api/templates", {
            method: templateId ? "PUT" : "POST",
            body: JSON.stringify(payload),
          });
          resetTemplateForm();
          await loadAll();
        });

        cancelTemplateEditButton.addEventListener("click", () => {
          resetTemplateForm();
        });

        document.getElementById("previewPromptButton").addEventListener("click", async () => {
          const form = new FormData(templateForm);
          try {
            const parsed = parseJsonField(form.get("variables"), {});
            const variables = Array.isArray(parsed)
              ? Object.fromEntries(parsed.map((item) => [item.name, item.example || ""]))
              : parsed;
            const preview = await fetchJson("/api/templates/preview", {
              method: "POST",
              body: JSON.stringify({
                user_prompt_template: form.get("user_prompt_template"),
                variables,
              }),
            });
            templatePreview.innerHTML = `<pre>${escapeHtml(preview.resolved_prompt)}</pre>`;
          } catch (error) {
            templatePreview.innerHTML = `<pre>${escapeHtml(error.message)}</pre>`;
          }
        });

        templatesListEl.addEventListener("click", (event) => {
          const button = event.target.closest("[data-edit-template-id]");
          if (button) {
            loadTemplateIntoForm(Number(button.dataset.editTemplateId));
            return;
          }
          const deleteButton = event.target.closest("[data-delete-template-id]");
          if (!deleteButton) return;
          void (async () => {
            const templateId = Number(deleteButton.dataset.deleteTemplateId);
            if (!window.confirm("Delete this template? Delete schedules that use it first.")) {
              return;
            }
            try {
              await fetchJson(`/api/templates/${templateId}`, { method: "DELETE" });
              if (templateForm.elements.template_id.value === String(templateId)) {
                resetTemplateForm();
              }
              await loadAll();
            } catch (error) {
              templatePreview.innerHTML = `<pre>${escapeHtml(error.message)}</pre>`;
            }
          })();
        });

        resetTemplateForm();
        renderTemplates();
        loadAll().catch((error) => {
          templatesListEl.innerHTML = `<pre>${escapeHtml(error.message)}</pre>`;
        });
      </script>
    """
    body = body.replace("__INITIAL_TEMPLATES__", templates_json)
    body = body.replace("__TEMPLATES_MARKUP__", templates_markup)
    return _shell("Templates | Prompt Study Notifier", "templates", body, settings_json=settings_json)
