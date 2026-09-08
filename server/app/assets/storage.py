from pathlib import Path


class AssetStorage:
  def __init__(self, root: Path):
    self.root = root.resolve()

  def resolve(self, *parts: str) -> Path:
    path = self.root.joinpath(*parts).resolve()
    if self.root not in path.parents and path != self.root:
      raise ValueError(f"Path escapes asset root: {path}")
    return path

  def character_dir(self, asset_id: str) -> Path:
    return self.resolve("characters", asset_id)

  def background_file(self, asset_id: str) -> Path:
    return self.resolve("backgrounds", f"{asset_id}.png")
