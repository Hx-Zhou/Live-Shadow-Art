#!/usr/bin/env bash
set -uo pipefail

report_path="${1:-preflight_$(date +%Y%m%d_%H%M%S).log}"
exec > >(tee "${report_path}") 2>&1

section() {
  printf '\n===== %s =====\n' "$1"
}

try_run() {
  "$@" || printf '[WARN] command failed or unavailable: %s\n' "$*"
}

section "timestamp"
date -Is

section "system"
try_run uname -a
try_run lscpu
try_run free -h
try_run df -h

section "npu-smi"
try_run npu-smi info

section "Ascend versions"
try_run atc --version
for version_file in \
  /usr/local/Ascend/driver/version.info \
  /usr/local/Ascend/ascend-toolkit/latest/version.cfg; do
  if [[ -r "${version_file}" ]]; then
    printf '\n--- %s ---\n' "${version_file}"
    sed -n '1,120p' "${version_file}"
  fi
done

section "relevant environment variables"
env | sort | grep -E '^(ASCEND|NPU|HCCL|VLLM|LD_LIBRARY_PATH|PATH)=' || true

section "Python packages and device"
python3 - <<'PY' || true
import importlib
import platform
import sys

print("python:", sys.version.replace("\n", " "))
print("platform:", platform.platform())
for name in ("torch", "torch_npu", "vllm", "vllm_ascend", "vllm_omni", "diffusers", "transformers"):
    try:
        module = importlib.import_module(name)
        print(f"{name}: {getattr(module, '__version__', 'version-unknown')}")
    except Exception as exc:
        print(f"{name}: IMPORT_FAILED: {type(exc).__name__}: {exc}")

try:
    import torch
    import torch_npu  # noqa: F401
    print("npu_available:", torch.npu.is_available())
    print("npu_count:", torch.npu.device_count())
    for index in range(torch.npu.device_count()):
        print(f"npu_{index}_name:", torch.npu.get_device_name(index))
        try:
            print(f"npu_{index}_mem_get_info:", torch.npu.mem_get_info(index))
        except Exception as exc:
            print(f"npu_{index}_mem_get_info_failed:", exc)
except Exception as exc:
    print("torch_npu_probe_failed:", type(exc).__name__, exc)
PY

section "container and source tools"
try_run docker version
try_run git --version

section "result"
printf 'Preflight report saved to: %s\n' "${report_path}"

