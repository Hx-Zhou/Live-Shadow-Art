#!/usr/bin/env bash
set -euo pipefail

deploy_root="${DEPLOY_ROOT:-/home/ma-user/work/longcat_deploy}"
source "${deploy_root}/runtime_env.sh"

export PIP_CACHE_DIR="${deploy_root}/pip-cache"
export PIP_INDEX_URL="http://pip.modelarts.private.com:8888/repository/pypi/simple"
export PIP_TRUSTED_HOST="pip.modelarts.private.com"

python -m pip install -r "${deploy_root}/compat_constraints.txt"

# Refresh only editable metadata after applying the two packaging-only source
# overlays. Compiled NPU operators remain at the verified source commit.
TORCH_DEVICE_BACKEND_AUTOLOAD=0 VLLM_TARGET_DEVICE=empty VLLM_VERSION_OVERRIDE=0.16.0 \
  python -m pip install --no-build-isolation --no-deps -e "${deploy_root}/src/vllm"
SOC_VERSION=ascend910b3 \
  python -m pip install --no-build-isolation --no-deps -e "${deploy_root}/src/vllm-ascend"

PYTHONPATH= python -m pip check
PYTHONPATH= python - <<'PY'
import importlib.metadata

for distribution in (
    "torch", "torch-npu", "triton-ascend", "vllm", "vllm-ascend", "vllm-omni",
    "transformers", "xgrammar", "opencv-python-headless", "numpy",
):
    print(distribution, importlib.metadata.version(distribution))
PY
