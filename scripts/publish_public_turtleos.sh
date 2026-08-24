#!/usr/bin/env bash
# publish_public_turtleos.sh — derive a public subset from public_surface.conf.
#
# The private chronicle lives on the Mini (~/repos/turtleos.git). Forge
# origin and Mini origin both point there. This script is the only supported
# path to the public GitHub subset (malteristo/turtleos), with its own
# lineage. It never pushes the subset to origin.
#
#   ./scripts/publish_public_turtleos.sh            # dry-run (default)
#   ./scripts/publish_public_turtleos.sh --dry-run  # same
#   ./scripts/publish_public_turtleos.sh --publish  # commit+push; needs remote
#   ./scripts/publish_public_turtleos.sh --publish --init
#       first snapshot onto an empty public remote (orphan history)
#
# --publish is the visibility act. This script does not create remotes or
# GitHub repos. --init refuses if the public branch already exists.
#
# Paths go to stdout (same set as public_surface.sh --list). Status goes to
# stderr, so a test can compare the two lists without parsing prose.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

MODE=dry-run
INIT=false
REMOTE="${TURTLEOS_PUBLIC_REMOTE:-public}"
BRANCH="${TURTLEOS_PUBLIC_BRANCH:-main}"
STAGING_BRANCH="${TURTLEOS_PUBLIC_STAGING_BRANCH:-publish/staging}"
WORKTREE=".publish-worktree"

for arg in "$@"; do
  case "$arg" in
    --dry-run) MODE=dry-run ;;
    --publish) MODE=publish ;;
    --init) INIT=true; MODE=publish ;;
    -h|--help)
      sed -n '2,18p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      echo "usage: $0 [--dry-run|--publish|--publish --init]" >&2
      exit 1
      ;;
  esac
done

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$ROOT" ]; then
  echo "Not inside a git repository." >&2
  exit 1
fi
cd "$ROOT"

# shellcheck source=/dev/null
. "$ROOT/scripts/public_surface.sh"

SURFACE="$(mktemp)"
trap 'rm -f "$SURFACE"' EXIT
ps_list_surface | sort > "$SURFACE"
COUNT="$(wc -l < "$SURFACE" | tr -d ' ')"

LEAK=""
while IFS= read -r path; do
  [ -z "$path" ] && continue
  is_public_surface "$path" || LEAK="${LEAK}${path}"$'\n'
done < "$SURFACE"

NEVER_LEAK=""
for never in "${PS_ABSOLUTE_NEVER[@]}"; do
  if grep -qxF "$never" "$SURFACE"; then
    NEVER_LEAK="${NEVER_LEAK}${never}"$'\n'
  fi
done

if [ -n "$LEAK$NEVER_LEAK" ]; then
  echo -e "${RED}BLOCKED: the surface list is not the public surface:${NC}" >&2
  printf '%s' "$LEAK$NEVER_LEAK" | grep . | head -20 >&2
  exit 1
fi

echo "Resolving public surface..." >&2
echo "  $COUNT path(s) on the public surface" >&2

if [ "$MODE" = dry-run ]; then
  cat "$SURFACE"
  echo -e "${YELLOW}Dry run — no remote, no commit, no push.${NC}" >&2
  exit 0
fi

# ── --publish ────────────────────────────────────────────────────
# origin is the Mini's auto-pull. A different name pointing at the same
# URL is the same act. Both refuse.

_remote_url() {
  git remote get-url "$1" 2>/dev/null || true
}

ORIGIN_URL="$(_remote_url origin)"
if [ "$REMOTE" = "origin" ]; then
  echo -e "${RED}Refusing: origin is the Mini's private pull.${NC}" >&2
  echo "The public remote is a different remote with its own lineage." >&2
  exit 1
fi

if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then
  echo -e "${RED}Remote '$REMOTE' is not configured.${NC}" >&2
  echo "Creating it is the visibility act — this script does not create remotes." >&2
  echo "Set TURTLEOS_PUBLIC_REMOTE when the sanctioned remote exists." >&2
  exit 1
fi

PUB_URL="$(_remote_url "$REMOTE")"
if [ -n "$ORIGIN_URL" ] && [ "$PUB_URL" = "$ORIGIN_URL" ]; then
  echo -e "${RED}Refusing: $REMOTE has the same URL as origin.${NC}" >&2
  echo "That would push the private chronicle. The public remote needs its own lineage." >&2
  exit 1
fi
case "$PUB_URL" in
  *repos/turtleos.git*)
    echo -e "${RED}Refusing: $REMOTE points at the Mini chronicle.${NC}" >&2
    echo "The public remote is GitHub. origin is the bare repo on the Mini." >&2
    exit 1
    ;;
esac

MSG="Publish product subset from the private chronicle.

Allowlisted by scripts/public_surface.conf. New lineage — not a rewrite."

worktree_exists() {
  [ -e "$WORKTREE/.git" ] || git worktree list --porcelain | grep -q "^worktree $ROOT/$WORKTREE$"
}

if [ "$INIT" = true ]; then
  if git ls-remote --exit-code "$REMOTE" "refs/heads/$BRANCH" >/dev/null 2>&1; then
    echo -e "${RED}Remote already has $BRANCH. Use --publish without --init.${NC}" >&2
    exit 1
  fi
  # A worktree --orphan of THIS repo stole main on 2026-08-23 (bare=true,
  # HEAD moved to the snapshot). First snapshot is an independent repo.
  echo "First snapshot — independent tree, not a worktree of this chronicle..." >&2
  INIT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/turtleos-publish.XXXXXX")"
  trap 'rm -f "$SURFACE"; rm -rf "$INIT_DIR"' EXIT
  git init -q -b "$BRANCH" "$INIT_DIR"
  while IFS= read -r rel; do
    [ -z "$rel" ] && continue
    mkdir -p "$INIT_DIR/$(dirname "$rel")"
    cp "$ROOT/$rel" "$INIT_DIR/$rel"
  done < "$SURFACE"
  cd "$INIT_DIR"
  git add -A
  BLOCKED=""
  while IFS= read -r path; do
    [ -z "$path" ] && continue
    is_public_surface "$path" || BLOCKED="${BLOCKED}${path}"$'\n'
  done < <(git diff --cached --name-only --diff-filter=ACM)
  if [ -n "$BLOCKED" ]; then
    echo -e "${RED}BLOCKED: staged paths are not on the public surface:${NC}" >&2
    echo "$BLOCKED" | grep . | head -20 >&2
    exit 1
  fi
  echo "  $(git diff --cached --name-only | wc -l | tr -d ' ') path(s) in the first snapshot" >&2
  git commit -q -m "$MSG"
  git remote add dest "$PUB_URL"
  git push dest "$BRANCH:$BRANCH"
  echo -e "${GREEN}Published first snapshot to $REMOTE/$BRANCH${NC}" >&2
  exit 0
else
  echo "Fetching $REMOTE..." >&2
  if ! git fetch "$REMOTE" "$BRANCH" 2>/dev/null; then
    echo -e "${RED}Public remote has no $BRANCH yet.${NC}" >&2
    echo "First snapshot: $0 --publish --init" >&2
    exit 1
  fi
  if ! worktree_exists; then
    echo "Creating publish worktree at $WORKTREE..." >&2
    git worktree add -B "$STAGING_BRANCH" "$WORKTREE" "$REMOTE/$BRANCH"
  else
    echo "Updating publish worktree..." >&2
    git -C "$WORKTREE" fetch "$REMOTE" "$BRANCH"
    git -C "$WORKTREE" checkout -q "$STAGING_BRANCH"
    git -C "$WORKTREE" reset -q --hard "$REMOTE/$BRANCH"
  fi
fi

echo "Deriving worktree from the surface..." >&2
find "$WORKTREE" -mindepth 1 -path "$WORKTREE/.git" -prune -o -type f -print0 \
  | xargs -0 rm -f 2>/dev/null || true

while IFS= read -r rel; do
  [ -z "$rel" ] && continue
  mkdir -p "$WORKTREE/$(dirname "$rel")"
  cp "$ROOT/$rel" "$WORKTREE/$rel"
done < "$SURFACE"

cd "$WORKTREE"
git add -A

BLOCKED=""
while IFS= read -r path; do
  [ -z "$path" ] && continue
  is_public_surface "$path" || BLOCKED="${BLOCKED}${path}"$'\n'
done < <(git diff --cached --name-only --diff-filter=ACM)

if [ -n "$BLOCKED" ]; then
  echo -e "${RED}BLOCKED: staged paths are not on the public surface:${NC}" >&2
  echo "$BLOCKED" | grep . | head -20 >&2
  exit 1
fi

if git diff --cached --quiet; then
  echo -e "${GREEN}Public remote already up to date — nothing to publish.${NC}" >&2
  exit 0
fi

echo "" >&2
echo "=== Changes to publish ===" >&2
git diff --cached --stat >&2
echo "" >&2

git commit -m "$MSG"
git push "$REMOTE" "$STAGING_BRANCH:$BRANCH"

echo -e "${GREEN}Published to $REMOTE/$BRANCH${NC}" >&2
git log -1 --oneline >&2
