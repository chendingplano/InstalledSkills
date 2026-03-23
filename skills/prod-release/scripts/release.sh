#!/usr/bin/env bash
# prod-release helper script
# Usage: release.sh <project-name> [jj|git]
#
# Handles the mechanical parts of a production release:
#   - Validates project directory
#   - Auto-detects VCS (jj or git) unless overridden
#   - Computes release name (rel-yyyymmdd or rel-yyyymmddnn)
#
# Output (tab-separated on one line):
#   <release-name>\t<vcs>
#   e.g. "rel-20260323\tjj"
#
# Exit codes:
#   0  success
#   1  validation error (message on stderr)

set -euo pipefail

PROJECT_NAME="${1:-}"
VCS_OVERRIDE="${2:-}"
WORKSPACE="$HOME/Workspace"

if [[ -z "$PROJECT_NAME" ]]; then
  echo "Usage: release.sh <project-name> [jj|git]" >&2
  exit 1
fi

PROJECT_DIR="$WORKSPACE/$PROJECT_NAME"

# Validate project directory
if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "ERROR: Project directory not found: $PROJECT_DIR" >&2
  exit 1
fi

# Detect VCS
detect_vcs() {
  local dir="$1"
  if [[ -d "$dir/.jj" ]]; then
    echo "jj"
  elif [[ -d "$dir/.git" ]]; then
    echo "git"
  else
    echo ""
  fi
}

if [[ -n "$VCS_OVERRIDE" ]]; then
  PROJECT_VCS="$VCS_OVERRIDE"
else
  PROJECT_VCS=$(detect_vcs "$PROJECT_DIR")
fi

if [[ -z "$PROJECT_VCS" ]]; then
  echo "ERROR: $PROJECT_DIR is not a jj or git repository (no .jj or .git directory)" >&2
  exit 1
fi

# Compute release name — collect existing tags from both repos
TODAY=$(date +%Y%m%d)
BASE_NAME="rel-$TODAY"

existing_tags_jj() {
  local dir="$1"
  # jj tag list outputs "tagname: commitid ..." — strip the trailing colon
  (cd "$dir" && jj tag list 2>/dev/null | awk '{print $1}' | sed 's/:$//') || true
}

existing_tags_git() {
  local dir="$1"
  (cd "$dir" && git tag 2>/dev/null) || true
}

existing_tags() {
  local dir="$1"
  local vcs="$2"
  if [[ "$vcs" == "jj" ]]; then
    existing_tags_jj "$dir"
  else
    existing_tags_git "$dir"
  fi
}

SHARED_DIR="$WORKSPACE/shared"
SHARED_VCS=$(detect_vcs "$SHARED_DIR")

ALL_TAGS=$(existing_tags "$PROJECT_DIR" "$PROJECT_VCS")
if [[ -n "$SHARED_VCS" ]]; then
  ALL_TAGS+=$'\n'$(existing_tags "$SHARED_DIR" "$SHARED_VCS")
fi

if echo "$ALL_TAGS" | grep -qx "$BASE_NAME"; then
  nn=1
  while true; do
    CANDIDATE="${BASE_NAME}$(printf '%02d' $nn)"
    if ! echo "$ALL_TAGS" | grep -qx "$CANDIDATE"; then
      RELEASE_NAME="$CANDIDATE"
      break
    fi
    nn=$((nn + 1))
  done
else
  RELEASE_NAME="$BASE_NAME"
fi

printf '%s\t%s\n' "$RELEASE_NAME" "$PROJECT_VCS"
