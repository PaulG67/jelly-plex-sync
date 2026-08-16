from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from jellyplexsync.report import ReportStore

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
      --warn: #f0b429;
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
    .row { display: flex; flex-wrap: wrap; gap: .75rem; margin-bottom: 1.25rem; }
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
    table {
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      overflow: hidden;
    }
    th, td { text-align: left; padding: .7rem .85rem; border-bottom: 1px solid var(--line); vertical-align: top; }
    th { color: var(--muted); font-size: .78rem; text-transform: uppercase; letter-spacing: .04em; }
    tr:last-child td { border-bottom: none; }
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
    h2 { margin: 2rem 0 .75rem; font-size: 1.1rem; }
  </style>
</head>
<body>
  <main>
    <h1>jelly-plex-sync</h1>
    <p class="sub">Lokale Übersicht der letzten Sync-Läufe. Bei Dry Run siehst du hier, was geschrieben würde — ohne Änderungen.</p>
    <div class="row" id="meta"></div>
    <div class="row">
      <button type="button" onclick="loadReport()">Aktualisieren</button>
    </div>
    <h2>Geplante / ausgeführte Aktionen</h2>
    <div id="actions"></div>
    <h2>Neu erkannte Titel</h2>
    <div id="newitems"></div>
  </main>
  <script>
    function fmtSec(s) {
      s = Math.max(0, Math.round(Number(s) || 0));
      const m = Math.floor(s / 60), r = s % 60;
      return m + ":" + String(r).padStart(2, "0");
    }
    function esc(t) {
      return String(t ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }
    async function loadReport() {
      const res = await fetch("/api/report");
      const data = await res.json();
      const meta = document.getElementById("meta");
      const stats = data.stats || {};
      const badge = data.dry_run
        ? '<span class="badge dry">DRY RUN — nichts geschrieben</span>'
        : '<span class="badge live">LIVE — Änderungen geschrieben</span>';
      const status = data.ok === false
        ? '<span class="badge err">Fehler</span>'
        : '';
      meta.innerHTML = `
        <div class="card"><div class="label">Modus</div><div class="value">${badge} ${status}</div></div>
        <div class="card"><div class="label">Aktionen</div><div class="value">${(data.actions||[]).length}</div></div>
        <div class="card"><div class="label">Plex → JF</div><div class="value">${stats.updated_jellyfin ?? 0}</div></div>
        <div class="card"><div class="label">JF → Plex</div><div class="value">${stats.updated_plex ?? 0}</div></div>
        <div class="card"><div class="label">Übersprungen</div><div class="value">${stats.skipped ?? 0}</div></div>
        <div class="card"><div class="label">Neu</div><div class="value">${stats.new_items ?? 0}</div></div>
        <div class="card"><div class="label">Letzter Lauf</div><div class="value" style="font-size:.95rem">${esc(data.finished_at || data.message || "—")}</div></div>
      `;
      if (data.error) {
        meta.innerHTML += `<div class="card" style="flex:1 1 100%"><div class="label">Fehler</div><div class="value" style="font-size:1rem;color:#fecaca">${esc(data.error)}</div></div>`;
      }
      const actions = data.actions || [];
      const box = document.getElementById("actions");
      if (!actions.length) {
        box.innerHTML = '<div class="empty">Keine Aktionen in diesem Lauf. Entweder war alles schon synchron, oder der nächste Scan steht noch aus.</div>';
      } else {
        box.innerHTML = `<table>
          <thead><tr>
            <th>Richtung</th><th>Titel</th><th>Aktion</th><th>Quelle</th><th>Ziel</th>
          </tr></thead>
          <tbody>${actions.map(a => `
            <tr>
              <td class="dir">${esc(a.source_server)} → ${esc(a.dest_server)}</td>
              <td><strong>${esc(a.title)}</strong><div class="muted">${esc(a.kind)} · ${esc(a.library)}${a.user ? " · " + esc(a.user) : ""}</div></td>
              <td>${esc(a.reason)}${a.dry_run ? ' <span class="badge dry">würde</span>' : ''}</td>
              <td class="muted">${a.source_played ? "gesehen" : fmtSec(a.source_position)}</td>
              <td class="muted">${a.dest_played ? "gesehen" : fmtSec(a.dest_position)}</td>
            </tr>`).join("")}</tbody></table>`;
      }
      const news = data.new_items || [];
      const nbox = document.getElementById("newitems");
      if (!news.length) {
        nbox.innerHTML = '<div class="empty">Keine neu erkannten Titel.</div>';
      } else {
        nbox.innerHTML = `<table><thead><tr><th>Server</th><th>Titel</th></tr></thead>
          <tbody>${news.map(n => `<tr><td class="dir">${esc(n.server)}</td><td>${esc(n.title)}</td></tr>`).join("")}</tbody></table>`;
      }
    }
    loadReport();
    setInterval(loadReport, 15000);
  </script>
</body>
</html>
"""


def start_web(report_store: ReportStore, host: str, port: int) -> ThreadingHTTPServer:
    store = report_store

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

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path in {"/", "/index.html"}:
                self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/api/report":
                payload = json.dumps(store.latest()).encode("utf-8")
                self._send(200, payload, "application/json; charset=utf-8")
                return
            if path == "/health":
                healthy = Path(store.path).parent / "healthy"
                if healthy.exists():
                    self._send(200, b"ok", "text/plain")
                else:
                    self._send(503, b"starting", "text/plain")
                return
            self._send(404, b"not found", "text/plain")

    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, name="web", daemon=True)
    thread.start()
    log.info("Web-UI auf http://%s:%s (nur LAN, nicht ins Internet freigeben)", host, port)
    return server
