#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" != "--execute" ]]; then
  cat <<'EOF'
DRY RUN ONLY
用途：拉取匹配 vLLM-Ascend 0.23.0 的官方容器并挂载 NPU、模型目录和项目目录。
成本：镜像通常为十几至数十 GiB；会占用网络、磁盘并启动容器。
确认租用实例的驱动、卡型和磁盘后，使用：
  ASCEND_VARIANT=A2 NPU_COUNT=2 MODEL_CACHE=/data/models bash scripts/01_start_container.sh --execute
或：
  ASCEND_VARIANT=A3 NPU_COUNT=2 MODEL_CACHE=/data/models bash scripts/01_start_container.sh --execute
EOF
  exit 0
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"
variant="${ASCEND_VARIANT:-A2}"
npu_count="${NPU_COUNT:-2}"
model_cache="${MODEL_CACHE:-/data/models}"

case "${variant}" in
  A2) image="quay.io/ascend/vllm-ascend:v0.23.0" ;;
  A3) image="quay.io/ascend/vllm-ascend:v0.23.0-a3" ;;
  *) printf 'ASCEND_VARIANT must be A2 or A3, got: %s\n' "${variant}" >&2; exit 2 ;;
esac

if ! [[ "${npu_count}" =~ ^[1-8]$ ]]; then
  printf 'NPU_COUNT must be an integer from 1 to 8\n' >&2
  exit 2
fi

mkdir -p "${model_cache}"
device_args=()
for ((index=0; index<npu_count; index++)); do
  device_path="/dev/davinci${index}"
  if [[ ! -e "${device_path}" ]]; then
    printf 'Missing device: %s\n' "${device_path}" >&2
    exit 3
  fi
  device_args+=(--device "${device_path}")
done

docker pull "${image}"
docker run --rm -it \
  --name longcat-vllm-omni \
  --ipc=host \
  --shm-size=16g \
  "${device_args[@]}" \
  --device /dev/davinci_manager \
  --device /dev/devmm_svm \
  --device /dev/hisi_hdc \
  -v /usr/local/dcmi:/usr/local/dcmi \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
  -v /usr/local/Ascend/driver/lib64/:/usr/local/Ascend/driver/lib64/ \
  -v /usr/local/Ascend/driver/version.info:/usr/local/Ascend/driver/version.info \
  -v /etc/ascend_install.info:/etc/ascend_install.info \
  -v "${model_cache}:/data/models" \
  -v "${project_dir}:/workspace/project" \
  -p 8091:8091 \
  "${image}" bash

