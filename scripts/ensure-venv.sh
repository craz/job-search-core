#!/usr/bin/env bash
# Create and synchronize the repository-local environment. This script is the
# non-interactive counterpart to direnv and is safe to call repeatedly from Make.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is required; install it from https://docs.astral.sh/uv/" >&2
  exit 1
fi

UV_LINK_MODE=copy uv sync --all-groups --frozen

