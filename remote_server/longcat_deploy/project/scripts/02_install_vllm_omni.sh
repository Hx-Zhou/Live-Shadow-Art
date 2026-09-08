#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" != "--execute" ]]; then
  cat <<'EOF'
DRY RUN ONLY
用途：在 vLLM-Ascend 0.23.0 容器中克隆并以 editable 模式安装 vLLM-Omni v0.23.0rc1。
成本：下载源码及 Python 依赖，通常小于模型权重，但可能耗时 5–20 分钟。
执行：bash scripts/02_install_vllm_omni.sh --execute
EOF
  exit 0
fi

omni_root="${OMNI_ROOT:-/vllm-workspace/vllm-omni}"
omni_parent="$(dirname "${omni_root}")"
mkdir -p "${omni_parent}"

python3 - <<'PY'
import vllm
assert vllm.__version__ == "0.23.0", f"Expected vLLM 0.23.0, got {vllm.__version__}"
print("vLLM version OK:", vllm.__version__)
PY

if [[ ! -d "${omni_root}/.git" ]]; then
  git clone --depth 1 --branch v0.23.0rc1 \
    https://github.com/vllm-project/vllm-omni.git "${omni_root}"
else
  printf 'Existing checkout found: %s\n' "${omni_root}"
  git -C "${omni_root}" fetch --depth 1 origin tag v0.23.0rc1
  git -C "${omni_root}" checkout --detach v0.23.0rc1
fi

python3 -m pip install --no-build-isolation -e "${omni_root}"
python3 -m pip check

python3 - <<'PY'
import torch
import torch_npu  # noqa: F401
import vllm
import vllm_ascend
import vllm_omni

print("torch:", torch.__version__)
print("torch_npu:", torch_npu.__version__)
print("vllm:", vllm.__version__)
print("vllm_ascend:", getattr(vllm_ascend, "__version__", "unknown"))
print("vllm_omni:", getattr(vllm_omni, "__version__", "unknown"))
print("NPU available:", torch.npu.is_available())
print("NPU count:", torch.npu.device_count())
PY

runner="${omni_root}/examples/offline_inference/text_to_image/text_to_image.py"
test -f "${runner}"
help_text="$(python3 "${runner}" --help)"
for required_flag in \
  --negative-prompt \
  --guidance-scale \
  --tensor-parallel-size \
  --cfg-parallel-size \
  --ulysses-degree \
  --vae-use-slicing \
  --vae-use-tiling; do
  if ! grep -q -- "${required_flag}" <<<"${help_text}"; then
    printf 'Required runner flag is missing: %s\n' "${required_flag}" >&2
    exit 4
  fi
done
printf 'vLLM-Omni text-to-image CLI contract: OK\n'
