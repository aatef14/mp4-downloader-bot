#!/data/data/com.termux/files/usr/bin/bash
# Starts the local web control panel in the background.

cd "$(dirname "$0")"

if pgrep -f "python webui.py" > /dev/null; then
    echo "Web UI is already running. Use 'bash web-stop.sh' first if you want to restart it."
    exit 1
fi

nohup python webui.py >> webui.log 2>&1 &
disown

sleep 2

if pgrep -f "python webui.py" > /dev/null; then
    PORT=$(grep -E '^WEBUI_PORT=' .env 2>/dev/null | cut -d= -f2)
    PORT=${PORT:-8080}
    echo "Web UI started. Open http://localhost:$PORT in your phone's browser."
    echo "Stop it with: bash web-stop.sh"
else
    echo "Web UI failed to start. Last log lines:"
    echo "---"
    tail -n 20 webui.log
    exit 1
fi
