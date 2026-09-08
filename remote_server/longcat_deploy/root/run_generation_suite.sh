#!/usr/bin/env bash
set -euo pipefail

deploy_root="${DEPLOY_ROOT:-/home/ma-user/work/longcat_deploy}"
result_root="${RESULT_ROOT:-${deploy_root}/results}"
suite_name="${SUITE_NAME:?SUITE_NAME is required}"
suite_root="${result_root}/${suite_name}"
cases_file="${CASES_FILE:-${deploy_root}/project/prompts/selection_cases.json}"
negative_prompt_file="${NEGATIVE_PROMPT_FILE:-${deploy_root}/project/config/negative_prompt.txt}"
mkdir -p "${suite_root}"
source "${deploy_root}/runtime_env.sh"

run_id="$(date +%Y%m%dT%H%M%S)"
stop_file="/tmp/longcat_${suite_name}_${run_id}.stop"
monitor_csv="${suite_root}/npu_monitor_${run_id}.csv"
monitor_log="${suite_root}/npu_monitor_${run_id}.log"

python "${deploy_root}/npu_monitor.py" \
  --output "${monitor_csv}" \
  --stop-file "${stop_file}" \
  --interval "${MONITOR_INTERVAL:-2}" \
  --device-ids 4,7 > "${monitor_log}" 2>&1 &
monitor_pid=$!

finish_monitor() {
  touch "${stop_file}"
  wait "${monitor_pid}" || true
  printf 'monitor_csv=%s\n' "${monitor_csv}"
}
trap finish_monitor EXIT

args=(
  python "${deploy_root}/batch_generate.py"
  --model "${deploy_root}/models/LongCat-Image"
  --cases "${cases_file}"
  --negative-prompt-file "${negative_prompt_file}"
  --output-dir "${suite_root}"
  --seeds "${SEEDS:-42,3407,20260903}"
  --steps "${STEPS:-50}"
  --guidance-scale "${GUIDANCE_SCALE:-4.0}"
  --tensor-parallel-size "${TENSOR_PARALLEL_SIZE:-2}"
  --cfg-parallel-size "${CFG_PARALLEL_SIZE:-1}"
  --ulysses-degree "${ULYSSES_DEGREE:-1}"
  --ring-degree "${RING_DEGREE:-1}"
  --vae-use-slicing
  --vae-use-tiling
)

if [[ "${STABILITY_RUNS:-0}" != "0" ]]; then
  args+=(--stability-runs "${STABILITY_RUNS}" --stability-seed-base "${STABILITY_SEED_BASE:-91000}")
fi
if [[ "${ENFORCE_EAGER:-0}" == "1" ]]; then
  args+=(--enforce-eager)
fi

printf 'suite_started_epoch=%s\n' "$(date +%s)"
printf 'suite_name=%s\n' "${suite_name}"
printf 'command='; printf '%q ' "${args[@]}"; printf '\n'
"${args[@]}"
printf 'suite_finished_epoch=%s\n' "$(date +%s)"
