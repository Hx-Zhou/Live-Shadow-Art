#!/usr/bin/env bash
# Source this file before every LongCat inference or diagnostic command.

deploy_root="${DEPLOY_ROOT:-/home/ma-user/work/longcat_deploy}"
venv_dir="${deploy_root}/venv"

set +u
source /usr/local/Ascend/cann-8.5.2/set_env.sh
if [[ -r /usr/local/Ascend/nnal/atb/set_env.sh ]]; then
  source /usr/local/Ascend/nnal/atb/set_env.sh
fi
set -u

export VIRTUAL_ENV="${venv_dir}"
export PATH="${venv_dir}/bin:${PATH}"
# ModelArts injects the physical-device visibility list when the instance starts.
# Preserve that current value instead of baking one server generation's card IDs
# into the repository. Do not set ASCEND_RT_VISIBLE_DEVICES here: doing so applies
# a second physical-ID filter and can make logical device 0 invalid.
unset ASCEND_RT_VISIBLE_DEVICES
if [[ -n "${ASCEND_VISIBLE_DEVICES:-}" ]]; then
  export ASCEND_VISIBLE_DEVICES
fi
if [[ -n "${NPU_VISIBLE_DEVICES:-}" ]]; then
  export NPU_VISIBLE_DEVICES
fi
export PYTHONUNBUFFERED=1
export TOKENIZERS_PARALLELISM=false
export HF_HOME="${HF_HOME:-${deploy_root}/hf-cache}"
export HCCL_CONNECT_TIMEOUT="${HCCL_CONNECT_TIMEOUT:-1200}"
export HCCL_EXEC_TIMEOUT="${HCCL_EXEC_TIMEOUT:-7200}"
export TORCH_DEVICE_BACKEND_AUTOLOAD=1
