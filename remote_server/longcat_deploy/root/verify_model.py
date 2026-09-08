#!/usr/bin/env python3
"""Verify the pinned LongCat snapshot and every safetensors shard header."""

import argparse
import hashlib
import json
from pathlib import Path

from safetensors import safe_open


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    revision = (args.model_dir / "MODEL_REVISION.txt").read_text().strip()
    if revision != args.expected_revision:
        raise RuntimeError(f"revision mismatch: {revision} != {args.expected_revision}")

    shards = []
    for path in sorted(args.model_dir.rglob("*.safetensors")):
        relative = str(path.relative_to(args.model_dir))
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                digest.update(block)
        with safe_open(path, framework="pt", device="cpu") as archive:
            keys = list(archive.keys())
        shards.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": digest.hexdigest(),
                "tensor_count": len(keys),
                "status": "PASS",
            }
        )

    files = [path for path in args.model_dir.rglob("*") if path.is_file()]
    report = {
        "model_dir": str(args.model_dir),
        "revision": revision,
        "file_count_recursive": len(files),
        "bytes_recursive": sum(path.stat().st_size for path in files),
        "safetensors_shard_count": len(shards),
        "safetensors": shards,
        "overall": "PASS" if shards else "FAIL",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not shards:
        raise RuntimeError("no safetensors shards found")


if __name__ == "__main__":
    main()
