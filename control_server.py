"""
Personal AI OS — control server + always-on supervisor.

ONE command starts everything and gives you a web page to watch it:

    python control_server.py

Then open http://localhost:8800  (the START launcher opens it for you).

What it does:
  * Boots `main.py` (the capture -> Google Sheet engine) as a child process.
  * Supervises it: if the engine ever dies, it is restarted automatically,
    so listening + Sheet syncing keep running with no missed tasks.
  * Serves a live status dashboard (engine up/down, uptime, task counts,
    unsynced backlog, recent log) and Start / Stop / Restart buttons.

Pure standard library — no extra pip installs needed to run this file.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGS_DIR = ROOT / "logs"
RUNNER_LOG = LOGS_DIR / "runner.log"
WEB_DIR = ROOT / "web"

# ---------------------------------------------------------------------------
# Minimal .env reader (so we don't depend on python-dotenv just to show links)
# ---------------------------------------------------------------------------

def read_env() -> dict[str, str]:
    env: dict[str, str] = {}
    f = ROOT / ".env"
    if not f.exists():
        return env
    try:
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            val = val.strip().strip('"').strip("'")
            env[key.strip()] = val
    except Exception:
        pass
    return env


ENV = read_env()
SHEET_ID = ENV.get("GOOGLE_SHEET_ID", "")
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit" if SHEET_ID else ""
DB_PATH = ROOT / ENV.get("DATABASE_PATH", "./data/personal_ai_os.db").lstrip("./")


def venv_python() -> str:
    """Prefer the project virtualenv interpreter on either OS, else current."""
    candidates = [
        ROOT / ".venv" / "Scripts" / "python.exe",   # Windows
        ROOT / ".venv" / "bin" / "python",            # macOS / Linux
        ROOT / "venv" / "Scripts" / "python.exe",
        ROOT / "venv" / "bin" / "python",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return sys.executable


# ---------------------------------------------------------------------------
# Engine supervisor
# ---------------------------------------------------------------------------

class Supervisor:
    """Keeps main.py alive. Restarts it automatically unless stopped on purpose."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.proc: subprocess.Popen | None = None
        self.desired_running = False
        self.started_at: float | None = None
        self.restart_count = 0
        self.last_exit_code: int | None = None
        self._lock = threading.Lock()
        LOGS_DIR.mkdir(exist_ok=True)

    def is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self) -> None:
        with self._lock:
            self.desired_running = True
            if self.is_running():
                return
            main_py = ROOT / "main.py"
            if not main_py.exists():
                self._log("ERROR: main.py not found; cannot start engine.")
                return
            py = venv_python()
            self._log(f"Starting engine: {py} main.py")
            logf = open(RUNNER_LOG, "a", encoding="utf-8", errors="replace")
            self.proc = subprocess.Popen(
                [py, "main.py"],
                cwd=str(ROOT),
                stdout=logf,
                stderr=subprocess.STDOUT,
            )
            self.started_at = time.time()

    def stop(self) -> None:
        with self._lock:
            self.desired_running = False
            if self.proc and self.proc.poll() is None:
                self._log("Stopping engine (manual).")
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            self.proc = None
            self.started_at = None

    def restart(self) -> None:
        self.stop()
        time.sleep(1)
        self.start()

    def monitor_loop(self) -> None:
        """Background watchdog: bring the engine back if it dies unexpectedly."""
        backoff = 2
        while True:
            time.sleep(2)
            if not self.desired_running:
                continue
            if not self.is_running():
                if self.proc is not None:
                    self.last_exit_code = self.proc.returncode
                    self._log(
                        f"Engine exited (code {self.last_exit_code}); "
                        f"restarting in {backoff}s (restart #{self.restart_count + 1})."
                    )
                self.restart_count += 1
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)  # exponential backoff, capped
                self.start()
            else:
                backoff = 2  # healthy -> reset backoff

    def _log(self, msg: str) -> None:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{stamp}] [supervisor] {msg}"
        print(line, flush=True)
        try:
            with open(RUNNER_LOG, "a", encoding="utf-8", errors="replace") as fh:
                fh.write(line + "\n")
        except Exception:
            pass


SUP = Supervisor()


# ---------------------------------------------------------------------------
# Status helpers (read-only DB peek; never blocks the engine's writes)
# ---------------------------------------------------------------------------

def db_stats() -> dict:
    out = {"total_tasks": None, "unsynced": None, "last_task": None, "db_ok": False}
    if not DB_PATH.exists():
        return out
    try:
        uri = f"file:{DB_PATH.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=2)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM extracted_tasks")
        out["total_tasks"] = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM extracted_tasks WHERE synced_to_sheets = 0")
        out["unsynced"] = cur.fetchone()["c"]
        try:
            cur.execute("SELECT MAX(created_at) AS m FROM extracted_tasks")
            out["last_task"] = cur.fetchone()["m"]
        except sqlite3.Error:
            pass
        out["db_ok"] = True
        conn.close()
    except Exception:
        pass
    return out


def log_tail(n: int = 25) -> list[str]:
    if not RUNNER_LOG.exists():
        return []
    try:
        lines = RUNNER_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-n:]
    except Exception:
        return []


def status_payload() -> dict:
    stats = db_stats()
    uptime = int(time.time() - SUP.started_at) if (SUP.is_running() and SUP.started_at) else 0
    return {
        "running": SUP.is_running(),
        "desired_running": SUP.desired_running,
        "pid": SUP.proc.pid if SUP.is_running() else None,
        "uptime_seconds": uptime,
        "restart_count": SUP.restart_count,
        "last_exit_code": SUP.last_exit_code,
        "sheet_url": SHEET_URL,
        "sheet_configured": bool(SHEET_ID),
        "db": stats,
        "log_tail": log_tail(),
    }


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

DASHBOARD = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Personal AI OS — Control</title>
<style>
  :root{--bg:#0b0f17;--panel:#121826;--line:#1f2937;--ink:#e6edf5;--dim:#93a1b5;
    --accent:#6366f1;--ok:#22c55e;--warn:#f59e0b;--bad:#ef4444;--radius:14px}
  *{box-sizing:border-box;margin:0;padding:0;font-family:'Inter',system-ui,Segoe UI,Roboto,sans-serif}
  body{background:radial-gradient(1100px 500px at 12% -8%,rgba(99,102,241,.12),transparent 60%),var(--bg);
    color:var(--ink);min-height:100vh;padding:28px clamp(16px,4vw,40px)}
  h1{font-size:22px;font-weight:800;display:flex;align-items:center;gap:12px}
  .logo{width:34px;height:34px;border-radius:9px;background:linear-gradient(135deg,#6366f1,#8b5cf6);
    display:grid;place-items:center;font-weight:800;font-size:14px}
  .sub{color:var(--dim);font-size:12.5px;margin-top:4px;letter-spacing:.04em}
  .statusbar{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:24px 0 18px}
  .pill{display:inline-flex;align-items:center;gap:9px;font-weight:800;font-size:15px;
    padding:11px 18px;border-radius:999px;border:1px solid var(--line)}
  .pill .dot{width:11px;height:11px;border-radius:50%}
  .pill.on{background:rgba(34,197,94,.12);color:#86efac;border-color:rgba(34,197,94,.4)}
  .pill.on .dot{background:var(--ok);box-shadow:0 0 0 0 rgba(34,197,94,.6);animation:pulse 1.6s infinite}
  .pill.off{background:rgba(239,68,68,.10);color:#fca5a5;border-color:rgba(239,68,68,.4)}
  .pill.off .dot{background:var(--bad)}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(34,197,94,.5)}70%{box-shadow:0 0 0 9px rgba(34,197,94,0)}100%{box-shadow:0 0 0 0 rgba(34,197,94,0)}}
  button{cursor:pointer;font-weight:700;font-size:13.5px;border-radius:10px;padding:11px 16px;border:1px solid var(--line);
    background:#0e1420;color:var(--ink);transition:.15s}
  button:hover{border-color:var(--accent)}
  button.primary{background:linear-gradient(135deg,#6366f1,#8b5cf6);border:0;color:#fff}
  button.danger:hover{border-color:var(--bad);color:#fca5a5}
  a.linkbtn{text-decoration:none}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:8px 0 22px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:18px}
  .card .k{color:var(--dim);font-size:11px;letter-spacing:.12em;text-transform:uppercase}
  .card .v{font-size:26px;font-weight:800;margin-top:8px}
  .card.warn .v{color:var(--warn)}
  .card.ok .v{color:var(--ok)}
  .logbox{background:#080b11;border:1px solid var(--line);border-radius:var(--radius);padding:14px 16px;
    font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;line-height:1.6;color:#9fb0c4;
    max-height:300px;overflow:auto;white-space:pre-wrap}
  .links{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:22px}
  .note{color:var(--dim);font-size:12px;margin-top:6px}
</style></head>
<body>
  <h1><span class="logo">AI</span> Personal AI OS — Control</h1>
  <div class="sub" id="clock">listening &amp; syncing to Google Sheets · supervised, auto-restarts</div>

  <div class="statusbar">
    <span class="pill off" id="pill"><span class="dot"></span><span id="pillText">Checking…</span></span>
    <button class="primary" onclick="act('start')">▶ Start</button>
    <button class="danger" onclick="act('stop')">■ Stop</button>
    <button onclick="act('restart')">↻ Restart</button>
  </div>

  <div class="links">
    <a class="linkbtn" id="sheetLink" target="_blank"><button>📊 Open Google Sheet</button></a>
    <a class="linkbtn" href="/board" target="_blank"><button>🗂 Open Task Board</button></a>
  </div>

  <div class="grid">
    <div class="card"><div class="k">Uptime</div><div class="v" id="uptime">—</div></div>
    <div class="card"><div class="k">Total tasks captured</div><div class="v" id="total">—</div></div>
    <div class="card" id="unsyncedCard"><div class="k">Unsynced backlog</div><div class="v" id="unsynced">—</div></div>
    <div class="card"><div class="k">Auto-restarts</div><div class="v" id="restarts">—</div></div>
  </div>

  <div class="logbox" id="log">loading log…</div>
  <div class="note" id="dbnote"></div>

<script>
function fmtUptime(s){if(!s)return'—';var h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;
  return (h?h+'h ':'')+(m?m+'m ':'')+x+'s';}
async function refresh(){
  try{
    const r=await fetch('/api/status'); const d=await r.json();
    const pill=document.getElementById('pill'),pt=document.getElementById('pillText');
    if(d.running){pill.className='pill on';pt.textContent='ENGINE RUNNING'+(d.pid?(' · pid '+d.pid):'');}
    else{pill.className='pill off';pt.textContent= d.desired_running?'ENGINE DOWN — restarting…':'ENGINE STOPPED';}
    document.getElementById('uptime').textContent=fmtUptime(d.uptime_seconds);
    document.getElementById('total').textContent=(d.db.total_tasks??'—');
    document.getElementById('restarts').textContent=d.restart_count;
    const u=d.db.unsynced, uc=document.getElementById('unsyncedCard');
    document.getElementById('unsynced').textContent=(u??'—');
    uc.className='card '+(u>0?'warn':(u===0?'ok':''));
    const sl=document.getElementById('sheetLink');
    if(d.sheet_url){sl.href=d.sheet_url;sl.style.display='';}else{sl.style.display='none';}
    document.getElementById('log').textContent=(d.log_tail||[]).join('\\n')||'(no log yet)';
    document.getElementById('dbnote').textContent = d.db.db_ok?'':'Note: task database not found yet — it is created on first capture.';
  }catch(e){document.getElementById('pillText').textContent='control server unreachable';}
}
async function act(a){await fetch('/api/'+a,{method:'POST'});setTimeout(refresh,400);}
refresh();setInterval(refresh,3000);
</script>
</body></html>
"""


import importlib.util

_board_mod = None
_board_lock = threading.Lock()
_board_built_at = 0.0


def _board_module():
    """Lazy-load web/build_board.py as a module so we can call main() in-process."""
    global _board_mod
    if _board_mod is None:
        spec = importlib.util.spec_from_file_location(
            "build_board", str(WEB_DIR / "build_board.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _board_mod = mod
    return _board_mod


def refresh_board(min_interval: float = 5.0) -> None:
    """
    Regenerate web/data.json from the live SQLite DB so the Kanban board
    reflects newly-extracted tasks. Throttled to once per `min_interval`
    seconds so rapid polling can't hammer the DB. Never raises.
    """
    global _board_built_at
    with _board_lock:
        now = time.time()
        if now - _board_built_at < min_interval:
            return
        try:
            _board_module().main()
            _board_built_at = now
        except Exception as exc:  # board is best-effort; engine keeps running
            print(f"[board] data.json refresh failed: {exc}")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/" or path == "/index.html":
            self._send(200, DASHBOARD.encode("utf-8"))
        elif path == "/api/status":
            self._send(200, json.dumps(status_payload()).encode("utf-8"),
                       "application/json; charset=utf-8")
        elif path == "/board":
            self._serve_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
        elif path == "/data.json":
            refresh_board()  # regenerate from the live DB (throttled) before serving
            self._serve_file(WEB_DIR / "data.json", "application/json; charset=utf-8")
        else:
            self._send(404, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/start":
            SUP.start(); self._send(200, b'{"ok":true}', "application/json")
        elif path == "/api/stop":
            SUP.stop(); self._send(200, b'{"ok":true}', "application/json")
        elif path == "/api/restart":
            threading.Thread(target=SUP.restart, daemon=True).start()
            self._send(200, b'{"ok":true}', "application/json")
        else:
            self._send(404, b"Not found", "text/plain; charset=utf-8")

    def _serve_file(self, fp: Path, ctype: str):
        if fp.exists():
            self._send(200, fp.read_bytes(), ctype)
        else:
            self._send(404, f"{fp.name} not generated yet".encode(), "text/plain; charset=utf-8")

    def log_message(self, *args):  # silence default per-request stderr spam
        pass


def main():
    ap = argparse.ArgumentParser(description="Personal AI OS control server + supervisor")
    ap.add_argument("--port", type=int, default=8800)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-engine", action="store_true",
                    help="serve the dashboard only; do not auto-start main.py")
    args = ap.parse_args()

    threading.Thread(target=SUP.monitor_loop, daemon=True).start()
    if not args.no_engine:
        SUP.start()
    refresh_board(min_interval=0)  # ensure data.json is current at boot

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://localhost:{args.port}"
    print("=" * 60)
    print("  Personal AI OS — control server")
    print(f"  Dashboard : {url}")
    print(f"  Engine    : {'OFF (--no-engine)' if args.no_engine else 'starting + supervised'}")
    print(f"  Sheet     : {SHEET_URL or '(GOOGLE_SHEET_ID not set in .env)'}")
    print("  Press Ctrl+C to stop the control server (engine stops too).")
    print("=" * 60)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down…")
    finally:
        SUP.stop()
        httpd.server_close()


if __name__ == "__main__":
    main()
