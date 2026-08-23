import os
import subprocess
import time
from functools import wraps

from dotenv import dotenv_values, load_dotenv, set_key
from flask import Flask, Response, redirect, render_template_string, request, url_for

load_dotenv()

APP_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(APP_DIR, "bot.log")
ENV_PATH = os.path.join(APP_DIR, ".env")

WEBUI_HOST = os.environ.get("WEBUI_HOST", "127.0.0.1")
WEBUI_PORT = int(os.environ.get("WEBUI_PORT", "8080"))
WEBUI_PASSWORD = os.environ.get("WEBUI_PASSWORD") or None

app = Flask(__name__)

PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Admin View</title>
<style>
  :root {
    --bg: #0f1115;
    --card: #171a21;
    --card-border: #262a35;
    --text: #e6e8ec;
    --muted: #8b93a7;
    --accent: #4f8cff;
    --accent-hover: #3d75e0;
    --green: #35c471;
    --green-bg: rgba(53, 196, 113, .12);
    --red: #ff5c5c;
    --red-bg: rgba(255, 92, 92, .12);
    --amber: #f5b942;
    --amber-bg: rgba(245, 185, 66, .12);
    --blue-bg: rgba(79, 140, 255, .12);
    --radius: 14px;
  }
  * { box-sizing: border-box; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    max-width: 640px;
    margin: 0 auto;
    padding: 1.5rem 1rem 3rem;
    line-height: 1.5;
  }
  h1 {
    font-size: 1.4rem;
    display: flex;
    align-items: center;
    gap: .5rem;
    margin-bottom: 1.25rem;
  }
  h3 {
    font-size: .95rem;
    text-transform: uppercase;
    letter-spacing: .04em;
    color: var(--muted);
    margin: 1.75rem 0 .75rem;
  }
  .card {
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
    padding: 1.1rem 1.2rem;
    margin-bottom: 1rem;
  }
  .badge {
    padding: .35rem .8rem;
    border-radius: 999px;
    display: inline-flex;
    align-items: center;
    gap: .4rem;
    font-weight: 600;
    font-size: .85rem;
  }
  .badge.running { background: var(--green-bg); color: var(--green); }
  .badge.stopped { background: var(--red-bg); color: var(--red); }
  .dot { width: .5rem; height: .5rem; border-radius: 50%; background: currentColor; }
  .banner {
    padding: .7rem 1rem;
    border-radius: 10px;
    margin-bottom: 1rem;
    font-size: .9rem;
  }
  .banner.warning { background: var(--amber-bg); color: var(--amber); }
  .banner.info { background: var(--blue-bg); color: var(--accent); }
  .actions { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .9rem; }
  button {
    appearance: none;
    border: none;
    border-radius: 10px;
    padding: .65rem 1.1rem;
    font-size: .92rem;
    font-weight: 600;
    cursor: pointer;
    background: #232733;
    color: var(--text);
    transition: background .15s ease;
  }
  button:hover:not(:disabled) { background: #2c313f; }
  button:disabled { opacity: .4; cursor: not-allowed; }
  button.primary { background: var(--accent); color: #fff; }
  button.primary:hover:not(:disabled) { background: var(--accent-hover); }
  button.danger { background: var(--red-bg); color: var(--red); }
  button.danger:hover:not(:disabled) { background: rgba(255, 92, 92, .22); }
  button.small { padding: .4rem .8rem; font-size: .8rem; }
  form.inline { display: inline; }
  .add-form { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .5rem; }
  .add-form input[type=text] { min-width: 140px; }
  .uid-muted { color: var(--muted); font-weight: 400; font-size: .85rem; }
  input[type=text] {
    flex: 1;
    padding: .6rem .8rem;
    border-radius: 10px;
    border: 1px solid var(--card-border);
    background: #10131a;
    color: var(--text);
    font-size: .95rem;
  }
  input[type=text]:focus { outline: 2px solid var(--accent); }
  ul.whitelist { list-style: none; padding: 0; margin: 0; }
  ul.whitelist li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: .5rem;
    padding: .55rem 0;
    border-bottom: 1px solid var(--card-border);
    font-variant-numeric: tabular-nums;
  }
  ul.whitelist li:last-child { border-bottom: none; }
  .hint { color: var(--muted); font-size: .8rem; margin-top: .6rem; }
  pre {
    background: #0a0c10;
    color: #c7ccd8;
    padding: 1rem;
    border-radius: var(--radius);
    overflow-x: auto;
    max-height: 360px;
    white-space: pre-wrap;
    word-break: break-word;
    font-size: .78rem;
    border: 1px solid var(--card-border);
    margin: 0;
  }
</style>
</head>
<body>

<h1>🛠️ Admin View</h1>

{% if message %}<div class="banner info">{{ message }}</div>{% endif %}

<div class="card">
  <span class="badge {{ 'running' if running else 'stopped' }}">
    <span class="dot"></span>{{ 'RUNNING' if running else 'STOPPED' }}
  </span>
  <div class="actions">
    <form class="inline" method="post" action="{{ url_for('start') }}">
      <button class="primary" type="submit" {{ 'disabled' if running else '' }}>▶ Start</button>
    </form>
    <form class="inline" method="post" action="{{ url_for('stop') }}">
      <button class="danger" type="submit" {{ '' if running else 'disabled' }}>■ Stop</button>
    </form>
    <form class="inline" method="post" action="{{ url_for('restart') }}">
      <button type="submit">⟳ Restart</button>
    </form>
    <form class="inline" method="get" action="{{ url_for('index') }}">
      <button type="submit">↻ Refresh</button>
    </form>
  </div>
</div>

<h3>Whitelist</h3>
<div class="card">
  {% if allowed_entries %}
  <ul class="whitelist">
    {% for uid, name in allowed_entries %}
    <li>
      <span>{% if name %}{{ name }} <span class="uid-muted">({{ uid }})</span>{% else %}{{ uid }}{% endif %}</span>
      <form class="inline" method="post" action="{{ url_for('whitelist_remove') }}">
        <input type="hidden" name="user_id" value="{{ uid }}">
        <button class="small danger" type="submit">Remove</button>
      </form>
    </li>
    {% endfor %}
  </ul>
  {% else %}
  <div class="banner warning">Whitelist is empty — anyone can use the bot.</div>
  {% endif %}
  <form class="add-form" method="post" action="{{ url_for('whitelist_add') }}">
    <input type="text" name="user_id" placeholder="Telegram user ID" inputmode="numeric">
    <input type="text" name="name" placeholder="Name (optional)">
    <button class="primary" type="submit">Add</button>
  </form>
  <p class="hint">Get an ID by having the person send /id to the bot. Changes restart the bot automatically.</p>
</div>

<h3>Live Log</h3>
<pre>{{ log_tail }}</pre>

</body>
</html>
"""


def check_auth(password: str) -> bool:
    return password == WEBUI_PASSWORD


def authenticate() -> Response:
    return Response(
        "Authentication required.",
        401,
        {"WWW-Authenticate": 'Basic realm="mp4-downloader-bot"'},
    )


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if WEBUI_PASSWORD:
            auth = request.authorization
            if not auth or not check_auth(auth.password):
                return authenticate()
        return f(*args, **kwargs)

    return decorated


def is_running() -> bool:
    result = subprocess.run(["pgrep", "-f", "python bot.py"], capture_output=True)
    return result.returncode == 0


def tail_log(lines: int = 50) -> str:
    if not os.path.exists(LOG_PATH):
        return "(no log yet)"
    with open(LOG_PATH, "r", errors="ignore") as f:
        return "".join(f.readlines()[-lines:]) or "(empty)"


def get_allowed_entries() -> list[tuple[str, str]]:
    """Returns [(user_id, name)] parsed from ALLOWED_USER_IDS, which stores
    entries as either "id" or "id:Name" (name is optional, comma-separated)."""
    values = dotenv_values(ENV_PATH)
    raw = (values.get("ALLOWED_USER_IDS") or "").strip()
    entries = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        uid, _, name = part.partition(":")
        entries.append((uid.strip(), name.strip()))
    return entries


def set_allowed_entries(entries: list[tuple[str, str]]) -> None:
    parts = [f"{uid}:{name}" if name else uid for uid, name in entries]
    set_key(ENV_PATH, "ALLOWED_USER_IDS", ",".join(parts), quote_mode="never")


def restart_bot(only_if_running: bool = False) -> None:
    if only_if_running and not is_running():
        return
    subprocess.run(["bash", "bot-stop.sh"], cwd=APP_DIR)
    time.sleep(1)
    subprocess.run(["bash", "bot-start.sh"], cwd=APP_DIR)


@app.route("/")
@requires_auth
def index():
    message = request.args.get("message")
    return render_template_string(
        PAGE,
        running=is_running(),
        log_tail=tail_log(),
        allowed_entries=get_allowed_entries(),
        message=message,
    )


@app.route("/start", methods=["POST"])
@requires_auth
def start():
    subprocess.run(["bash", "bot-start.sh"], cwd=APP_DIR)
    return redirect(url_for("index"))


@app.route("/stop", methods=["POST"])
@requires_auth
def stop():
    subprocess.run(["bash", "bot-stop.sh"], cwd=APP_DIR)
    return redirect(url_for("index"))


@app.route("/restart", methods=["POST"])
@requires_auth
def restart():
    restart_bot()
    return redirect(url_for("index"))


@app.route("/whitelist/add", methods=["POST"])
@requires_auth
def whitelist_add():
    new_id = request.form.get("user_id", "").strip()
    name = request.form.get("name", "").strip()
    if not new_id.isdigit():
        return redirect(url_for("index", message=f"'{new_id}' is not a valid numeric Telegram ID."))

    entries = get_allowed_entries()
    if any(uid == new_id for uid, _ in entries):
        return redirect(url_for("index", message=f"{new_id} is already whitelisted."))

    entries.append((new_id, name))
    set_allowed_entries(entries)
    restart_bot(only_if_running=True)
    label = f"{new_id} ({name})" if name else new_id
    return redirect(url_for("index", message=f"Added {label}. Bot restarted to apply."))


@app.route("/whitelist/remove", methods=["POST"])
@requires_auth
def whitelist_remove():
    remove_id = request.form.get("user_id", "").strip()
    entries = get_allowed_entries()
    remaining = [(uid, name) for uid, name in entries if uid != remove_id]
    if len(remaining) != len(entries):
        set_allowed_entries(remaining)
        restart_bot(only_if_running=True)
        return redirect(url_for("index", message=f"Removed {remove_id}. Bot restarted to apply."))
    return redirect(url_for("index"))


if __name__ == "__main__":
    if WEBUI_HOST != "127.0.0.1" and not WEBUI_PASSWORD:
        print(
            "WARNING: WEBUI_HOST is not 127.0.0.1 but WEBUI_PASSWORD is unset. "
            "Anyone on your network can start/stop the bot. Set WEBUI_PASSWORD in .env."
        )
    app.run(host=WEBUI_HOST, port=WEBUI_PORT)
