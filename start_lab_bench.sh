#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# pyontrust Lab Bench — starter script (Linux / macOS)
#
#   ./start_lab_bench.sh                  # 127.0.0.1:5200, auto-open browser
#   ./start_lab_bench.sh --port 8080      # custom port
#   ./start_lab_bench.sh --no-browser     # skip auto-open
#   ./start_lab_bench.sh --setup          # create .venv + install ".[gui,analysis]" first
#
# Mirrors the flags/env of start_lab_bench.py and the Dockerfile CMD.
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

# ── Resolve repo root (directory containing this script) ────────────
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
ROOT="$SCRIPT_DIR"

# ── Defaults (overridable via env or flags) ─────────────────────────
HOST="${PYONTRUST_HOST:-127.0.0.1}"
PORT="${PYONTRUST_PORT:-5200}"
ARTIFACTS="${PYONTRUST_ARTIFACTS:-artifacts}"
BENCH="${PYONTRUST_BENCH:-}"
DEBUG=""
NO_BROWSER=0
SETUP=0
EXTRAS="${PYONTRUST_EXTRAS:-gui,analysis}"
WANT_HELP=0
WANT_VERSION=0

usage() {
  cat <<'EOF'
pyontrust Lab Bench — starter script

Usage: ./start_lab_bench.sh [options]

Options:
  -h, --host <addr>     Bind address              (default: 127.0.0.1)
      --port <n>        TCP port                  (default: 5200)
      --artifacts <dir> Artifacts directory       (default: ./artifacts)
      --bench <json>    Default lab-bench JSON    (default: none)
      --debug           Enable Flask debug mode
      --no-browser      Don't auto-open the browser
  -s, --setup           Create .venv and install ".[gui,analysis]" first
      --extras <list>   Extras to install with --setup (default: gui,analysis)
  -V, --version         Print version and exit
  -H, --help            Show this help

Environment overrides: PYONTRUST_HOST, PYONTRUST_PORT, PYONTRUST_ARTIFACTS,
PYONTRUST_BENCH, PYONTRUST_LOG_LEVEL, PYONTRUST_EXTRAS.
EOF
}

# ── Parse arguments ──────────────────────────────────────────────────
while [ $# -gt 0 ]; do
  case "$1" in
    --host|-h)        HOST="${2:?--host needs a value}"; shift 2 ;;
    --port)           PORT="${2:?--port needs a value}"; shift 2 ;;
    --artifacts)      ARTIFACTS="${2:?--artifacts needs a value}"; shift 2 ;;
    --bench)          BENCH="${2:?--bench needs a value}"; shift 2 ;;
    --debug)          DEBUG="--debug"; shift ;;
    --no-browser)     NO_BROWSER=1; shift ;;
    -s|--setup)       SETUP=1; shift ;;
    --extras)         EXTRAS="${2:?--extras needs a value}"; shift 2 ;;
    -V|--version)     WANT_VERSION=1; shift ;;
    -H|--help)        WANT_HELP=1; shift ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[ "$WANT_HELP" = 1 ] && { usage; exit 0; }

# ── Bootstrap the environment (optional) ─────────────────────────────
do_setup() {
  local py3
  py3="$(command -v python3 || command -v python || true)"
  if [ -z "$py3" ]; then
    echo "ERROR: no python3/python found on PATH to create a venv." >&2
    exit 1
  fi
  if [ ! -x "$ROOT/.venv/bin/python" ]; then
    echo ">> Creating virtualenv at $ROOT/.venv"
    "$py3" -m venv "$ROOT/.venv"
  fi
  local py="$ROOT/.venv/bin/python"
  echo ">> Upgrading pip"
  "$py" -m pip install --upgrade pip >/dev/null
  echo ">> Installing pyontrust[.$EXTRAS]"
  "$py" -m pip install ".[$EXTRAS]"
}

# ── Pick a usable interpreter (venv preferred) ───────────────────────
PY=""
if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
elif [ "$SETUP" = 1 ]; then
  do_setup
  PY="$ROOT/.venv/bin/python"
else
  # Fall back to a system interpreter that already has pyontrust + flask.
  for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1 \
       && "$cand" -c "import pyontrust, flask" >/dev/null 2>&1; then
      PY="$(command -v "$cand")"; break
    fi
  done
fi

if [ -z "$PY" ]; then
  echo "ERROR: no usable Python with 'pyontrust' + 'flask' found." >&2
  echo "" >&2
  echo "  Recommended: ./start_lab_bench.sh --setup" >&2
  echo "  Or manually: python3 -m venv .venv && .venv/bin/pip install '.[gui,analysis]'" >&2
  exit 1
fi

# ── Version (early exit) ─────────────────────────────────────────────
if [ "$WANT_VERSION" = 1 ]; then
  "$PY" -c "import pyontrust; print(pyontrust.__version__)" 2>/dev/null \
    || echo "pyontrust (version unknown)"
  exit 0
fi

# ── Sanity: can we actually import the gateway? ──────────────────────
if ! "$PY" -c "import pyontrust.gateway.app, flask" >/dev/null 2>&1; then
  echo "ERROR: '$PY' cannot import pyontrust.gateway.app / flask." >&2
  echo "       Try: ./start_lab_bench.sh --setup" >&2
  exit 1
fi

# ── Banner ───────────────────────────────────────────────────────────
URL="http://${HOST}:${PORT}"
echo ""
echo "  +--------------------------------------------------+"
echo "  |  pyontrust Lab Bench                              |"
printf '  |  %-49s|\n' "$URL"
echo "  +--------------------------------------------------+"
echo ""
echo "  Artifacts : $ARTIFACTS"
[ -n "$BENCH" ] && echo "  Bench     : $BENCH"
echo "  Debug     : $( [ -n "$DEBUG" ] && echo ON || echo OFF )"
echo "  Python    : $PY"
echo ""
echo "  Press Ctrl+C to stop the server."
echo ""

# ── Auto-open browser (best-effort, non-blocking) ────────────────────
open_browser() {
  local url="$1"
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$url" >/dev/null 2>&1 || true
  fi
}
if [ "$NO_BROWSER" = 0 ]; then
  ( sleep 1.5; open_browser "$URL" ) >/dev/null 2>&1 &
fi

# ── Launch (foreground; exec so Ctrl+C / signals reach Flask) ────────
cd "$ROOT"   # resolve relative artifacts/ and data/ against the repo root
export PYONTRUST_LOG_LEVEL="${PYONTRUST_LOG_LEVEL:-INFO}"
exec "$PY" -m pyontrust.gateway.app \
  --host "$HOST" \
  --port "$PORT" \
  --artifacts "$ARTIFACTS" \
  ${BENCH:+--bench "$BENCH"} \
  $DEBUG
