#!/usr/bin/env python3
"""
install_autostart.py — cross-platform autostart installer for Personal AI OS.

Detects the OS (Windows / macOS / Linux) and registers `control_server.py`
(the supervisor that boots main.py + serves the dashboard on :8800) to launch
automatically every time you log in, and keep running in the background.

Run the SAME command on any machine — it figures out the rest:

    python install_autostart.py            # install + start on every login
    python install_autostart.py uninstall  # remove autostart
    python install_autostart.py status     # show whether it's installed

Works whether you use a .venv (preferred) or the system Python.
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LABEL = "com.anchit.personal-ai-os"
TARGET = ROOT / "control_server.py"


def _venv_python(*, windowless: bool) -> str:
    """Prefer the project venv; pick pythonw on Windows to avoid a console window."""
    if os.name == "nt":
        cand = [
            ROOT / ".venv" / "Scripts" / ("pythonw.exe" if windowless else "python.exe"),
            ROOT / "venv" / "Scripts" / ("pythonw.exe" if windowless else "python.exe"),
        ]
    else:
        cand = [ROOT / ".venv" / "bin" / "python", ROOT / "venv" / "bin" / "python"]
    for p in cand:
        if p.exists():
            return str(p)
    # Fall back to whatever Python is running this installer.
    return sys.executable


# ----------------------------- macOS -----------------------------------------
def _mac_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def mac_install() -> None:
    py = _venv_python(windowless=False)
    (ROOT / "logs").mkdir(exist_ok=True)
    plist = _mac_plist_path()
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{py}</string>
    <string>{TARGET}</string>
  </array>
  <key>WorkingDirectory</key><string>{ROOT}</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>{ROOT / 'logs' / 'control_server.out.log'}</string>
  <key>StandardErrorPath</key><string>{ROOT / 'logs' / 'control_server.err.log'}</string>
</dict></plist>
""",
        encoding="utf-8",
    )
    subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
    subprocess.run(["launchctl", "load", str(plist)], check=True)
    print(f"✓ Installed macOS LaunchAgent ({LABEL})")
    print(f"  python : {py}")
    print(f"  logs   : {ROOT / 'logs'}/control_server.{{out,err}}.log")
    print("  dashboard once up: http://localhost:8800")


def mac_uninstall() -> None:
    plist = _mac_plist_path()
    subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
    plist.unlink(missing_ok=True)
    print(f"✓ Removed macOS LaunchAgent ({LABEL})")


def mac_status() -> None:
    r = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    print("installed + loaded" if LABEL in r.stdout else "not installed")


# ----------------------------- Windows ---------------------------------------
def _win_startup_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _win_launcher_bat() -> Path:
    return _win_startup_dir() / "PersonalAIOS.bat"


def win_install() -> None:
    py = _venv_python(windowless=True)
    (ROOT / "logs").mkdir(exist_ok=True)
    bat = _win_launcher_bat()
    bat.parent.mkdir(parents=True, exist_ok=True)
    # Startup-folder .bat: cd into the project, launch windowless, log output.
    bat.write_text(
        "@echo off\r\n"
        f'cd /d "{ROOT}"\r\n'
        f'start "" /b "{py}" "{TARGET}" '
        f'> "{ROOT / "logs" / "control_server.out.log"}" '
        f'2> "{ROOT / "logs" / "control_server.err.log"}"\r\n',
        encoding="utf-8",
    )
    # Also kick it off now so the user doesn't have to log out/in first.
    subprocess.Popen(["cmd", "/c", str(bat)], cwd=str(ROOT))
    print("✓ Installed Windows autostart (Startup folder)")
    print(f"  launcher : {bat}")
    print(f"  python   : {py}")
    print(f"  logs     : {ROOT / 'logs'}\\control_server.{{out,err}}.log")
    print("  dashboard once up: http://localhost:8800")


def win_uninstall() -> None:
    _win_launcher_bat().unlink(missing_ok=True)
    print("✓ Removed Windows autostart")


def win_status() -> None:
    print("installed" if _win_launcher_bat().exists() else "not installed")


# ----------------------------- Linux (bonus) ---------------------------------
def _linux_unit_path() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / "personal-ai-os.service"


def linux_install() -> None:
    py = _venv_python(windowless=False)
    unit = _linux_unit_path()
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text(
        "[Unit]\nDescription=Personal AI OS\n\n"
        "[Service]\n"
        f"WorkingDirectory={ROOT}\n"
        f"ExecStart={py} {TARGET}\n"
        "Restart=always\n\n"
        "[Install]\nWantedBy=default.target\n",
        encoding="utf-8",
    )
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "--user", "enable", "--now", "personal-ai-os"], check=False)
    print(f"✓ Installed systemd user service at {unit}")
    print("  (run `loginctl enable-linger $USER` to keep it running after logout)")


def linux_uninstall() -> None:
    subprocess.run(["systemctl", "--user", "disable", "--now", "personal-ai-os"], check=False)
    _linux_unit_path().unlink(missing_ok=True)
    print("✓ Removed systemd user service")


def linux_status() -> None:
    r = subprocess.run(
        ["systemctl", "--user", "is-enabled", "personal-ai-os"],
        capture_output=True, text=True,
    )
    print((r.stdout or r.stderr).strip() or "not installed")


# ----------------------------- dispatch --------------------------------------
HANDLERS = {
    "Darwin": (mac_install, mac_uninstall, mac_status),
    "Windows": (win_install, win_uninstall, win_status),
    "Linux": (linux_install, linux_uninstall, linux_status),
}


def main() -> int:
    system = platform.system()
    if system not in HANDLERS:
        print(f"Unsupported OS: {system!r}. Supported: macOS, Windows, Linux.")
        return 2
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found — run this from the Personal-AI-OS folder.")
        return 2

    install, uninstall, status = HANDLERS[system]
    action = (sys.argv[1].lower() if len(sys.argv) > 1 else "install")

    print(f"Detected OS: {system}")
    if action == "install":
        install()
    elif action == "uninstall":
        uninstall()
    elif action == "status":
        status()
    else:
        print(f"Unknown action {action!r}. Use: install | uninstall | status")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
