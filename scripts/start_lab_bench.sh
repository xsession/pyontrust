#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# pyontrust Lab Bench — Quick Launcher (Linux/macOS)
# Mirrors start_lab_bench.py / start_lab_bench.bat
#
# Usage:
#   ./start_lab_bench.sh                          # defaults: 127.0.0.1:5200
#   ./start_lab_bench.sh --port 8080              # custom port
#   ./start_lab_bench.sh --host 0.0.0.0           # bind all interfaces
#   ./start_lab_bench.sh --no-browser             # skip auto-open
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

HOST="${PYONTRUST_HOST:-127.0.0.1}"
PORT="${PYONTRUST_PORT:-5200}"
OPEN_BROWSER=1
EXTRA_ARGS=()

# ── Parse arguments (unknown flags pass through to the gateway) ──
while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)      HOST="$2"; shift 2 ;;
        --port)      PORT="$2"; shift 2 ;;
        --no-browser) OPEN_BROWSER=0; shift ;;
        *)           EXTRA_ARGS+=("$1"); shift ;;
    esac
done

URL="http://${HOST}:${PORT}"

echo
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║  pyontrust Lab Bench                            ║"
printf "  ║  %-46s║\n" "$URL"
echo "  ╚══════════════════════════════════════════════════╝"
echo

# ── Locate a Python with pyontrust installed ───────────────────
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi

if ! "$PY" -c "import pyontrust.gateway.app" >/dev/null 2>&1; then
    # fall back to the repo venv if we're running from a source checkout
    REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    if [[ -x "$REPO_ROOT/.venv/bin/python" ]] \
       && "$REPO_ROOT/.venv/bin/python" -c "import pyontrust.gateway.app" >/dev/null 2>&1; then
        PY="$REPO_ROOT/.venv/bin/python"
    else
        echo "  [ERROR] pyontrust is not importable by $PY."
        echo "          Install it first:   pip install -e ".[gui]""
        exit 1
    fi
fi

# ── Auto-open browser (non-blocking) ───────────────────────────
if [[ "$OPEN_BROWSER" == "1" ]]; then
    ( sleep 2
      if command -v xdg-open >/dev/null 2>&1;     then xdg-open "$URL" >/dev/null 2>&1 || true
      elif command -v open >/dev/null 2>&1;       then open "$URL" >/dev/null 2>&1 || true
      fi ) &
fi

# ── Run the gateway (foreground, Ctrl+C to stop) ───────────────
exec "$PY" -m pyontrust.gateway.app --host "$HOST" --port "$PORT" "${EXTRA_ARGS[@]}"
