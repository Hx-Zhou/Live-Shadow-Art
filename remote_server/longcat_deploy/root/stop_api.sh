#!/usr/bin/env bash
set -euo pipefail

deploy_root="${DEPLOY_ROOT:-/home/ma-user/work/longcat_deploy}"
state_dir="${LONGCAT_API_STATE_DIR:-${deploy_root}/api_state}"
run_dir="${state_dir}/run"

stop_one() {
  local name="$1"
  local pid_file="${run_dir}/${name}.pid"
  if [[ ! -f "${pid_file}" ]]; then
    printf '%s is not running (no pid file)\n' "${name}"
    return
  fi
  local pid
  pid="$(<"${pid_file}")"
  if [[ "${pid}" =~ ^[0-9]+$ ]] && kill -0 "${pid}" 2>/dev/null; then
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
  else
    printf '%s pid=%s is already stopped\n' "${name}" "${pid}"
  fi
  rm -f "${pid_file}"
}

# Stop accepting requests first, then let the worker finish/close its model.
stop_one api
stop_one worker

