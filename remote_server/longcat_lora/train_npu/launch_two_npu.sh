#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 CONFIG_YAML" >&2
  exit 2
fi

training_root=/home/ma-user/work/longcat_lora
inference_venv=/home/ma-user/work/longcat_deploy/venv
config_path=$1

export PYTHONPATH="${training_root}/python_packages:${training_root}/src/LongCat-Image:${training_root}/train_npu"
export TOKENIZERS_PARALLELISM=false
export HCCL_CONNECT_TIMEOUT=1200
export HCCL_EXEC_TIMEOUT=7200
export ASCEND_LAUNCH_BLOCKING=0

exec "${inference_venv}/bin/torchrun" \
  --standalone \
  --nnodes=1 \
  --nproc-per-node=2 \
  "${training_root}/train_npu/train_lora_npu.py" \
  --config "${config_path}"
