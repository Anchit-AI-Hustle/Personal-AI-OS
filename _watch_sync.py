"""
Watch the unsynced-task count drain. One stdout line per state change so
the Monitor tool surfaces meaningful events without spam. Exits 0 when
unsynced hits 0, exits 1 if it stalls for too long.
"""
import io, sqlite3, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from config import settings

POLL_SECS = 20
STALL_LIMIT_POLLS = 12   # 12 * 20s = 4 min with no progress -> warn
MAX_RUNTIME_SECS = 30 * 60

conn = sqlite3.connect(settings.database_path)

def state():
    u = conn.execute("SELECT COUNT(*) FROM extracted_tasks WHERE synced_to_sheets=0").fetchone()[0]
    s = conn.execute("SELECT COUNT(*) FROM extracted_tasks WHERE synced_to_sheets=1").fetchone()[0]
    return u, s

u, s = state()
print(f"START unsynced={u} synced={s}", flush=True)
last_u = u
stall_polls = 0
started = time.monotonic()

while True:
    if u == 0:
        print(f"DONE all tasks synced. final synced={s}", flush=True)
        sys.exit(0)
    if time.monotonic() - started > MAX_RUNTIME_SECS:
        print(f"TIMEOUT after 30 min; unsynced={u} synced={s}", flush=True)
        sys.exit(1)

    time.sleep(POLL_SECS)
    u, s = state()
    if u != last_u:
        delta = last_u - u
        print(f"PROGRESS unsynced={u} synced={s} (-{delta} this tick)", flush=True)
        last_u = u
        stall_polls = 0
    else:
        stall_polls += 1
        if stall_polls % STALL_LIMIT_POLLS == 0:
            mins = (stall_polls * POLL_SECS) // 60
            print(f"STALLED no change in {mins} min; unsynced={u}", flush=True)
