#!/usr/bin/env bash
# scripts/rav-gcp.sh — unified operator CLI for RAV GCP spot-runner wrappers.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

_run_wrapper() {
  local wrapper="$1"
  shift
  bash "${SCRIPT_DIR}/${wrapper}" "$@"
}

_usage() {
  cat <<'USAGE'
rav-gcp — RAV GCP Spot Runner CLI

Usage:
  ./scripts/rav-gcp.sh <command> [args]

Commands:
  submit [ARGS]          Submit PRIMARY (CheXpert) run
  primary [ARGS]         Alias for submit
  poc [ARGS]             Submit POC run
  build [ARGS]           Build/push training image
  monitor [ARGS]         Open tmux monitor workspace (spotctl monitor wrapper)
  ops [ARGS]             Pass-through to ops wrapper (default: status)
  status [ARGS]          Alias for: ops status
  serial [ARGS]          Alias for: ops serial
  events [ARGS]          Alias for: ops events
  preempt [ARGS]         Alias for: ops preempt
  list [ARGS]            Alias for: ops list
  watch [ARGS]           Alias for: ops watch
  delete [ARGS]          Alias for: ops delete
  help                   Show this help

Examples:
  ./scripts/rav-gcp.sh build
  ./scripts/rav-gcp.sh submit --run-id rav-chexpert-001 --skip-build
  ./scripts/rav-gcp.sh poc --run-id rav-poc-001 --skip-build
  ./scripts/rav-gcp.sh status --run-id rav-chexpert-001
  ./scripts/rav-gcp.sh events --run-id rav-chexpert-001 --since 24h
  ./scripts/rav-gcp.sh monitor --single --pin-run-id
USAGE
}

main() {
  local cmd="${1:-help}"
  shift || true

  case "${cmd}" in
    submit|primary)
      _run_wrapper "gcp_submit_primary.sh" "$@"
      ;;
    poc)
      _run_wrapper "gcp_submit_poc.sh" "$@"
      ;;
    build)
      _run_wrapper "gcp_build_image.sh" "$@"
      ;;
    monitor)
      _run_wrapper "gcp_monitor.sh" "$@"
      ;;
    ops)
      _run_wrapper "gcp_ops.sh" "$@"
      ;;
    status)
      _run_wrapper "gcp_ops.sh" status "$@"
      ;;
    serial)
      _run_wrapper "gcp_ops.sh" serial "$@"
      ;;
    events)
      _run_wrapper "gcp_ops.sh" events "$@"
      ;;
    preempt)
      _run_wrapper "gcp_ops.sh" preempt "$@"
      ;;
    list|ls)
      _run_wrapper "gcp_ops.sh" list "$@"
      ;;
    watch)
      _run_wrapper "gcp_ops.sh" watch "$@"
      ;;
    delete|del|kill)
      _run_wrapper "gcp_ops.sh" delete "$@"
      ;;
    help|-h|--help)
      _usage
      ;;
    *)
      echo "Unknown command: ${cmd}" >&2
      echo "Run './scripts/rav-gcp.sh help' for usage." >&2
      exit 1
      ;;
  esac
}

main "$@"
