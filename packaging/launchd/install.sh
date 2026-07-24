#!/usr/bin/env bash
# Install a LaunchAgent that runs `aiuse -q --json` every 6 hours and enables
# analysis.persist_snapshots in ~/.config/aiuse/services.yaml when missing.
set -euo pipefail

LABEL="com.djbclark.aiuse"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TEMPLATE="${REPO_ROOT}/packaging/launchd/${LABEL}.plist"
DEST_DIR="${HOME}/Library/LaunchAgents"
DEST="${DEST_DIR}/${LABEL}.plist"
LOG_DIR="${HOME}/Library/Logs/aiuse"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/aiuse"
SERVICES="${CONFIG_DIR}/services.yaml"

AIUSE_BIN="$(command -v aiuse || true)"
if [[ -z "${AIUSE_BIN}" ]]; then
  echo "error: aiuse not on PATH (install via pipx or brew first)" >&2
  exit 1
fi
AIUSE_BIN="$(cd "$(dirname "${AIUSE_BIN}")" && pwd)/$(basename "${AIUSE_BIN}")"

mkdir -p "${DEST_DIR}" "${LOG_DIR}" "${CONFIG_DIR}"

# Enable persist_snapshots without clobbering an existing services.yaml.
if [[ ! -f "${SERVICES}" ]]; then
  mkdir -p "${CONFIG_DIR}"
  cat >"${SERVICES}" <<'EOF'
analysis:
  persist_snapshots: true
  learn_from_history: false
EOF
  echo "created: ${SERVICES} (persist_snapshots: true)"
else
  if grep -q 'persist_snapshots:' "${SERVICES}" 2>/dev/null; then
    # Leave explicit setting alone.
    :
  else
    if grep -q '^analysis:' "${SERVICES}"; then
      # Insert under analysis: (first occurrence).
      tmp="$(mktemp)"
      awk '
        BEGIN { done=0 }
        /^analysis:/ && !done {
          print
          print "  persist_snapshots: true"
          done=1
          next
        }
        { print }
        END {
          if (!done) {
            print "analysis:"
            print "  persist_snapshots: true"
          }
        }
      ' "${SERVICES}" >"${tmp}"
      mv "${tmp}" "${SERVICES}"
      echo "updated: ${SERVICES} (added persist_snapshots: true)"
    else
      printf '\nanalysis:\n  persist_snapshots: true\n' >>"${SERVICES}"
      echo "updated: ${SERVICES} (appended analysis.persist_snapshots)"
    fi
  fi
fi

# Render plist from template.
sed \
  -e "s|AIUSE_BIN|${AIUSE_BIN}|g" \
  -e "s|LOG_DIR|${LOG_DIR}|g" \
  "${TEMPLATE}" >"${DEST}"
chmod 644 "${DEST}"

UID_NUM="$(id -u)"
# Unload if already present (best-effort).
launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/${UID_NUM}" "${DEST}"
launchctl enable "gui/${UID_NUM}/${LABEL}"
launchctl kickstart -k "gui/${UID_NUM}/${LABEL}" || true

echo "installed: ${DEST}"
echo "aiuse:     ${AIUSE_BIN}"
echo "logs:      ${LOG_DIR}/"
echo "interval:  6 hours (StartInterval 21600)"
echo "note:      exit 1 = hard failure; exit 2 = alerts present (collection ok)"
echo "next:      after a few days of snapshots, set learn_from_history: true"
echo "           (see docs/history-learning.md)"
