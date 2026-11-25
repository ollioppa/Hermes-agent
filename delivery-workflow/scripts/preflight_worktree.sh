#!/usr/bin/env bash
# Compatibility entry point; the runner directly uses preflight_worktree.py.
set -euo pipefail
exec "${DELIVERY_WORKFLOW_PYTHON:-python3}" "$(dirname "$0")/preflight_worktree.py" "${@:-$PWD}"
