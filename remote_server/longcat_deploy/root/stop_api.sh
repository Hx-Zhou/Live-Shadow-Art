#!/usr/bin/env bash
set -euo pipefail

deploy_root="${DEPLOY_ROOT:-/home/ma-user/work/longcat_deploy}"
source "${deploy_root}/process_utils.sh"
if [[ -r "${deploy_root}/api.env" ]]; then
  source "${deploy_root}/api.env"
fi
state_dir="${LONGCAT_API_STATE_DIR:-${deploy_root}/api_state}"
run_dir="${state_dir}/run"

stop_one() {
  local name="$1"
  local expected="$2"
  local pid_file="${run_dir}/${name}.pid"
  if [[ ! -f "${pid_file}" ]]; then
    printf '%s is not running (no pid file)\n' "${name}"
    return
  fi
  local pid
  if ! pid="$(read_service_pid "${pid_file}")"; then
    printf '%s has an invalid PID file; removing it without signalling a process\n' "${name}"
    rm -f "${pid_file}"
    return
  fi
  if service_pid_matches "${pid}" "${expected}"; then
    kill -TERM "${pid}"
    for _ in {1..30}; do
      if ! kill -0 "${pid}" 2>/dev/null; then
        break
      fi
      sleep 1
    done
    if kill -0 "${pid}" 2>/dev/null; then
      printf '%s pid=%s did not stop within 30 seconds; inspect it manually\n' "${name}" "${pid}" >&2
      return 1
    fi
    printf 'stopped %s pid=%s\n' "${name}" "${pid}"
  elif kill -0 "${pid}" 2>/dev/null; then
    printf '%s pid=%s belongs to another command; removing stale PID file only\n' \
      "${name}" "${pid}"
  else
    printf '%s pid=%s is already stopped\n' "${name}" "${pid}"
  fi
  rm -f "${pid_file}"
}

# Stop accepting requests first, then let the worker finish/close its model.
stop_one api "uvicorn api_service.app:app"
stop_one worker "python -m api_service.worker"
