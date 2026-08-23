import os
import subprocess
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, Response, redirect, render_template_string, request, url_for

load_dotenv()

APP_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(APP_DIR, "bot.log")

WEBUI_HOST = os.environ.get("WEBUI_HOST", "127.0.0.1")
WEBUI_PORT = int(os.environ.get("WEBUI_PORT", "8080"))
WEBUI_PASSWORD = os.environ.get("WEBUI_PASSWORD") or None

app = Flask(__name__)

PAGE = """
<!doctype html>
<title>mp4-downloader-bot control panel</title>
<style>
  body { font-family: sans-serif; max-width: 640px; margin: 2rem auto; padding: 0 1rem; }
  .status { padding: .5rem 1rem; border-radius: 6px; display: inline-block; margin-bottom: 1rem; font-weight: bold; }
  .running { background: #d4f7d4; color: #146614; }
  .stopped { background: #f7d4d4; color: #661414; }
  button { padding: .6rem 1.2rem; margin: 0 .5rem .5rem 0; font-size: 1rem; }
  pre { background: #111; color: #ddd; padding: 1rem; overflow-x: auto; max-height: 400px; white-space: pre-wrap; word-break: break-word; }
</style>
<h1>mp4-downloader-bot</h1>
<p class="status {{ 'running' if running else 'stopped' }}">
  Status: {{ 'RUNNING' if running else 'STOPPED' }}
</p>
<form method="post" action="{{ url_for('start') }}" style="display:inline">
  <button type="submit" {{ 'disabled' if running else '' }}>Start</button>
</form>
<form method="post" action="{{ url_for('stop') }}" style="display:inline">
  <button type="submit" {{ '' if running else 'disabled' }}>Stop</button>
</form>
<form method="post" action="{{ url_for('restart') }}" style="display:inline">
  <button type="submit">Restart</button>
</form>
<form method="get" action="{{ url_for('index') }}" style="display:inline">
  <button type="submit">Refresh</button>
</form>
<h3>Last log lines</h3>
<pre>{{ log_tail }}</pre>
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


@app.route("/")
@requires_auth
def index():
    return render_template_string(PAGE, running=is_running(), log_tail=tail_log())


@app.route("/start", methods=["POST"])
@requires_auth
def start():
    subprocess.run(["bash", "start.sh"], cwd=APP_DIR)
    return redirect(url_for("index"))


@app.route("/stop", methods=["POST"])
@requires_auth
def stop():
    subprocess.run(["bash", "stop.sh"], cwd=APP_DIR)
    return redirect(url_for("index"))


@app.route("/restart", methods=["POST"])
@requires_auth
def restart():
    subprocess.run(["bash", "stop.sh"], cwd=APP_DIR)
    subprocess.run(["bash", "start.sh"], cwd=APP_DIR)
    return redirect(url_for("index"))


if __name__ == "__main__":
    if WEBUI_HOST != "127.0.0.1" and not WEBUI_PASSWORD:
        print(
            "WARNING: WEBUI_HOST is not 127.0.0.1 but WEBUI_PASSWORD is unset. "
            "Anyone on your network can start/stop the bot. Set WEBUI_PASSWORD in .env."
        )
    app.run(host=WEBUI_HOST, port=WEBUI_PORT)
