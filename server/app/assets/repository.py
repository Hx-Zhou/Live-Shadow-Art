import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .manifest import load_manifest
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
