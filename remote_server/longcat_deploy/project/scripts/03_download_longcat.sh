#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" != "--execute" ]]; then
  cat <<'EOF'
DRY RUN ONLY
用途：解析 LongCat-Image 当前提交 SHA，按该 SHA 下载完整模型并写入 MODEL_REVISION.txt。
成本：vLLM-Omni 官方资源表记录模型文件约 27.3 GiB；建议预留至少 60 GiB 临时空间。
执行：MODEL_DIR=/data/models/LongCat-Image bash scripts/03_download_longcat.sh --execute
EOF
  exit 0
fi

model_id="${MODEL_ID:-meituan-longcat/LongCat-Image}"
model_dir="${MODEL_DIR:-/data/models/LongCat-Image}"
mkdir -p "${model_dir}"

MODEL_ID="${model_id}" MODEL_DIR="${model_dir}" python3 - <<'PY'
import os
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download

model_id = os.environ["MODEL_ID"]
model_dir = Path(os.environ["MODEL_DIR"]).resolve()
info = HfApi().model_info(model_id)
revision = info.sha
print(f"Resolved {model_id} revision: {revision}")

snapshot_download(
    repo_id=model_id,
    revision=revision,
    local_dir=str(model_dir),
)
(model_dir / "MODEL_REVISION.txt").write_text(revision + "\n", encoding="utf-8")
print(f"Downloaded to: {model_dir}")
print(f"Pinned revision written to: {model_dir / 'MODEL_REVISION.txt'}")
PY

du -sh "${model_dir}"

