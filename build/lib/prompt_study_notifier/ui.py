from __future__ import annotations

import json

from prompt_study_notifier.schemas import SettingsRecord


def render_dashboard(settings: SettingsRecord) -> str:
    settings_json = json.dumps(settings.model_dump())
    html = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Prompt Study Notifier</title>
    <style>
      :root {{
        --bg-top: #f6efe1;
        --bg-bottom: #ddeaf1;
        --surface: rgba(255, 253, 248, 0.84);
        --ink: #18222f;
        --muted: #61717f;
        --accent: #bb5a34;
        --accent-strong: #8e3f20;
        --line: rgba(24, 34, 47, 0.09);
        --shadow: 0 24px 70px rgba(24, 34, 47, 0.14);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        color: var(--ink);
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
        background:
          radial-gradient(circle at top left, rgba(255,255,255,0.75), transparent 30%),
          radial-gradient(circle at right, rgba(187,90,52,0.16), transparent 28%),
          linear-gradient(160deg, var(--bg-top), var(--bg-bottom));
      }}
      .page {{
        width: min(1200px, calc(100vw - 28px));
        margin: 18px auto 42px;
      }}
      .hero {{
        padding: 26px;
        border-radius: 28px;
        background:
          linear-gradient(135deg, rgba(24,34,47,0.96), rgba(44,63,81,0.92)),
          linear-gradient(135deg, rgba(187,90,52,0.46), rgba(255,255,255,0.08));
        color: #f8f3ec;
        box-shadow: var(--shadow);
      }}
      .hero h1 {{
        margin: 10px 0 8px;
        font-family: "Palatino", "Book Antiqua", serif;
        font-size: clamp(40px, 6vw, 68px);
        line-height: 0.95;
      }}
      .hero p {{ margin: 0; max-width: 820px; color: rgba(248,243,236,0.82); }}
      .hero-actions {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 18px; }}
      .chip {{
        display: inline-flex;
        align-items: center;
        padding: 7px 12px;
        border-radius: 999px;
        border: 1px solid rgba(255,255,255,0.14);
        background: rgba(255,255,255,0.08);
        font-size: 14px;
      }}
      .layout {{
        display: grid;
        grid-template-columns: 1.3fr 0.9fr;
        gap: 18px;
        margin-top: 18px;
      }}
      .layout[data-right-density="compact"] {{
        grid-template-columns: 1.55fr 0.45fr;
      }}
      .layout[data-right-density="collapsed"] {{
        grid-template-columns: 1.8fr 0.2fr;
      }}
      .column {{
        display: grid;
        gap: 18px;
        align-content: start;
      }}
      .column[data-column-role="right"] .panel[data-panel-collapsed="true"] {{
        padding: 16px;
      }}
      .column[data-column-role="right"] .panel[data-panel-collapsed="true"] .actions {{
        justify-content: space-between;
      }}
      .panel {{
        padding: 20px;
        border-radius: 24px;
        border: 1px solid var(--line);
        background: var(--surface);
        backdrop-filter: blur(10px);
        box-shadow: var(--shadow);
      }}
      .panel h2 {{
        margin: 0 0 14px;
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        color: var(--muted);
      }}
      .result-title {{
        margin: 0 0 8px;
        font-size: clamp(32px, 4vw, 52px);
        line-height: 1.02;
        font-family: "Palatino", "Book Antiqua", serif;
      }}
      .summary {{ margin: 0; color: var(--muted); font-size: 18px; line-height: 1.6; }}
      .cards {{ display: grid; gap: 14px; margin-top: 16px; }}
      .card {{
        padding: 18px;
        border-radius: 20px;
        background: rgba(255,255,255,0.68);
        border: 1px solid var(--line);
      }}
      .card h3 {{ margin: 0 0 8px; font-size: 28px; }}
      .card p {{ margin: 6px 0; line-height: 1.55; }}
      .muted {{ color: var(--muted); }}
      .list {{ display: grid; gap: 10px; }}
      .list-item {{
        padding: 14px;
        border-radius: 18px;
        background: rgba(255,255,255,0.62);
        border: 1px solid var(--line);
      }}
      form {{ display: grid; gap: 10px; }}
      input, textarea, select {{
        width: 100%;
        padding: 12px 14px;
        border-radius: 14px;
        border: 1px solid rgba(24,34,47,0.12);
        font: inherit;
        background: rgba(255,255,255,0.92);
      }}
      textarea {{ min-height: 96px; resize: vertical; }}
      button {{
        appearance: none;
        border: 0;
        border-radius: 999px;
        padding: 12px 16px;
        background: linear-gradient(135deg, var(--accent), var(--accent-strong));
        color: white;
        font: inherit;
        font-weight: 600;
        cursor: pointer;
      }}
      button.secondary {{
        background: rgba(24,34,47,0.08);
        color: var(--ink);
      }}
      .actions {{ display: flex; gap: 10px; flex-wrap: wrap; }}
      .two-up {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
      }}
      pre {{
        margin: 0;
        padding: 14px;
        border-radius: 16px;
        background: rgba(24,34,47,0.06);
        overflow: auto;
        white-space: pre-wrap;
      }}
      .status {{
        display: inline-flex;
        padding: 4px 10px;
        border-radius: 999px;
        background: rgba(24,34,47,0.08);
        font-size: 13px;
      }}
      @media (max-width: 980px) {{
        .layout {{ grid-template-columns: 1fr; }}
        .two-up {{ grid-template-columns: 1fr; }}
      }}
    </style>
  </head>
  <body>
    <main class="page">
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
          <input id="modelInput" name="active_model" list="modelOptions" placeholder="Model ID">
          <datalist id="modelOptions"></datalist>
          <button type="submit">Save Model</button>
        </form>
      </section>

      <section class="layout">
        <div class="column" data-column-role="left">
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

        <div class="column" data-column-role="right" id="rightColumn">
          <section class="panel" id="templatesPanel">
            <div class="actions" style="justify-content:space-between; align-items:center; margin-bottom:14px;">
              <h2 style="margin:0;">Prompt Templates</h2>
              <button id="toggleTemplatesButton" class="secondary" type="button">Collapse</button>
            </div>
            <div id="templatesPanelContent">
              <form id="templateForm">
                <input name="name" placeholder="Template name" required>
                <textarea name="description" placeholder="Description"></textarea>
                <textarea name="system_prompt" placeholder="System prompt" required></textarea>
                <textarea name="user_prompt_template" placeholder="User prompt template with variables like {{topic}}" required></textarea>
                <textarea name="variables" placeholder='Variable definitions JSON, e.g. [{{"name":"topic","label":"Topic"}}]'></textarea>
                <div class="actions">
                  <button type="submit">Save Template</button>
                  <button id="previewPromptButton" class="secondary" type="button">Preview Prompt</button>
                </div>
              </form>
              <div id="templatePreview" style="margin-top:12px;"></div>
              <div id="templatesList" class="list" style="margin-top:16px;"></div>
            </div>
          </section>

          <section class="panel" id="schedulesPanel">
            <div class="actions" style="justify-content:space-between; align-items:center; margin-bottom:14px;">
              <h2 style="margin:0;">Schedules</h2>
              <button id="toggleSchedulesButton" class="secondary" type="button">Collapse</button>
            </div>
            <div id="schedulesPanelContent">
              <form id="scheduleForm">
                <input name="name" placeholder="Schedule name" required>
                <select name="template_id" required></select>
                <input name="cron_expr" placeholder="Cron expression, e.g. */30 * * * *" required>
                <input name="timezone" value="Europe/Belgrade" required>
                <textarea name="variables" placeholder='Variables JSON, e.g. {{"target_language":"Spanish","topic":"restaurant conversations","focus_area":"polite requests","difficulty":"A2"}}'></textarea>
                <div class="two-up">
                  <label><input type="checkbox" name="is_active" checked> Active</label>
                  <label><input type="checkbox" name="notification_enabled" checked> Browser notification</label>
                </div>
                <div class="actions">
                  <button type="submit">Save Schedule</button>
                </div>
              </form>
              <div id="schedulesList" class="list" style="margin-top:16px;"></div>
            </div>
          </section>
        </div>
      </section>
    </main>

    <script>
      const settings = __SETTINGS_JSON__;
      const state = {{
        settings,
        templates: [],
        schedules: [],
        sessions: [],
      }};

      const layoutEl = document.querySelector(".layout");
      const latestResultEl = document.getElementById("latestResult");
      const historyListEl = document.getElementById("historyList");
      const historyPanelContentEl = document.getElementById("historyPanelContent");
      const rightColumnEl = document.getElementById("rightColumn");
      const templatesPanelEl = document.getElementById("templatesPanel");
      const schedulesPanelEl = document.getElementById("schedulesPanel");
      const templatesListEl = document.getElementById("templatesList");
      const templatesPanelContentEl = document.getElementById("templatesPanelContent");
      const schedulesListEl = document.getElementById("schedulesList");
      const schedulesPanelContentEl = document.getElementById("schedulesPanelContent");
      const templateForm = document.getElementById("templateForm");
      const scheduleForm = document.getElementById("scheduleForm");
      const templatePreview = document.getElementById("templatePreview");
      const connectionStatus = document.getElementById("connectionStatus");
      const runtimeInfo = document.getElementById("runtimeInfo");
      const modelForm = document.getElementById("modelForm");
      const modelInput = document.getElementById("modelInput");
      const modelOptions = document.getElementById("modelOptions");
      const toggleHistoryButton = document.getElementById("toggleHistoryButton");
      const toggleTemplatesButton = document.getElementById("toggleTemplatesButton");
      const toggleSchedulesButton = document.getElementById("toggleSchedulesButton");
      const clearHistoryButton = document.getElementById("clearHistoryButton");

      function renderRuntimeInfo() {{
        runtimeInfo.textContent = `${{state.settings.active_model}} on ${{state.settings.host}}:${{state.settings.port}}`;
        modelInput.value = state.settings.active_model;
        modelOptions.innerHTML = (state.settings.available_models || []).map((model) => `
          <option value="${{escapeHtml(model)}}"></option>
        `).join("");
      }}

      function parseJsonField(text, fallback) {{
        if (!text.trim()) {{
          return fallback;
        }}
        return JSON.parse(text);
      }}

      function escapeHtml(value) {{
        return String(value ?? "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;");
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

      function renderLatest() {{
        const latest = state.sessions[0];
        if (!latest) {{
          latestResultEl.innerHTML = '<p class="muted">No generated session yet.</p>';
          return;
        }}
        if (latest.status !== "success" || !latest.render_payload) {{
          latestResultEl.innerHTML = `
            <span class="status">Failed</span>
            <p class="summary">${{escapeHtml(latest.error_text || "Generation failed.")}}</p>
          `;
          return;
        }}
        const payload = latest.render_payload;
        const cards = payload.items.map((item) => `
          <article class="card">
            <h3>${{escapeHtml(item.term)}}</h3>
            <p><strong>Translation:</strong> ${{escapeHtml(item.translation || "-")}}</p>
            <p><strong>Explanation:</strong> ${{escapeHtml(item.explanation || "-")}}</p>
            <p><strong>Example:</strong> ${{escapeHtml(item.example_source || "-")}}</p>
            <p><strong>Example translation:</strong> ${{escapeHtml(item.example_target || "-")}}</p>
            <p><strong>Notes:</strong> ${{escapeHtml(item.notes || "-")}}</p>
            <p class="muted">${{escapeHtml((item.tags || []).join(", "))}}</p>
          </article>
        `).join("");
        latestResultEl.innerHTML = `
          <div class="chip">${{escapeHtml(payload.topic)}}</div>
          <h3 class="result-title">${{escapeHtml(payload.title)}}</h3>
          <p class="summary">${{escapeHtml(payload.summary)}}</p>
          ${payload.focus_hint ? `<p><strong>Focus:</strong> ${{escapeHtml(payload.focus_hint)}}</p>` : ""}
          <div class="cards">${cards}</div>
        `;
      }}

      function renderHistory() {{
        if (!state.sessions.length) {{
          historyListEl.innerHTML = '<p class="muted">No sessions yet.</p>';
          return;
        }}
        historyListEl.innerHTML = state.sessions.map((session) => `
          <article class="list-item">
            <div class="actions">
              <span class="status">${{escapeHtml(session.status)}}</span>
              <button class="secondary" type="button" data-session-id="${{session.id}}">Open</button>
              <button class="secondary" type="button" data-delete-session-id="${{session.id}}">Remove</button>
            </div>
            <p><strong>${{escapeHtml(session.render_payload?.title || session.error_text || "Untitled session")}}</strong></p>
            <p class="muted">${{escapeHtml(formatDateTime(session.generated_at, Intl.DateTimeFormat().resolvedOptions().timeZone))}}</p>
          </article>
        `).join("");
      }}

      function setHistoryCollapsed(collapsed) {{
        historyPanelContentEl.style.display = collapsed ? "none" : "";
        toggleHistoryButton.textContent = collapsed ? "Expand" : "Collapse";
        toggleHistoryButton.dataset.collapsed = collapsed ? "true" : "false";
      }}

      function setTemplatesCollapsed(collapsed) {{
        templatesPanelContentEl.style.display = collapsed ? "none" : "";
        toggleTemplatesButton.textContent = collapsed ? "Expand" : "Collapse";
        toggleTemplatesButton.dataset.collapsed = collapsed ? "true" : "false";
        templatesPanelEl.dataset.panelCollapsed = collapsed ? "true" : "false";
        updateRightColumnDensity();
      }}

      function setSchedulesCollapsed(collapsed) {{
        schedulesPanelContentEl.style.display = collapsed ? "none" : "";
        toggleSchedulesButton.textContent = collapsed ? "Expand" : "Collapse";
        toggleSchedulesButton.dataset.collapsed = collapsed ? "true" : "false";
        schedulesPanelEl.dataset.panelCollapsed = collapsed ? "true" : "false";
        updateRightColumnDensity();
      }}

      function updateRightColumnDensity() {{
        const templatesCollapsed = toggleTemplatesButton.dataset.collapsed === "true";
        const schedulesCollapsed = toggleSchedulesButton.dataset.collapsed === "true";
        if (templatesCollapsed && schedulesCollapsed) {{
          layoutEl.dataset.rightDensity = "collapsed";
          rightColumnEl.dataset.rightDensity = "collapsed";
          return;
        }}
        if (templatesCollapsed || schedulesCollapsed) {{
          layoutEl.dataset.rightDensity = "compact";
          rightColumnEl.dataset.rightDensity = "compact";
          return;
        }}
        layoutEl.dataset.rightDensity = "full";
        rightColumnEl.dataset.rightDensity = "full";
      }}

      function renderTemplates() {{
        const select = scheduleForm.elements.template_id;
        select.innerHTML = state.templates.map((template) => `
          <option value="${{template.id}}">${{escapeHtml(template.name)}}</option>
        `).join("");
        templatesListEl.innerHTML = state.templates.map((template) => `
          <article class="list-item">
            <p><strong>${{escapeHtml(template.name)}}</strong></p>
            <p class="muted">${{escapeHtml(template.description || "")}}</p>
            <p class="muted">Variables: ${{escapeHtml(template.variable_names.join(", ") || "none")}}</p>
          </article>
        `).join("") || '<p class="muted">No templates yet.</p>';
      }}

      function renderSchedules() {{
        schedulesListEl.innerHTML = state.schedules.map((schedule) => `
          <article class="list-item">
            <p><strong>${{escapeHtml(schedule.name)}}</strong></p>
            <p class="muted">${{escapeHtml(schedule.cron_expr)}} | next: ${{escapeHtml(formatDateTime(schedule.next_run_at, schedule.timezone))}}${{schedule.timezone ? ` (${escapeHtml(schedule.timezone)})` : ""}}</p>
            <div class="actions">
              <span class="status">${{schedule.is_active ? "active" : "paused"}}</span>
              <button class="secondary" type="button" data-run-now="${{schedule.id}}">Run Now</button>
            </div>
          </article>
        `).join("") || '<p class="muted">No schedules yet.</p>';
      }}

      async function loadAll() {{
        const [appSettings, templates, schedules, sessions] = await Promise.all([
          fetchJson("/api/settings"),
          fetchJson("/api/templates"),
          fetchJson("/api/schedules"),
          fetchJson("/api/sessions?limit=20"),
        ]);
        state.settings = appSettings;
        state.templates = templates;
        state.schedules = schedules;
        state.sessions = await Promise.all(sessions.map((session) => fetchJson(`/api/sessions/${{session.id}}`)));
        renderRuntimeInfo();
        renderTemplates();
        renderSchedules();
        renderHistory();
        renderLatest();
      }}

      modelForm.addEventListener("submit", async (event) => {{
        event.preventDefault();
        state.settings = await fetchJson("/api/settings", {{
          method: "PUT",
          body: JSON.stringify({{
            active_model: modelInput.value.trim(),
          }}),
        }});
        renderRuntimeInfo();
      }});

      templateForm.addEventListener("submit", async (event) => {{
        event.preventDefault();
        const form = new FormData(templateForm);
        const payload = {{
          name: form.get("name"),
          description: form.get("description") || null,
          system_prompt: form.get("system_prompt"),
          user_prompt_template: form.get("user_prompt_template"),
          output_schema_version: "v1",
          is_active: true,
          variables: parseJsonField(form.get("variables"), []),
        }};
        await fetchJson("/api/templates", {{
          method: "POST",
          body: JSON.stringify(payload),
        }});
        templateForm.reset();
        await loadAll();
      }});

      document.getElementById("previewPromptButton").addEventListener("click", async () => {{
        const form = new FormData(templateForm);
        try {{
          const preview = await fetchJson("/api/templates/preview", {{
            method: "POST",
            body: JSON.stringify({{
              user_prompt_template: form.get("user_prompt_template"),
              variables: parseJsonField(form.get("variables"), {{}}).reduce
                ? Object.fromEntries(parseJsonField(form.get("variables"), []).map((item) => [item.name, item.example || ""]))
                : parseJsonField(form.get("variables"), {{}}),
            }}),
          }});
          templatePreview.innerHTML = `<pre>${{escapeHtml(preview.resolved_prompt)}}</pre>`;
        }} catch (error) {{
          templatePreview.innerHTML = `<pre>${{escapeHtml(error.message)}}</pre>`;
        }}
      }});

      scheduleForm.addEventListener("submit", async (event) => {{
        event.preventDefault();
        const form = new FormData(scheduleForm);
        const payload = {{
          name: form.get("name"),
          template_id: Number(form.get("template_id")),
          variables: parseJsonField(form.get("variables"), {{}}),
          cron_expr: form.get("cron_expr"),
          timezone: form.get("timezone"),
          is_active: form.get("is_active") === "on",
          notification_enabled: form.get("notification_enabled") === "on",
        }};
        await fetchJson("/api/schedules", {{
          method: "POST",
          body: JSON.stringify(payload),
        }});
        scheduleForm.reset();
        scheduleForm.elements.timezone.value = "Europe/Belgrade";
        await loadAll();
      }});

      historyListEl.addEventListener("click", async (event) => {{
        const deleteButton = event.target.closest("[data-delete-session-id]");
        if (deleteButton) {{
          const sessionId = Number(deleteButton.dataset.deleteSessionId);
          await fetchJson(`/api/sessions/${{sessionId}}`, {{ method: "DELETE" }});
          state.sessions = state.sessions.filter((item) => item.id !== sessionId);
          renderHistory();
          renderLatest();
          return;
        }}
        const button = event.target.closest("[data-session-id]");
        if (!button) return;
        const session = await fetchJson(`/api/sessions/${{button.dataset.sessionId}}`);
        state.sessions = [session, ...state.sessions.filter((item) => item.id !== session.id)];
        renderHistory();
        renderLatest();
      }});

      toggleHistoryButton.addEventListener("click", () => {{
        const collapsed = toggleHistoryButton.dataset.collapsed === "true";
        setHistoryCollapsed(!collapsed);
      }});

      toggleTemplatesButton.addEventListener("click", () => {{
        const collapsed = toggleTemplatesButton.dataset.collapsed === "true";
        setTemplatesCollapsed(!collapsed);
      }});

      toggleSchedulesButton.addEventListener("click", () => {{
        const collapsed = toggleSchedulesButton.dataset.collapsed === "true";
        setSchedulesCollapsed(!collapsed);
      }});

      clearHistoryButton.addEventListener("click", async () => {{
        if (!window.confirm("Delete all generated session history?")) {{
          return;
        }}
        await fetchJson("/api/sessions", {{ method: "DELETE" }});
        state.sessions = [];
        renderHistory();
        renderLatest();
      }});

      schedulesListEl.addEventListener("click", async (event) => {{
        const button = event.target.closest("[data-run-now]");
        if (!button) return;
        await fetchJson(`/api/schedules/${{button.dataset.runNow}}/run-now`, {{ method: "POST" }});
      }});

      document.getElementById("enableNotificationsButton").addEventListener("click", async () => {{
        if (!("Notification" in window)) {{
          alert("This browser does not support notifications.");
          return;
        }}
        await Notification.requestPermission();
      }});

      function notifyBrowser(session) {{
        if (Notification.permission !== "granted" || session.status !== "success" || !session.render_payload) {{
          return;
        }}
        const notification = new Notification(session.render_payload.title, {{
          body: session.render_payload.summary,
        }});
        notification.onclick = () => {{
          window.focus();
          state.sessions = [session, ...state.sessions.filter((item) => item.id !== session.id)];
          renderHistory();
          renderLatest();
        }};
      }}

      function connectLive() {{
        const protocol = window.location.protocol === "https:" ? "wss" : "ws";
        const socket = new WebSocket(`${{protocol}}://${{window.location.host}}/api/live`);
        socket.onopen = () => {{
          connectionStatus.textContent = "Live connected";
        }};
        socket.onclose = () => {{
          connectionStatus.textContent = "Reconnecting…";
          setTimeout(connectLive, 1500);
        }};
        socket.onmessage = (event) => {{
          const payload = JSON.parse(event.data);
          if (payload.type === "session.created") {{
            const session = payload.session;
            state.sessions = [session, ...state.sessions.filter((item) => item.id !== session.id)].slice(0, 20);
            state.schedules = state.schedules.map((schedule) =>
              schedule.id === payload.schedule.id ? payload.schedule : schedule
            );
            renderSchedules();
            renderHistory();
            renderLatest();
            if (payload.schedule?.notification_enabled) {{
              notifyBrowser(session);
            }}
          }}
        }};
      }}

      renderRuntimeInfo();
      setHistoryCollapsed(false);
      setTemplatesCollapsed(false);
      setSchedulesCollapsed(false);

      loadAll().then(connectLive).catch((error) => {{
        connectionStatus.textContent = "Load failed";
        latestResultEl.innerHTML = `<pre>${{escapeHtml(error.message)}}</pre>`;
      }});
    </script>
  </body>
</html>
"""
    html = html.replace("{{", "{").replace("}}", "}")
    return html.replace("__SETTINGS_JSON__", settings_json)
