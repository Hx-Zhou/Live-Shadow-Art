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

extra_args=()
if [[ "${ENABLE_VAE_MEMORY_OPTS:-1}" == "1" ]]; then
  extra_args+=(--vae-memory-opts)
fi

python3 "${project_dir}/tools/benchmark.py" \
  --runner "${runner}" \
  --model "${model_dir}" \
  --cases "${project_dir}/prompts/selection_cases.json" \
  --negative-prompt-file "${project_dir}/config/negative_prompt.txt" \
  --output-dir "${output_root}/benchmark" \
  --seeds "${SEEDS:-42,3407,20260903}" \
  --steps "${BENCHMARK_STEPS:-50}" \
  --guidance-scale "${GUIDANCE_SCALE:-4.0}" \
  --tensor-parallel-size "${TENSOR_PARALLEL_SIZE:-1}" \
  --cfg-parallel-size "${CFG_PARALLEL_SIZE:-1}" \
  --ulysses-degree "${ULYSSES_DEGREE:-1}" \
  --ring-degree "${RING_DEGREE:-1}" \
  "${extra_args[@]}"

