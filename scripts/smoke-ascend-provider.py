#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from server.app.assets.repository import AssetRepository
from server.app.generation.ascend_provider import AscendGenerationProvider
from server.app.schemas import TextureGenerateRequest
from server.app.settings import Settings


def main() -> None:
  parser = argparse.ArgumentParser(description="Run one real LongCat LoRA provider smoke test")
  parser.add_argument("--api", default="http://127.0.0.1:8010")
  parser.add_argument("--seed", type=int, default=2026090901)
  args = parser.parse_args()

  with tempfile.TemporaryDirectory(prefix="longcat-provider-smoke-") as temporary:
    asset_root = Path(temporary)
    (asset_root / "demo").mkdir(parents=True)
    (asset_root / "demo" / "catalog.json").write_text(
      json.dumps({"characters": [], "backgrounds": []}), encoding="utf-8"
    )
    settings = Settings(
      PROVIDER="ascend",
      ASSET_ROOT=asset_root,
      ASCEND_API_BASE_URL=args.api,
      ASCEND_API_POLL_INTERVAL_SECONDS=1,
    )
    repository = AssetRepository(asset_root)
    provider = AscendGenerationProvider(settings, repository)
    result = provider.generate(
      TextureGenerateRequest(
        kind="background",
        style="traditional_shadow_puppet",
        prompt=(
          "江南水乡夜景，远景屋檐和拱桥，"
          "中央水面留出宽阔角色表演区"
        ),
        negativePrompt="现代建筑，人物，文字，水印",
        seed=args.seed,
      )
    )
    record = repository.get(result.asset_id)
    metadata = json.loads(
      (asset_root / "backgrounds" / f"{result.asset_id}.json").read_text(encoding="utf-8")
    )
    output = {
      "ok": True,
      "assetId": result.asset_id,
      "message": result.message,
      "previewUrl": record.preview_url,
      "adapterRevision": metadata["source"]["adapterRevision"],
      "adapterScale": metadata["source"]["adapterScale"],
      "seed": metadata["source"]["seed"],
      "savedPngBytes": (
        asset_root / "backgrounds" / f"{result.asset_id}.png"
      ).stat().st_size,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
  main()
