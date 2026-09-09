import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from .manifest import load_manifest, write_manifest
from .storage import AssetStorage


class AssetNotFoundError(LookupError):
  pass


@dataclass(frozen=True)
class AssetRecord:
  id: str
  kind: Literal["character", "background"]
  name: str
  base_url: str
  manifest_url: str
  preview_url: str | None = None


class AssetRepository:
  def __init__(self, root: Path):
    self.storage = AssetStorage(root)
    self._catalog_lock = threading.Lock()

  def get(self, asset_id: str) -> AssetRecord:
    catalog = self.catalog()
    for item in catalog["characters"]:
      if item["id"] == asset_id:
        manifest_path = self.storage.character_dir(asset_id) / "manifest.json"
        manifest = load_manifest(manifest_path)
        return AssetRecord(
          id=asset_id,
          kind="character",
          name=manifest["name"],
          base_url=f"/static/characters/{asset_id}",
          manifest_url=f"/static/characters/{asset_id}/manifest.json",
          preview_url=f"/static/characters/{asset_id}/preview.png",
        )
    for item in catalog["backgrounds"]:
      if item["id"] == asset_id:
        file_path = self.storage.background_file(asset_id)
        if not file_path.exists():
          raise AssetNotFoundError(asset_id)
        return AssetRecord(
          id=asset_id,
          kind="background",
          name=item["name"],
          base_url=f"/static/backgrounds/{asset_id}.png",
          manifest_url=f"/static/backgrounds/{asset_id}.json",
          preview_url=f"/static/backgrounds/{asset_id}.png",
        )
    raise AssetNotFoundError(asset_id)

  def first(self, kind: Literal["character", "background"]) -> AssetRecord:
    catalog = self.catalog()
    items = catalog["characters"] if kind == "character" else catalog["backgrounds"]
    if not items:
      raise AssetNotFoundError(kind)
    return self.get(items[0]["id"])

  def catalog(self) -> dict:
    path = self.storage.resolve("demo", "catalog.json")
    return json.loads(path.read_text(encoding="utf-8"))

  def save_generated_image(
    self,
    *,
    kind: Literal["character", "background"],
    image: bytes,
    prompt: str,
    negative_prompt: str | None,
    seed: int,
    remote_task_id: str,
    adapter_revision: str,
    adapter_scale: float,
  ) -> AssetRecord:
    if not image.startswith(b"\x89PNG\r\n\x1a\n"):
      raise ValueError("Ascend API result is not a PNG image")

    asset_id = f"longcat_{kind}_{uuid4().hex[:12]}"
    display_name = f"LoRA 生成{'角色' if kind == 'character' else '场景'} {asset_id[-6:]}"
    source = {
      "provider": "longcat-ascend-lora",
      "modelVersion": f"LongCat-Image+LoRA:{adapter_revision[:12]}",
      "adapterRevision": adapter_revision,
      "adapterScale": adapter_scale,
      "remoteTaskId": remote_task_id,
      "prompt": prompt,
      "negativePrompt": negative_prompt,
      "seed": seed,
      "createdAt": datetime.now(timezone.utc).isoformat(),
    }

    with self._catalog_lock:
      catalog = self.catalog()
      if kind == "background":
        image_path = self.storage.background_file(asset_id)
        image_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_bytes_atomic(image_path, image)
        metadata_path = self.storage.resolve("backgrounds", f"{asset_id}.json")
        self._write_json_atomic(
          metadata_path,
          {
            "id": asset_id,
            "kind": kind,
            "name": display_name,
            "version": "1.0.0",
            "source": source,
            "parts": [f"{asset_id}.png"],
            "rig": None,
            "preview": f"{asset_id}.png",
            "tags": ["generated", "background", "shadow-puppet", "longcat-lora"],
          },
        )
        catalog["backgrounds"].append({"id": asset_id, "name": display_name})
      else:
        output_dir = self.storage.character_dir(asset_id)
        output_dir.mkdir(parents=True, exist_ok=False)
        self._write_bytes_atomic(output_dir / "source.png", image)
        self._write_bytes_atomic(output_dir / "preview.png", image)
        write_manifest(
          output_dir / "manifest.json",
          {
            "id": asset_id,
            "kind": kind,
            "name": display_name,
            "version": "1.0.0",
            "source": source,
            "parts": [],
            "rig": None,
            "preview": "preview.png",
            "tags": [
              "generated",
              "character",
              "shadow-puppet",
              "longcat-lora",
              "unrigged",
            ],
          },
        )
        catalog["characters"].append({"id": asset_id, "name": display_name})

      self._write_json_atomic(self.storage.resolve("demo", "catalog.json"), catalog)

    return self.get(asset_id)

  @staticmethod
  def _write_bytes_atomic(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)

  @staticmethod
  def _write_json_atomic(path: Path, content: dict) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
      json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)
