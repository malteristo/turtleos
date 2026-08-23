#!/usr/bin/env bash
# public_surface.sh — one answer to "may this path be public?"
#
#   ./scripts/public_surface.sh --self-test
#   ./scripts/public_surface.sh --list
#   ./scripts/public_surface.sh --check PATH
#
# A tracked file at the repo root (no slash) is public unless DENY'd.
# That is how discord_bot.py ships without a hundred FILE lines.

set -uo pipefail

PS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
PS_CONF="${PS_CONF:-$PS_ROOT/scripts/public_surface.conf}"

PS_DIRS=()
PS_FILES=()
PS_DENY=()

# Unreachable even if someone writes FILE. Instance facts, not product.
PS_ABSOLUTE_NEVER=(
  "docs/live-runtime.md"
  "docs/learnings.md"
)

ps_load() {
  [ "${#PS_DIRS[@]}" -gt 0 ] && return 0
  [ -f "$PS_CONF" ] || { echo "public_surface: missing $PS_CONF" >&2; return 1; }
  local kind value
  while read -r kind value _rest; do
    case "$kind" in
      DIR)  PS_DIRS+=("${value%/}") ;;
      FILE) PS_FILES+=("$value") ;;
      DENY) PS_DENY+=("$value") ;;
      ''|'#'*) ;;
    esac
  done < <(sed 's/#.*//' "$PS_CONF" | grep -E '^\s*(DIR|FILE|DENY)\s')
  return 0
}

_ps_denied() {
  local path="$1" pat base
  base="$(basename "$path")"
  for pat in "${PS_DENY[@]}"; do
    case "$pat" in
      */)
        local d="${pat%/}"
        [ "$path" = "$d" ] && return 0
        case "$path" in "$d"/*|*/"$d"/*) return 0 ;; esac
        ;;
      *\**)
        # shellcheck disable=SC2254
        case "$path" in $pat) return 0 ;; esac
        case "$base" in $pat) return 0 ;; esac
        ;;
      */*)
        [ "$path" = "$pat" ] && return 0
        ;;
      *)
        [ "$base" = "$pat" ] && return 0
        ;;
    esac
  done
  return 1
}

is_public_surface() {
  ps_load || return 1
  local path="${1#./}" never f d
  [ -z "$path" ] && return 1

  for never in "${PS_ABSOLUTE_NEVER[@]}"; do
    [ "$path" = "$never" ] && return 1
  done

  for f in "${PS_FILES[@]}"; do
    [ "$path" = "$f" ] && return 0
  done

  _ps_denied "$path" && return 1

  for d in "${PS_DIRS[@]}"; do
    case "$path" in "$d"/*) return 0 ;; esac
  done

  # Repo-root file (discord_bot.py, README.md already FILE'd, …).
  case "$path" in */*) return 1 ;; esac
  return 0
}

ps_list_surface() {
  ps_load || return 1
  local p
  while IFS= read -r p; do
    is_public_surface "$p" && echo "$p"
  done < <(cd "$PS_ROOT" && git ls-files)
}

_ps_fail=0
_ps_expect() {
  local got="private"
  is_public_surface "$1" && got="public"
  if [ "$got" != "$2" ]; then
    echo "  FAIL  $1 → $got, expected $2   ($3)"
    _ps_fail=$((_ps_fail + 1))
  fi
}

ps_self_test() {
  ps_load || return 1
  echo "public_surface self-test"
  echo "  conf: $PS_CONF (${#PS_DIRS[@]} DIR, ${#PS_FILES[@]} FILE, ${#PS_DENY[@]} DENY)"
  echo ""

  _ps_expect "README.md" public "root product"
  _ps_expect "discord_bot.py" public "root module"
  _ps_expect "TURTLE_SPEC.md" public "law"
  _ps_expect "docs/ux/onboarding.md" public "allowed DIR"
  _ps_expect "tests/test_doc_topology.py" public "tests ship after fixtures are clean"
  _ps_expect "docs/live-runtime.md" private "one deployment"
  _ps_expect "docs/learnings.md" private "operator chronicle"
  _ps_expect "autoresearch/program.md" private "research queue"
  _ps_expect "identity/soul.md" private "retired attunement seed"

  local before=$_ps_fail
  if is_public_surface "docs/live-runtime.md"; then
    echo "  FAIL  positive control: live-runtime was public"
    _ps_fail=$((_ps_fail + 1))
  fi
  [ "$_ps_fail" -eq "$before" ] && echo "  ok    positive control: live-runtime is private"

  echo ""
  if [ "$_ps_fail" -gt 0 ]; then
    echo "FAILED — $_ps_fail check(s)"
    return 1
  fi
  echo "Unit checks green."
  return 0
}

if [ "${BASH_SOURCE[0]:-$0}" = "$0" ]; then
  case "${1:---self-test}" in
    --self-test) ps_self_test ;;
    --list)      ps_list_surface ;;
    --check)     if is_public_surface "${2:-}"; then echo "public"; else echo "private"; fi ;;
    *) echo "usage: $0 [--self-test|--list|--check PATH]" >&2; exit 2 ;;
  esac
fi
