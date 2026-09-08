#!/usr/bin/env bash
set -euo pipefail

deploy_root="${DEPLOY_ROOT:-/home/ma-user/work/longcat_deploy}"
python_base="${PYTHON_BASE:-/home/ma-user/anaconda3/envs/python-3.11.10/bin/python}"
venv_dir="${deploy_root}/venv"
src_dir="${deploy_root}/src"

set +u
source /usr/local/Ascend/cann-8.5.2/set_env.sh
if [[ -r /usr/local/Ascend/nnal/atb/set_env.sh ]]; then
  source /usr/local/Ascend/nnal/atb/set_env.sh
fi
set -u

export ASCEND_VISIBLE_DEVICES="${ASCEND_VISIBLE_DEVICES:-4,7}"
export NPU_VISIBLE_DEVICES="${NPU_VISIBLE_DEVICES:-4,7}"
export PIP_CACHE_DIR="${deploy_root}/pip-cache"
export PIP_INDEX_URL="http://pip.modelarts.private.com:8888/repository/pypi/simple"
export PIP_TRUSTED_HOST="pip.modelarts.private.com"

if [[ ! -x "${venv_dir}/bin/python" ]]; then
  "${python_base}" -m venv "${venv_dir}"
fi

python="${venv_dir}/bin/python"
# CANN's environment prepends the image's MindSpore interpreter. Keep all
# Python-aware CMake projects bound to this isolated environment instead.
export VIRTUAL_ENV="${venv_dir}"
export PATH="${venv_dir}/bin:${PATH}"
export Python_ROOT_DIR="${venv_dir}"
export Python3_ROOT_DIR="${venv_dir}"
"${python}" -m pip install --upgrade pip
"${python}" -m pip install \
  "setuptools==77.0.3" "setuptools-scm>=8" wheel \
  "cmake>=3.26.1" ninja "packaging>=24.2" jinja2 "grpcio-tools==1.78.0" \
  pybind11 nanobind

"${python}" -m pip install \
  "torch==2.9.0" "torchvision==0.24.0" "torchaudio==2.9.0" \
  "triton-ascend==3.2.0"

# ModelArts' internal mirror does not carry the CANN 8.5-compatible 2.9.0
# wheel. Pin the exact PyPI aarch64/cp311 artifact instead of resolving a
# newer post release for another CANN line.
wheel_dir="${deploy_root}/wheels"
torch_npu_wheel="${wheel_dir}/torch_npu-2.9.0-cp311-cp311-manylinux_2_28_aarch64.whl"
mkdir -p "${wheel_dir}"
if [[ ! -s "${torch_npu_wheel}" ]]; then
  curl --fail --location --retry 10 --retry-delay 2 --retry-all-errors \
    --connect-timeout 20 --max-time 600 \
    --output "${torch_npu_wheel}" \
    "https://files.pythonhosted.org/packages/df/91/ea9a22a34ca108e70d9752097228091cccdb28d20af7657653cfd9dc6508/torch_npu-2.9.0-cp311-cp311-manylinux_2_28_aarch64.whl"
fi
echo "6f2bda402cb03b292e6f2327b2e20e8dd688ad5e16642edc184ff4340783ddb2  ${torch_npu_wheel}" | sha256sum -c -
"${python}" -m pip install "${torch_npu_wheel}"

# Pin the vLLM-Ascend NumPy ABI with the exact official PyPI aarch64 wheel.
# This also avoids transient empty-index responses observed from the internal
# ModelArts mirror for constrained NumPy lookups.
numpy_wheel="${wheel_dir}/numpy-1.26.4-cp311-cp311-manylinux_2_17_aarch64.manylinux2014_aarch64.whl"
if [[ ! -s "${numpy_wheel}" ]]; then
  curl --fail --location --retry 10 --retry-delay 2 --retry-all-errors \
    --connect-timeout 20 --max-time 600 \
    --output "${numpy_wheel}" \
    "https://files.pythonhosted.org/packages/79/ae/7e5b85136806f9dadf4878bf73cf223fe5c2636818ba3ab1c585d0403164/numpy-1.26.4-cp311-cp311-manylinux_2_17_aarch64.manylinux2014_aarch64.whl"
fi
echo "7ab55401287bfec946ced39700c053796e7cc0e3acbef09993a9ad2adba6ca6e  ${numpy_wheel}" | sha256sum -c -
"${python}" -m pip install "${numpy_wheel}"

# CANN exposes several Python tools through its environment. Install their
# declared runtime dependencies before any build imports torch/torch_npu.
"${python}" -m pip install \
  pyyaml attrs decorator psutil cloudpickle ml-dtypes scipy \
  tornado absl-py

TORCH_DEVICE_BACKEND_AUTOLOAD=0 VLLM_TARGET_DEVICE=empty VLLM_VERSION_OVERRIDE=0.16.0 \
  "${python}" -m pip install --no-build-isolation -e "${src_dir}/vllm"

SOC_VERSION=ascend910b3 \
  "${python}" -m pip install --no-build-isolation -e "${src_dir}/vllm-ascend"

VLLM_OMNI_TARGET_DEVICE=npu VLLM_OMNI_VERSION_OVERRIDE=0.16.0+npu \
  "${python}" -m pip install --no-build-isolation -e "${src_dir}/vllm-omni"

# Re-assert the shared ABI constraints after editable installs have resolved all
# transitive dependencies. vLLM leaves NumPy open-ended while vLLM-Ascend pins
# the supported 1.x ABI; grpcio-tools also requires protobuf below 7.
"${python}" -m pip install "${numpy_wheel}" \
  "grpcio==1.78.0" "grpcio-reflection==1.78.0" "grpcio-tools==1.78.0" \
  "protobuf==6.33.6"

# CANN's set_env.sh injects system tool metadata with dependencies named after
# Python standard-library modules. Exclude that external PYTHONPATH so pip check
# validates the isolated deployment environment itself.
PYTHONPATH= "${python}" -m pip check
"${python}" - <<'PY'
import torch
import torch_npu
import vllm
import vllm_ascend
import vllm_omni

print("torch", torch.__version__)
print("torch_npu", torch_npu.__version__)
print("vllm", vllm.__version__)
print("vllm_ascend", getattr(vllm_ascend, "__version__", "unknown"))
print("vllm_omni", getattr(vllm_omni, "__version__", "unknown"))
print("npu_available", torch.npu.is_available())
print("npu_count", torch.npu.device_count())
for index in range(torch.npu.device_count()):
    print("npu", index, torch.npu.get_device_name(index), torch.npu.mem_get_info(index))
PY
