#!/usr/bin/env bash
# wsl-setup.sh — One-shot bootstrap for the WSL mutation-testing environment.
# Run this once after cloning into your WSL home directory.
#
# Usage:
#   cd ~/trucking-pay-wizard
#   chmod +x scripts/wsl-setup.sh
#   ./scripts/wsl-setup.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ── Colours ────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[setup]${NC} $*"; }
warn()    { echo -e "${YELLOW}[warn]${NC}  $*"; }
error()   { echo -e "${RED}[error]${NC} $*" >&2; exit 1; }

# ── Guard: must be running inside WSL ──────────────────────────────────────
if [[ -z "${WSL_DISTRO_NAME:-}" && ! -f /proc/sys/fs/binfmt_misc/WSLInterop ]]; then
    warn "This script is intended for WSL. Continuing anyway, but some steps may not apply."
fi

# ── Guard: must NOT be on the /mnt/c/ bridge ──────────────────────────────
if [[ "$REPO_ROOT" == /mnt/* ]]; then
    error "Repo is on the Windows filesystem ($REPO_ROOT). Clone into your WSL home (~/) instead.
  The /mnt/c/ bridge adds I/O overhead that makes mutmut very slow and can cause file-lock errors."
fi

# ── 1. Python 3.11+ ────────────────────────────────────────────────────────
info "Checking Python version..."
if ! command -v python3 &>/dev/null; then
    info "Python not found — installing via apt..."
    sudo apt-get update -qq
    sudo apt-get install -y python3 python3-pip python3-venv
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [[ "$PY_MAJOR" -lt 3 || ( "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 11 ) ]]; then
    info "Python $PY_VERSION found but 3.11+ is required. Installing python3.11..."
    sudo apt-get update -qq
    sudo apt-get install -y python3.11 python3.11-venv python3.11-pip
    PYTHON=python3.11
else
    info "Python $PY_VERSION — OK"
    PYTHON=python3
fi

# ── 2. Virtual environment ─────────────────────────────────────────────────
if [[ ! -d .venv ]]; then
    info "Creating virtual environment..."
    "$PYTHON" -m venv .venv
else
    info "Virtual environment already exists — skipping creation."
fi

# Activate
# shellcheck disable=SC1091
source .venv/bin/activate
info "Activated .venv ($(python --version))"

# ── 3. Install dependencies ────────────────────────────────────────────────
info "Installing dependencies from requirements-wsl.txt..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements-wsl.txt
info "Dependencies installed."

# ── 4. .env file ──────────────────────────────────────────────────────────
if [[ ! -f .env ]]; then
    cp .env.example .env
    warn ".env created from .env.example."
    warn "Fill in AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT, AZURE_DOCUMENT_INTELLIGENCE_KEY,"
    warn "and ANTHROPIC_API_KEY before running live API tests."
    warn "(Unit and integration tests use mocks and do not need real credentials.)"
else
    info ".env already exists — skipping."
fi

# ── 5. Smoke test ─────────────────────────────────────────────────────────
info "Running smoke test (pytest --no-cov -q)..."
if pytest --no-cov -q; then
    info "Smoke test passed."
else
    error "Smoke test FAILED. Fix the failures above before running mutmut."
fi

# ── Done ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN} WSL environment ready. To run mutation tests:${NC}"
echo ""
echo "   source .venv/bin/activate"
echo "   mutmut run"
echo ""
echo "   mutmut results          # after the run"
echo "   mutmut show <id>        # inspect a surviving mutant"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
