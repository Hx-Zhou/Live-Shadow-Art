#!/usr/bin/env python3
"""Collect Public Domain shadow-puppet candidates from The Met Open Access API."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


API_ROOT = "https://collectionapi.metmuseum.org/public/collection/v1"
USER_AGENT = "Live-Shadow-Art-LoRA-Dataset/1.0 (https://github.com/Hx-Zhou/Live-Shadow-Art)"
SEARCH_TERMS = ["Chinese shadow puppet", "shadow puppet China", "Chinese shadow puppets"]


def get_json(url: str) -> dict | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if error.code != 429 or attempt == 4:
                raise
            time.sleep(3 * (2**attempt))
    return None


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-download image files even when a cached file exists.",
    )
    args = parser.parse_args()
    output_dir = args.output.resolve()
    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    object_ids: set[int] = set()
    for term in SEARCH_TERMS:
        query = urllib.parse.urlencode({"hasImages": "true", "q": term})
        result = get_json(f"{API_ROOT}/search?{query}")
        object_ids.update((result or {}).get("objectIDs") or [])

    records: list[dict] = []
    for index, object_id in enumerate(sorted(object_ids), start=1):
        item = get_json(f"{API_ROOT}/objects/{object_id}")
        if item is None:
            continue
        searchable = " ".join(
            str(item.get(key, ""))
            for key in ("title", "objectName", "culture", "country", "classification", "medium")
        ).lower()
        image_url = item.get("primaryImage") or item.get("primaryImageSmall")
        if not item.get("isPublicDomain") or not image_url:
            continue
        if "shadow puppet" not in searchable and "shadow puppets" not in searchable:
            continue
        filename = f"met_{object_id}.jpg"
        destination = image_dir / filename
        if destination.exists() and not args.refresh:
            payload = destination.read_bytes()
        else:
            payload = download(image_url)
            destination.write_bytes(payload)
        records.append(
            {
                "source": "The Metropolitan Museum of Art Open Access",
                "source_category": "Open Access collection API",
                "source_id": str(object_id),
                "title": item.get("title", ""),
                "source_page": item.get("objectURL", ""),
                "download_url": image_url,
                "original_url": item.get("primaryImage", ""),
                "mime": "image/jpeg",
                "original_width": "",
                "original_height": "",
                "artist": item.get("artistDisplayName", ""),
                "credit": item.get("creditLine", ""),
                "description": item.get("objectName", ""),
                "license": "Public Domain / The Met Open Access",
                "license_url": "https://www.metmuseum.org/about-the-met/policies-and-documents/open-access",
                "attribution_required": "No",
                "usage_terms": "Unrestricted commercial and noncommercial use under The Met Open Access policy",
                "downloaded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "filename": filename,
                "relative_path": f"images/{filename}",
                "file_size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "review_status": "unreviewed",
                "dataset_role": "unassigned",
                "quality_grade": "",
                "split": "",
                "caption": "",
                "review_notes": "",
            }
        )
        print(f"checked {index}/{len(object_ids)} object {object_id}", flush=True)
        time.sleep(0.05)

    (output_dir / "met_candidates.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records),
        encoding="utf-8",
    )
    if records:
        with (output_dir / "met_candidates.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    print(f"saved {len(records)} Public Domain candidates to {output_dir}")


if __name__ == "__main__":
    main()
