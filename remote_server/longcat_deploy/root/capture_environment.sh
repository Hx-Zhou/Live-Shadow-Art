#!/usr/bin/env bash
set -euo pipefail

deploy_root="${DEPLOY_ROOT:-/home/ma-user/work/longcat_deploy}"
result_root="${RESULT_ROOT:-${deploy_root}/results}"
mkdir -p "${result_root}/environment"

source "${deploy_root}/runtime_env.sh"

# CANN adds its compiler helpers to PYTHONPATH.  Their vendor metadata lists
# Python standard-library modules as third-party requirements, which makes pip
# report false positives.  Check only the isolated venv metadata here.
PYTHONPATH= python -m pip check > "${result_root}/environment/pip_check.log" 2>&1
python -m pip freeze --all > "${result_root}/environment/requirements_frozen.txt"
npu-smi info > "${result_root}/environment/npu_smi_full.log" 2>&1
npu-smi info -t usages -i 4 > "${result_root}/environment/npu_4_idle_usage.log" 2>&1
npu-smi info -t usages -i 7 > "${result_root}/environment/npu_7_idle_usage.log" 2>&1

python - <<'PY' > "${result_root}/environment/python_versions.log" 2>&1
import platform
import sys
from importlib.metadata import version

import torch
import torch_npu

print("python", sys.version.replace("\n", " "))
print("platform", platform.platform())
print("torch", torch.__version__)
print("torch_npu", torch_npu.__version__)
print("vllm", version("vllm"))
print("vllm_ascend", version("vllm-ascend"))
print("vllm_omni", version("vllm-omni"))
print("diffusers", version("diffusers"))
print("transformers", version("transformers"))
print("huggingface_hub", version("huggingface-hub"))
print("npu_available", torch.npu.is_available())
print("npu_count", torch.npu.device_count())
for index in range(torch.npu.device_count()):
    print("npu", index, torch.npu.get_device_name(index), torch.npu.mem_get_info(index))
PY

{
  printf 'hostname=%s\n' "$(hostname)"
  printf 'kernel=%s\n' "$(uname -a)"
  printf 'cann_path=%s\n' "${ASCEND_HOME_PATH:-/usr/local/Ascend/cann-8.5.2}"
  printf 'vllm_commit=%s\n' "$(git -C "${deploy_root}/src/vllm" rev-parse HEAD)"
  printf 'vllm_ascend_commit=%s\n' "$(git -C "${deploy_root}/src/vllm-ascend" rev-parse HEAD)"
  printf 'vllm_omni_commit=%s\n' "$(git -C "${deploy_root}/src/vllm-omni" rev-parse HEAD)"
  printf 'model_revision=%s\n' "$(tr -d '\n' < "${deploy_root}/models/LongCat-Image/MODEL_REVISION.txt")"
  printf 'modelarts_physical_npus=%s\n' "${ASCEND_VISIBLE_DEVICES:-4,7}"
  printf 'process_logical_npus=0,1\n'
} > "${result_root}/environment/version_manifest.txt"
