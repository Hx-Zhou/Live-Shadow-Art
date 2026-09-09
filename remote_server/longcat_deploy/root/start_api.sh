#!/usr/bin/env bash
set -euo pipefail

deploy_root="${DEPLOY_ROOT:-/home/ma-user/work/longcat_deploy}"
source "${deploy_root}/runtime_env.sh"
source "${deploy_root}/process_utils.sh"
if [[ -r "${deploy_root}/api.env" ]]; then
  # api.env is deliberately server-local and ignored by Git. It may contain the
  # team token and the selected adapter, so never copy it into the repository.
  source "${deploy_root}/api.env"
fi

export LONGCAT_API_MODEL_DIR="${LONGCAT_API_MODEL_DIR:-${deploy_root}/models/LongCat-Image}"
export LONGCAT_API_STATE_DIR="${LONGCAT_API_STATE_DIR:-${deploy_root}/api_state}"
export LONGCAT_API_OUTPUT_DIR="${LONGCAT_API_OUTPUT_DIR:-${LONGCAT_API_STATE_DIR}/outputs}"
export LONGCAT_API_ENGINE="${LONGCAT_API_ENGINE:-omni}"
export LONGCAT_API_TP="${LONGCAT_API_TP:-2}"
export LONGCAT_API_CFG_PARALLEL="${LONGCAT_API_CFG_PARALLEL:-1}"
export LONGCAT_API_ULYSSES="${LONGCAT_API_ULYSSES:-1}"
export LONGCAT_API_RING="${LONGCAT_API_RING:-1}"
export LONGCAT_API_VAE_SLICING="${LONGCAT_API_VAE_SLICING:-1}"
export LONGCAT_API_VAE_TILING="${LONGCAT_API_VAE_TILING:-1}"
export LONGCAT_API_HOST="${LONGCAT_API_HOST:-127.0.0.1}"
export LONGCAT_API_PORT="${LONGCAT_API_PORT:-8010}"
if [[ -n "${LONGCAT_API_EXTRA_PYTHONPATH:-}" ]]; then
  export PYTHONPATH="${LONGCAT_API_EXTRA_PYTHONPATH}:${deploy_root}:${PYTHONPATH:-}"
else
  export PYTHONPATH="${deploy_root}:${PYTHONPATH:-}"
fi

run_dir="${LONGCAT_API_STATE_DIR}/run"
log_dir="${LONGCAT_API_STATE_DIR}/logs"
mkdir -p "${run_dir}" "${log_dir}" "${LONGCAT_API_OUTPUT_DIR}"

worker_pid_file="${run_dir}/worker.pid"
api_pid_file="${run_dir}/api.pid"

check_not_running() {
  local name="$1"
  local pid_file="$2"
  local expected="$3"
  local pid
  if pid="$(read_service_pid "${pid_file}")" && service_pid_matches "${pid}" "${expected}"; then
    printf '%s is already running (pid=%s)\n' "${name}" "${pid}" >&2
    return 1
  fi
  if [[ -e "${pid_file}" ]]; then
    printf 'Discarding stale %s PID file; no matching service owns it.\n' "${name}" >&2
    rm -f "${pid_file}"
  fi
}

check_not_running worker "${worker_pid_file}" "python -m api_service.worker"
check_not_running api "${api_pid_file}" "uvicorn api_service.app:app"

nohup python -m api_service.worker >> "${log_dir}/worker.log" 2>&1 &
worker_pid=$!
printf '%s\n' "${worker_pid}" > "${worker_pid_file}"

nohup python -m uvicorn api_service.app:app \
  --host "${LONGCAT_API_HOST}" \
  --port "${LONGCAT_API_PORT}" \
  --workers 1 \
  --no-access-log >> "${log_dir}/api.log" 2>&1 &
api_pid=$!
printf '%s\n' "${api_pid}" > "${api_pid_file}"

printf 'api_pid=%s\nworker_pid=%s\nlisten=http://%s:%s\n' \
  "${api_pid}" "${worker_pid}" "${LONGCAT_API_HOST}" "${LONGCAT_API_PORT}"
printf 'The API process starts quickly; /health reports ready=true after model loading completes.\n'
