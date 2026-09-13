#!/usr/bin/env bash
#
# install.sh - set up Ubuntu MCP Server locally.
#
# Usage:
#   ./deploy/install.sh
#
# This script:
#   1. Installs OS packages needed to build/run the project (python3,
#      venv, pip, git).
#   2. Creates a virtualenv in .venv/
#   3. Installs the project (and dev/test deps) into it.
#   4. Copies .env.example to .env if .env doesn't exist yet.
#   5. Runs the test suite as a smoke check.
#
# It does NOT start the server or install the systemd unit -- see
# README.md ("Running" and "Deploying as a systemd service") for that.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "==> Installing OS packages (requires sudo)"
sudo apt-get update -qq
sudo apt-get install -y python3 python3-venv python3-pip git curl

echo "==> Creating virtual environment in .venv/"
python3 -m venv .venv
source .venv/bin/activate

echo "==> Upgrading pip and installing the project (with dev/test extras)"
pip install --upgrade pip --quiet
pip install -e ".[dev]" --quiet

if [ ! -f .env ]; then
  echo "==> Creating .env from .env.example"
  cp .env.example .env
else
  echo "==> .env already exists, leaving it alone"
fi

echo "==> Running the test suite as a smoke check"
pytest -q

cat <<'EOF'

==> Done.

Next steps:
  source .venv/bin/activate
  python -m ubuntu_mcp                 # run locally over stdio

Or point an MCP client at it -- see README.md "MCP client configuration".
EOF
