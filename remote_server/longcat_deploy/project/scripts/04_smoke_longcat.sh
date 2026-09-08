#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"
omni_root="${OMNI_ROOT:-/vllm-workspace/vllm-omni}"
model_dir="${MODEL_DIR:-/data/models/LongCat-Image}"
output_root="${OUTPUT_ROOT:-${project_dir}/outputs}"
runner="${omni_root}/examples/offline_inference/text_to_image/text_to_image.py"

[[ -f "${runner}" ]] || { printf 'Missing vLLM-Omni runner: %s\n' "${runner}" >&2; exit 2; }
[[ -d "${model_dir}" ]] || { printf 'Missing model directory: %s\n' "${model_dir}" >&2; exit 2; }
mkdir -p "${output_root}/smoke"

width="${SMOKE_WIDTH:-768}"
height="${SMOKE_HEIGHT:-768}"
steps="${SMOKE_STEPS:-10}"
ulysses="${ULYSSES_DEGREE:-1}"
cfg_parallel="${CFG_PARALLEL_SIZE:-1}"
tensor_parallel="${TENSOR_PARALLEL_SIZE:-1}"
negative_prompt="$(tr '\n' ' ' < "${project_dir}/config/negative_prompt.txt")"
prompt='孙悟空皮影角色，严格侧身完整全身，四肢与躯干分离，金箍棒不与身体重叠，红金黑配色，纯暖白背景，traditional Chinese shadow-puppet cutout, perforated translucent leather, clean silhouette'

args=(
  python3 "${runner}"
  --model "${model_dir}"
  --prompt "${prompt}"
  --negative-prompt "${negative_prompt}"
  --seed 42
  --guidance-scale 4.0
  --num-inference-steps "${steps}"
  --width "${width}"
  --height "${height}"
  --tensor-parallel-size "${tensor_parallel}"
  --cfg-parallel-size "${cfg_parallel}"
  --ulysses-degree "${ulysses}"
  --ring-degree 1
  --output "${output_root}/smoke/longcat_smoke.png"
)

if [[ "${ENABLE_VAE_MEMORY_OPTS:-1}" == "1" ]]; then
  args+=(--vae-use-slicing --vae-use-tiling)
fi

printf 'Running smoke test: %sx%s, steps=%s\n' "${width}" "${height}" "${steps}"
start_time="$(date +%s)"
"${args[@]}" 2>&1 | tee "${output_root}/smoke/longcat_smoke.log"
end_time="$(date +%s)"
printf 'Smoke test wall time: %s seconds\n' "$((end_time - start_time))"
test -s "${output_root}/smoke/longcat_smoke.png"

