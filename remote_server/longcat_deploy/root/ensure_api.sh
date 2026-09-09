#!/usr/bin/env bash
set -euo pipefail

deploy_root="${DEPLOY_ROOT:-/home/ma-user/work/longcat_deploy}"
source "${deploy_root}/runtime_env.sh"
source "${deploy_root}/process_utils.sh"
if [[ -r "${deploy_root}/api.env" ]]; then
  source "${deploy_root}/api.env"
fi

state_dir="${LONGCAT_API_STATE_DIR:-${deploy_root}/api_state}"
run_dir="${state_dir}/run"
host="${LONGCAT_API_HOST:-127.0.0.1}"
port="${LONGCAT_API_PORT:-8010}"
timeout_seconds="${LONGCAT_API_STARTUP_TIMEOUT:-360}"
expected_engine="${LONGCAT_API_ENGINE:-diffusers-lora}"
expected_revision="${LONGCAT_API_ADAPTER_REVISION:-}"
health_url="http://${host}:${port}/health"

if [[ ! -d "${LONGCAT_API_MODEL_DIR:-${deploy_root}/models/LongCat-Image}" ]]; then
  printf 'Model directory is missing from the persistent volume.\n' >&2
  exit 1
fi
if [[ "${expected_engine}" == "diffusers-lora" ]] \
  && [[ ! -d "${LONGCAT_API_ADAPTER_DIR:-}" ]]; then
  printf 'LoRA adapter directory is missing from the persistent volume.\n' >&2
  exit 1
fi

health_body() {
  curl --connect-timeout 2 --max-time 4 -fsS "${health_url}" 2>/dev/null || true
}

health_matches() {
  local body="$1"
  [[ "${body}" == *'"ok":true'* ]] \
    && [[ "${body}" == *'"ready":true'* ]] \
    && [[ "${body}" == *"\"engine\":\"${expected_engine}\""* ]] \
    && { [[ -z "${expected_revision}" ]] \
      || [[ "${body}" == *"\"adapterRevision\":\"${expected_revision}\""* ]]; }
}

service_alive() {
  local name="$1"
  local expected="$2"
  local pid
  pid="$(read_service_pid "${run_dir}/${name}.pid")" || return 1
  service_pid_matches "${pid}" "${expected}"
}

wait_until_ready() {
  local elapsed=0
  local body
  while (( elapsed <= timeout_seconds )); do
    body="$(health_body)"
    if health_matches "${body}"; then
      printf '%s\n' "${body}"
      return 0
    fi
    sleep 3
    elapsed=$((elapsed + 3))
  done
  printf 'LongCat API did not become ready within %s seconds.\n' "${timeout_seconds}" >&2
  return 1
}

body="$(health_body)"
if health_matches "${body}"; then
  printf 'LongCat LoRA API is already ready.\n%s\n' "${body}"
  exit 0
fi

worker_alive=0
api_alive=0
service_alive worker "python -m api_service.worker" && worker_alive=1
service_alive api "uvicorn api_service.app:app" && api_alive=1

if (( worker_alive == 1 && api_alive == 1 )); then
  if [[ "${body}" == *'"ready":true'* ]]; then
    printf 'Running API uses an unexpected engine or adapter; restarting it.\n' >&2
    "${deploy_root}/stop_api.sh"
    "${deploy_root}/start_api.sh"
  else
    printf 'LongCat processes are running; waiting for model warm-up.\n'
  fi
else
  if (( worker_alive == 1 || api_alive == 1 )); then
    printf 'Found a partial LongCat service; replacing it safely.\n' >&2
    "${deploy_root}/stop_api.sh"
  fi
  "${deploy_root}/start_api.sh"
fi

wait_until_ready
