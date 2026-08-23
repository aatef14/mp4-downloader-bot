#!/data/data/com.termux/files/usr/bin/bash
# Stops the local web control panel started by web-start.sh.

if pgrep -f "python webui.py" > /dev/null; then
    pkill -f "python webui.py"
    echo "Web UI stopped."
else
    echo "Web UI is not running."
fi
