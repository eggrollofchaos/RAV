#!/usr/bin/env bash
# state_helpers.sh — Shared state transition validation for bash scripts
# Loads state_transitions.json and provides can_transition() + state.json CAS helpers.
# Source this file; do NOT execute directly.

_STATE_HELPERS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_STATE_TRANSITIONS_FILE="${_STATE_HELPERS_DIR}/state_transitions.json"

# Valid actors
_VALID_ACTORS="vm reconciler local operator"

# Status.txt compatibility mapping: state.json state → status.txt value
_status_compat_map() {
  local state="$1"
  case "$state" in
    RUNNING)    echo "RUNNING" ;;
    COMPLETE)   echo "COMPLETE" ;;
    FAILED)     echo "FAILED" ;;
    PARTIAL)    echo "PARTIAL" ;;
    PREEMPTED)  echo "PREEMPTED" ;;
    ORPHANED)   echo "PREEMPTED" ;;    # Intentional: same semantics from poll loop's perspective
    RESTARTING) echo "RUNNING" ;;       # Poll loop treats as active run
    STOPPED)    echo "STOPPED" ;;
    *)          echo "$state" ;;
  esac
}

# Terminal states — cannot be overwritten
_is_terminal_state() {
  case "$1" in
    COMPLETE|FAILED|PARTIAL|STOPPED) return 0 ;;
    *) return 1 ;;
  esac
}

# Validate transition using state_transitions.json (requires jq)
# Usage: can_transition FROM TO ACTOR
# Returns 0 if allowed, 1 if not. Prints error to stderr on rejection.
can_transition() {
  local from="${1:-null}" to="$2" actor="$3"

  # Validate actor
  if [[ -z "$actor" ]]; then
    echo "can_transition: actor is required" >&2
    return 1
  fi
  local valid=false
  local a
  for a in $_VALID_ACTORS; do
    if [[ "$a" == "$actor" ]]; then
      valid=true
      break
    fi
  done
  if [[ "$valid" != true ]]; then
    echo "can_transition: unknown actor '$actor' (valid: $_VALID_ACTORS)" >&2
    return 1
  fi

  if [[ ! -f "$_STATE_TRANSITIONS_FILE" ]]; then
    echo "can_transition: missing $_STATE_TRANSITIONS_FILE" >&2
    return 1
  fi

  # Check edge exists
  local allowed
  allowed="$(jq -r --arg from "$from" --arg to "$to" \
    '.edges[$from] // [] | index($to) // -1' \
    "$_STATE_TRANSITIONS_FILE" 2>/dev/null)"

  if [[ "$allowed" == "-1" ]] || [[ -z "$allowed" ]]; then
    echo "can_transition: $from → $to not allowed" >&2
    return 1
  fi

  # Check actor guard
  local guard_key="${from}:${to}"
  local guard_list
  guard_list="$(jq -r --arg key "$guard_key" \
    '.actor_guards[$key] // [] | .[]' \
    "$_STATE_TRANSITIONS_FILE" 2>/dev/null)"

  if [[ -n "$guard_list" ]]; then
    local actor_allowed=false
    while IFS= read -r allowed_actor; do
      if [[ "$allowed_actor" == "$actor" ]]; then
        actor_allowed=true
        break
      fi
    done <<< "$guard_list"
    if [[ "$actor_allowed" != true ]]; then
      echo "can_transition: $from → $to guarded — actor '$actor' not in allowed list" >&2
      return 1
    fi
  fi

  return 0
}

# Compute SHA-256 hash of state_transitions.json for version logging
_state_transitions_hash() {
  if command -v shasum &>/dev/null; then
    shasum -a 256 "$_STATE_TRANSITIONS_FILE" | cut -c1-64
  else
    sha256sum "$_STATE_TRANSITIONS_FILE" | cut -c1-64
  fi
}
