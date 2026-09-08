from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AssetPackResult:
  asset_id: str
  output_dir: Path


def texture_to_assetpack(texture_path: Path, rig_template: Path, output_dir: Path) -> AssetPackResult:
  output_dir.mkdir(parents=True, exist_ok=True)
  asset_id = output_dir.name
  marker = output_dir / "POSTPROCESS_TODO.md"
  marker.write_text(
    "\n".join(
      [
        "# Postprocess TODO",
        "",
        f"- Source texture: `{texture_path}`",
        f"- Rig template: `{rig_template}`",
        "- Split transparent PNG parts.",
        "- Align pivots and export rig.json.",
        "- Write manifest.json with prompt, seed and model version.",
      ]
    )
    + "\n",
    encoding="utf-8",
  )
  return AssetPackResult(asset_id=asset_id, output_dir=output_dir)
