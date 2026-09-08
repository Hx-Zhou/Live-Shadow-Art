#!/usr/bin/env python3
"""Collect license-filtered Chinese shadow-puppet candidates from Wikimedia Commons."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


API_URL = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "Live-Shadow-Art-LoRA-Dataset/1.0 (https://github.com/Hx-Zhou/Live-Shadow-Art)"
DEFAULT_CATEGORIES = [
    "Category:Shadow puppets from China",
    "Category:Shadow play in China",
]


def strip_html(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def api_get(params: dict[str, str | int]) -> dict:
    query = urllib.parse.urlencode({"format": "json", "formatversion": 2, **params})
    request = urllib.request.Request(f"{API_URL}?{query}", headers={"User-Agent": USER_AGENT})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == 5:
                raise
            time.sleep(5 * (2**attempt))
    raise RuntimeError("unreachable")


def list_subcategories(category: str) -> list[str]:
    found: list[str] = []
    continuation: dict[str, str] = {}
    while True:
        payload = api_get(
            {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": category,
                "cmtype": "subcat",
                "cmlimit": 500,
                **continuation,
            }
        )
        found.extend(item["title"] for item in payload.get("query", {}).get("categorymembers", []))
        continuation = payload.get("continue", {})
        if not continuation:
            return found


def expand_categories(roots: list[str], depth: int) -> list[str]:
    seen = set(roots)
    frontier = list(roots)
    for _ in range(depth):
        next_frontier: list[str] = []
        for category in frontier:
            for child in list_subcategories(category):
                if child not in seen:
                    seen.add(child)
                    next_frontier.append(child)
            time.sleep(0.05)
        frontier = next_frontier
    return sorted(seen)


def allowed_license(short_name: str) -> bool:
    normalized = short_name.upper().replace("–", "-")
    if "ND" in normalized:
        return False
    return normalized.startswith("CC BY") or normalized in {
        "CC0",
        "PUBLIC DOMAIN",
        "PDM",
    }


def metadata_value(metadata: dict, key: str) -> str:
    return strip_html(metadata.get(key, {}).get("value", ""))


def collect_category(category: str) -> list[dict]:
    records: list[dict] = []
    continuation: dict[str, str] = {}
    while True:
        payload = api_get(
            {
                "action": "query",
                "generator": "categorymembers",
                "gcmtitle": category,
                "gcmtype": "file",
                "gcmlimit": 500,
                "prop": "imageinfo|info",
                "inprop": "url",
                "iiprop": "url|size|mime|extmetadata",
                "iiurlwidth": 1600,
                **continuation,
            }
        )
        for page in payload.get("query", {}).get("pages", []):
            image_info = (page.get("imageinfo") or [{}])[0]
            metadata = image_info.get("extmetadata") or {}
            license_short = metadata_value(metadata, "LicenseShortName")
            mime = image_info.get("mime", "")
            if mime not in {"image/jpeg", "image/png"} or not allowed_license(license_short):
                continue
            records.append(
                {
                    "source": "Wikimedia Commons",
                    "source_category": category,
                    "source_id": str(page["pageid"]),
                    "title": page.get("title", "").removeprefix("File:"),
                    "source_page": page.get("fullurl", ""),
                    "download_url": image_info.get("thumburl") or image_info.get("url", ""),
                    "original_url": image_info.get("url", ""),
                    "mime": mime,
                    "original_width": image_info.get("width"),
                    "original_height": image_info.get("height"),
                    "artist": metadata_value(metadata, "Artist"),
                    "credit": metadata_value(metadata, "Credit"),
                    "description": metadata_value(metadata, "ImageDescription"),
                    "license": license_short,
                    "license_url": metadata_value(metadata, "LicenseUrl"),
                    "noncommercial_only": "NC" in license_short.upper(),
                    "attribution_required": metadata_value(metadata, "AttributionRequired"),
                    "usage_terms": metadata_value(metadata, "UsageTerms"),
                }
            )
        continuation = payload.get("continue", {})
        if not continuation:
            return records


def download(record: dict, image_dir: Path) -> dict:
    suffix = ".png" if record["mime"] == "image/png" else ".jpg"
    filename = f"commons_{int(record['source_id']):07d}{suffix}"
    destination = image_dir / filename
    if destination.exists():
        payload = destination.read_bytes()
    else:
        request = urllib.request.Request(record["download_url"], headers={"User-Agent": USER_AGENT})
        for attempt in range(6):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    payload = response.read()
                break
            except urllib.error.HTTPError as error:
                if error.code != 429 or attempt == 5:
                    raise
                time.sleep(5 * (2**attempt))
        destination.write_bytes(payload)
    return {
        **record,
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


def write_manifests(records: list[dict], output_dir: Path) -> None:
    jsonl_path = output_dir / "commons_candidates.jsonl"
    jsonl_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records),
        encoding="utf-8",
    )
    if not records:
        return
    with (output_dir / "commons_candidates.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--category", action="append", dest="categories")
    parser.add_argument("--limit", type=int, default=0, help="Maximum unique files; 0 means all.")
    args = parser.parse_args()

    output_dir = args.output.resolve()
    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    categories = expand_categories(args.categories or DEFAULT_CATEGORIES, args.depth)

    by_id: dict[str, dict] = {}
    for category in categories:
        print(f"collecting {category}", flush=True)
        for record in collect_category(category):
            if record["source_id"] in by_id:
                existing = by_id[record["source_id"]]
                existing["source_category"] = "; ".join(
                    sorted(set(existing["source_category"].split("; ") + [category]))
                )
            else:
                by_id[record["source_id"]] = record
        time.sleep(0.05)

    candidates = sorted(by_id.values(), key=lambda item: int(item["source_id"]))
    if args.limit:
        candidates = candidates[: args.limit]

    downloaded: list[dict] = []
    for index, record in enumerate(candidates, start=1):
        try:
            downloaded.append(download(record, image_dir))
            print(f"downloaded {index}/{len(candidates)} {record['title']}", flush=True)
        except Exception as error:
            print(f"failed {record['source_page']}: {error}", flush=True)
        if index % 10 == 0:
            write_manifests(downloaded, output_dir)
        time.sleep(0.8)
    write_manifests(downloaded, output_dir)
    print(f"saved {len(downloaded)} licensed candidates to {output_dir}")


if __name__ == "__main__":
    main()
