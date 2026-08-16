from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

log = logging.getLogger("jellyplexsync")

PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>jelly-plex-sync</title>
  <style>
    :root {
      --bg: #0f1419;
      --panel: #1a222c;
      --text: #e8eef4;
      --muted: #8b9aab;
      --accent: #3d9cf0;
      --ok: #3ecf8e;
      --dry: #c084fc;
      --line: #2a3542;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", system-ui, sans-serif;
      background: radial-gradient(1200px 600px at 10% -10%, #1b2a3a, var(--bg));
      color: var(--text);
      min-height: 100vh;
    }
    main { max-width: 1100px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }
    h1 { margin: 0 0 .35rem; font-size: 1.75rem; letter-spacing: -.02em; }
    .sub { color: var(--muted); margin-bottom: 1.5rem; }
    .row { display: flex; flex-wrap: wrap; gap: .75rem; margin-bottom: 1.25rem; align-items: center; }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: .9rem 1rem;
      min-width: 140px;
    }
    .card .label { color: var(--muted); font-size: .8rem; }
    .card .value { font-size: 1.35rem; font-weight: 650; margin-top: .2rem; }
    .badge {
      display: inline-block;
      padding: .2rem .55rem;
      border-radius: 999px;
      font-size: .75rem;
      font-weight: 600;
    }
    .badge.dry { background: color-mix(in srgb, var(--dry) 25%, transparent); color: #e9d5ff; }
    .badge.live { background: color-mix(in srgb, var(--ok) 22%, transparent); color: #bbf7d0; }
    .badge.err { background: #7f1d1d; color: #fecaca; }
    .badge.run { background: #1e3a5f; color: #93c5fd; }
    .badge.on { background: color-mix(in srgb, var(--accent) 30%, transparent); color: #bfdbfe; }
    .change {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 1rem 1.1rem;
      margin-bottom: .75rem;
    }
    .change h3 { margin: 0 0 .55rem; font-size: 1.05rem; display: flex; flex-wrap: wrap; gap: .4rem; align-items: center; }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: .55rem .9rem;
      font-size: .92rem;
    }
    .grid .k { color: var(--muted); font-size: .75rem; text-transform: uppercase; letter-spacing: .03em; }
    .grid .v { margin-top: .15rem; font-family: ui-monospace, Consolas, monospace; font-size: .88rem; }
    .dir { color: var(--accent); font-family: ui-monospace, Consolas, monospace; font-size: .85rem; }
    .muted { color: var(--muted); }
    .empty { padding: 2rem; text-align: center; color: var(--muted); border: 1px dashed var(--line); border-radius: 12px; }
    button {
      background: var(--accent);
      color: #041018;
      border: 0;
      border-radius: 8px;
      padding: .55rem .9rem;
      font-weight: 650;
      cursor: pointer;
    }
    button.secondary { background: #334155; color: var(--text); }
    button.active { outline: 2px solid var(--accent); }
    button.apply { background: var(--ok); margin-top: .75rem; }
    button:disabled { opacity: .5; cursor: not-allowed; }
    h2 { margin: 2rem 0 .75rem; font-size: 1.1rem; }
    #toast { color: var(--muted); }
    .hidden { display: none !important; }
  </style>
</head>
<body>
  <main>
    <h1>jelly-plex-sync</h1>
    <p class="sub">Bei Dry Run: einzelne Eintraege gezielt mit „Jetzt durchfuehren“ schreiben.</p>
    <div class="row" id="meta"></div>
    <div class="row">
      <button type="button" onclick="syncNow()">Jetzt synchronisieren</button>
      <button type="button" class="secondary" id="btnChanges" onclick="toggleChangesOnly()">Nur durchzufuehrende Aenderungen</button>
      <button type="button" class="secondary" onclick="loadReport()">Aktualisieren</button>
      <span id="toast"></span>
    </div>
    <div id="overviewBlock">
      <h2>Kurzuebersicht</h2>
      <div id="overview"></div>
      <h2>Neu erkannte Titel</h2>
      <div id="newitems"></div>
    </div>
    <div id="changesBlock" class="hidden">
      <h2>Durchzufuehrende Aenderungen <span id="changesCount" class="badge on"></span></h2>
      <div id="changes"></div>
    </div>
  </main>
  <script>
    let lastData = null;
    let changesOnly = false;

    function fmtSec(s) {
      s = Math.max(0, Math.round(Number(s) || 0));
      const m = Math.floor(s / 60), r = s % 60;
      return m + ":" + String(r).padStart(2, "0");
    }
    function esc(t) {
      return String(t ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }
    function stateLabel(played, position) {
      if (played) return "gesehen";
      return "Position " + fmtSec(position) + " (" + Math.round(Number(position) || 0) + "s)";
    }
    function toggleChangesOnly() {
      changesOnly = !changesOnly;
      document.getElementById("btnChanges").classList.toggle("active", changesOnly);
      document.getElementById("btnChanges").textContent = changesOnly
        ? "Zurueck zur Uebersicht"
        : "Nur durchzufuehrende Aenderungen";
      render();
    }
    async function syncNow() {
      document.getElementById("toast").textContent = "Sync wird gestartet…";
      const res = await fetch("/api/sync-now", { method: "POST" });
      const data = await res.json();
      document.getElementById("toast").textContent = data.message || "";
      setTimeout(loadReport, 2000);
      setTimeout(loadReport, 8000);
    }
    async function applyOne(actionId, btn) {
      if (!confirm("Diesen einen Eintrag jetzt wirklich schreiben?")) return;
      btn.disabled = true;
      btn.textContent = "schreibt…";
      try {
        const res = await fetch("/api/apply", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action_id: actionId })
        });
        const data = await res.json();
        document.getElementById("toast").textContent = data.message || "";
        await loadReport();
      } catch (e) {
        document.getElementById("toast").textContent = String(e);
        btn.disabled = false;
        btn.textContent = "Jetzt durchfuehren";
      }
    }
    function renderChanges(actions) {
      const box = document.getElementById("changes");
      const pending = actions.filter(a => !a.applied);
      document.getElementById("changesCount").textContent = String(pending.length) + " offen / " + actions.length;
      if (!actions.length) {
        box.innerHTML = '<div class="empty">Keine durchzufuehrenden Aenderungen in diesem Lauf.</div>';
        return;
      }
      box.innerHTML = actions.map((a, i) => {
        const canApply = !a.applied && a.dest_item_id;
        const applyBtn = a.applied
          ? '<span class="badge live">bereits durchgefuehrt</span>'
          : (canApply
            ? `<button type="button" class="apply" onclick="applyOne('${esc(a.id)}', this)">Jetzt durchfuehren</button>`
            : '<span class="muted">Bitte Sync erneut – Eintrag ohne IDs (altes Image)</span>');
        return `
        <article class="change">
          <h3>${i + 1}. ${esc(a.title)}
            ${a.applied ? '<span class="badge live">geschrieben</span>' : '<span class="badge dry">Dry Run</span>'}
          </h3>
          <div class="grid">
            <div><div class="k">Richtung</div><div class="v dir">${esc(a.source_server)} → ${esc(a.dest_server)}</div></div>
            <div><div class="k">Aktion</div><div class="v">${esc(a.reason)}</div></div>
            <div><div class="k">Typ</div><div class="v">${esc(a.kind)}</div></div>
            <div><div class="k">Bibliothek</div><div class="v">${esc(a.library)}</div></div>
            <div><div class="k">Benutzer</div><div class="v">${esc(a.user || "—")}</div></div>
            <div><div class="k">Quelle (${esc(a.source_server)})</div><div class="v">${stateLabel(a.source_played, a.source_position)}</div></div>
            <div><div class="k">Ziel vorher (${esc(a.dest_server)})</div><div class="v">${stateLabel(a.dest_played, a.dest_position)}</div></div>
            <div><div class="k">Ziel nachher</div><div class="v">${
              a.target_played || a.reason === "mark watched"
                ? "gesehen"
                : "Position " + fmtSec(a.target_position || a.source_position)
            }</div></div>
            <div><div class="k">Dest Item ID</div><div class="v">${esc(a.dest_item_id || "—")}</div></div>
          </div>
          ${applyBtn}
        </article>`;
      }).join("");
    }
    function render() {
      if (!lastData) return;
      const data = lastData;
      const stats = data.stats || {};
      const actions = data.actions || [];
      const badge = data.dry_run
        ? '<span class="badge dry">DRY RUN</span>'
        : '<span class="badge live">LIVE</span>';
      const runBadge = data.runner_status === "running"
        ? '<span class="badge run">laeuft…</span>'
        : (data.ok === false || data.runner_status === "error"
          ? '<span class="badge err">Fehler</span>' : '');
      document.getElementById("meta").innerHTML = `
        <div class="card"><div class="label">Modus</div><div class="value">${badge} ${runBadge}</div></div>
        <div class="card"><div class="label">Aenderungen</div><div class="value">${actions.length}</div></div>
        <div class="card"><div class="label">Noch offen</div><div class="value">${actions.filter(a => !a.applied).length}</div></div>
        <div class="card"><div class="label">Plex → JF</div><div class="value">${stats.updated_jellyfin ?? 0}</div></div>
        <div class="card"><div class="label">JF → Plex</div><div class="value">${stats.updated_plex ?? 0}</div></div>
        <div class="card"><div class="label">Letzter Lauf</div><div class="value" style="font-size:.95rem">${esc(data.finished_at || data.message || "—")}</div></div>
      `;
      const err = data.error || data.runner_error;
      if (err) {
        document.getElementById("meta").innerHTML += `<div class="card" style="flex:1 1 100%"><div class="label">Fehler</div><div class="value" style="font-size:1rem;color:#fecaca">${esc(err)}</div></div>`;
      }

      document.getElementById("overviewBlock").classList.toggle("hidden", changesOnly);
      document.getElementById("changesBlock").classList.toggle("hidden", !changesOnly);

      if (changesOnly) {
        renderChanges(actions);
        return;
      }

      const overview = document.getElementById("overview");
      if (!data.finished_at && !err) {
        overview.innerHTML = '<div class="empty">Noch kein Sync. Klicke „Jetzt synchronisieren“.</div>';
      } else if (!actions.length) {
        overview.innerHTML = '<div class="empty">Keine Aenderungen in diesem Lauf.</div>';
      } else {
        overview.innerHTML = `<div class="empty">${actions.length} Aenderung(en), davon ${actions.filter(a => !a.applied).length} noch offen.
          <br><br><button type="button" onclick="toggleChangesOnly()">Details + einzeln durchfuehren</button></div>`;
      }
      const news = data.new_items || [];
      document.getElementById("newitems").innerHTML = news.length
        ? `<p class="muted">${news.length} Eintraege (max. 20)</p><table style="width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden">
            <thead><tr><th style="text-align:left;padding:.7rem;color:var(--muted)">Server</th><th style="text-align:left;padding:.7rem;color:var(--muted)">Titel</th></tr></thead>
            <tbody>${news.slice(0,20).map(n => `<tr><td class="dir" style="padding:.55rem .7rem">${esc(n.server)}</td><td style="padding:.55rem .7rem">${esc(n.title)}</td></tr>`).join("")}</tbody></table>`
        : '<div class="empty">Keine neu erkannten Titel.</div>';
    }
    async function loadReport() {
      const res = await fetch("/api/report");
      lastData = await res.json();
      render();
    }
    loadReport();
    setInterval(loadReport, 5000);
  </script>
</body>
</html>
"""


def start_web(runner, host: str, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            log.debug("web: " + fmt, *args)

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8") or "{}")

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path in {"/", "/index.html"}:
                self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/api/report":
                payload = json.dumps(runner.snapshot()).encode("utf-8")
                self._send(200, payload, "application/json; charset=utf-8")
                return
            if path == "/health":
                self._send(200, b"ok", "text/plain")
                return
            self._send(404, b"not found", "text/plain")

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/api/sync-now":
                payload = json.dumps(runner.request_now()).encode("utf-8")
                self._send(200, payload, "application/json; charset=utf-8")
                return
            if path == "/api/apply":
                body = self._read_json()
                action_id = str(body.get("action_id") or "")
                payload = json.dumps(runner.apply_action(action_id)).encode("utf-8")
                self._send(200, payload, "application/json; charset=utf-8")
                return
            self._send(404, b"not found", "text/plain")

    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, name="web", daemon=True)
    thread.start()
    log.info("Web-UI auf http://%s:%s (nur LAN, nicht ins Internet freigeben)", host, port)
    return server
