#!/usr/bin/env bash
set -euo pipefail

deploy_root="${DEPLOY_ROOT:-/home/ma-user/work/longcat_deploy}"
result_root="${RESULT_ROOT:-${deploy_root}/results}"
project_root="${deploy_root}/project"
smoke_root="${result_root}/smoke"
mkdir -p "${smoke_root}"
source "${deploy_root}/runtime_env.sh"

run_id="$(date +%Y%m%dT%H%M%S)"
stop_file="/tmp/longcat_smoke_monitor_${run_id}.stop"
monitor_log="${smoke_root}/npu_monitor_${run_id}.log"
monitor_csv="${smoke_root}/npu_monitor_${run_id}.csv"

python "${deploy_root}/npu_monitor.py" \
  --output "${monitor_csv}" \
  --stop-file "${stop_file}" \
  --interval 2 \
  --device-ids 4,7 > "${monitor_log}" 2>&1 &
monitor_pid=$!

finish_monitor() {
  touch "${stop_file}"
  wait "${monitor_pid}" || true
  printf 'monitor_csv=%s\n' "${monitor_csv}"
}
trap finish_monitor EXIT

export OMNI_ROOT="${deploy_root}/src/vllm-omni"
export MODEL_DIR="${deploy_root}/models/LongCat-Image"
export OUTPUT_ROOT="${result_root}"
export SMOKE_WIDTH="${SMOKE_WIDTH:-768}"
export SMOKE_HEIGHT="${SMOKE_HEIGHT:-768}"
export SMOKE_STEPS="${SMOKE_STEPS:-10}"
export ULYSSES_DEGREE="${ULYSSES_DEGREE:-2}"
export RING_DEGREE="${RING_DEGREE:-1}"
export TENSOR_PARALLEL_SIZE="${TENSOR_PARALLEL_SIZE:-1}"
export CFG_PARALLEL_SIZE="${CFG_PARALLEL_SIZE:-1}"
export ENABLE_VAE_MEMORY_OPTS="${ENABLE_VAE_MEMORY_OPTS:-1}"

printf 'smoke_started_epoch=%s\n' "$(date +%s)"
bash "${project_root}/scripts/04_smoke_longcat.sh"
printf 'smoke_finished_epoch=%s\n' "$(date +%s)"
