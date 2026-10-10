#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_DIR="${ROOT}/.git/hooks"

mkdir -p "${HOOKS_DIR}"
install -m 755 "${ROOT}/scripts/git-hooks/pre-push" "${HOOKS_DIR}/pre-push"
echo "Installed pre-push hook → ${HOOKS_DIR}/pre-push"
echo "Push is blocked until scripts/ci-local.sh passes."
