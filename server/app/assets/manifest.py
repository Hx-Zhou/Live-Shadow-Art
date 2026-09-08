import json
from pathlib import Path
from typing import Any


REQUIRED_MANIFEST_FIELDS = {"id", "kind", "name", "version", "source", "parts", "rig"}


def load_manifest(path: Path) -> dict[str, Any]:
  data = json.loads(path.read_text(encoding="utf-8"))
  missing = REQUIRED_MANIFEST_FIELDS - data.keys()
  if missing:
    raise ValueError(f"Manifest {path} is missing fields: {', '.join(sorted(missing))}")
  return data


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
