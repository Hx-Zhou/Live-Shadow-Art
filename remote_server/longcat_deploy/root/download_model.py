#!/usr/bin/env python3
"""Pin and download the complete official LongCat-Image Hugging Face snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", default="meituan-longcat/LongCat-Image")
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--revision", default=None, help="Immutable commit resolved from the official Hugging Face API")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    args.model_dir.mkdir(parents=True, exist_ok=True)
    api = HfApi()
    info = None
    for attempt in range(1, 16):
        try:
            info = api.model_info(args.repo_id, revision=args.revision, files_metadata=True)
            break
        except Exception as exc:
            if attempt == 15:
                raise
            delay = min(60, attempt * 5)
            print(
                f"Metadata request attempt {attempt}/15 failed: {type(exc).__name__}: {exc}; "
                f"retrying in {delay}s",
                flush=True,
            )
            time.sleep(delay)
    assert info is not None
    revision = args.revision or info.sha
    if info.sha != revision:
        raise RuntimeError(f"Endpoint resolved {info.sha}, expected pinned revision {revision}")
    expected_bytes = sum(int(item.size or 0) for item in (info.siblings or []))
    started = time.time()
    print(f"Resolved {args.repo_id} to immutable revision {revision}", flush=True)
    print(f"Repository metadata reports {expected_bytes} bytes", flush=True)

    resolved = None
    for attempt in range(1, 11):
        try:
            resolved = snapshot_download(
                repo_id=args.repo_id,
                revision=revision,
                local_dir=str(args.model_dir),
                max_workers=args.workers,
                resume_download=True,
            )
            break
        except Exception as exc:
            if attempt == 10:
                raise
            delay = min(90, attempt * 10)
            print(
                f"Snapshot attempt {attempt}/10 failed: {type(exc).__name__}: {exc}; "
                f"resuming in {delay}s",
                flush=True,
            )
            time.sleep(delay)
    assert resolved is not None
    (args.model_dir / "MODEL_REVISION.txt").write_text(revision + "\n", encoding="utf-8")

    # Hash only lightweight configuration/tokenizer files here. Safetensor shard
    # integrity is already checked against Hugging Face metadata by the client;
    # full shard hashing is captured later with the deployment manifest.
    files = []
    actual_bytes = 0
    for path in sorted(args.model_dir.rglob("*")):
        if not path.is_file() or ".cache" in path.parts:
            continue
        size = path.stat().st_size
        actual_bytes += size
        record: dict[str, object] = {
            "path": str(path.relative_to(args.model_dir)),
            "bytes": size,
        }
        if size <= 64 * 1024 * 1024:
            record["sha256"] = sha256(path)
        files.append(record)

    manifest = {
        "repo_id": args.repo_id,
        "revision": revision,
        "resolved_snapshot": resolved,
        "download_started_epoch": started,
        "download_finished_epoch": time.time(),
        "expected_repository_bytes": expected_bytes,
        "actual_model_file_bytes": actual_bytes,
        "file_count": len(files),
        "hf_endpoint": os.environ.get("HF_ENDPOINT", "https://huggingface.co"),
        "files": files,
    }
    (args.model_dir / "DOWNLOAD_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: manifest[k] for k in manifest if k != "files"}, indent=2), flush=True)


if __name__ == "__main__":
    main()
