#!/usr/bin/env python3
"""Create the reviewed 96-image MVP dataset from the licensed candidate pool."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps


CHARACTER_IDS = {
    1, 2, 3, 4, 24, 29, 42, 56, 59, 61, 67, 69, 70, 71, 72, 77, 78,
    80, 81, 82, 84, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 101, 127,
    128, 129, 130, 131, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142,
    143, 144, 145, 147, 148, 149, 150, 151, 152,
}
SCENE_IDS = {
    32, 58, 74, 75, 76, 79, 85, 86, 87, 88, 105, 106, 107, 108, 109,
    110, 111, 112, 113, 114, 115, 117, 118, 119, 120, 208, 209, 280,
}
DETAIL_IDS = {30, 57, 60, 68, 104, 116, 121, 122, 123, 124, 277, 278}

VALIDATION_IDS = {3, 56, 68, 80, 109, 119, 120, 130}
TEST_IDS = {93, 94, 95, 96, 97, 98, 110, 277}

SOURCE_GROUPS = {
    **{item: "haining_characters_2014" for item in range(93, 99)},
    106: "mulian_shaanxi",
    107: "mulian_shaanxi",
    111: "mulian_shaanxi",
    115: "mulian_shaanxi",
    117: "mulian_shaanxi",
    112: "rising_gods_henan",
    116: "rising_gods_henan",
    119: "white_serpent_hebei",
    120: "white_serpent_hebei",
}

CHARACTER_B_GRADE = {93, 94, 95, 96, 97, 98}
SCENE_B_GRADE = set(SCENE_IDS)
DETAIL_B_GRADE = {57, 60, 116, 123}


def read_records(path: Path) -> dict[int, dict]:
    records: dict[int, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        records[int(record["display_id"][1:])] = record
    return records


def normalized_title(title: str) -> str:
    title = re.sub(r"\.(jpe?g|png)$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def caption(role: str, title: str) -> str:
    title = normalized_title(title)
    if role == "character":
        return (
            f"piying_china_style, traditional Chinese shadow-puppet character, {title}. "
            "A complete articulated flat puppet shown in side profile or near-side profile, carved translucent "
            "dyed leather, fine punched perforations, dark engraved contour lines, visible head arm hand thigh "
            "and shin joint separations, traditional costume, clean neutral museum-documentation presentation. "
            f"中国传统皮影人物，{title}，完整造型，侧身或近侧身，半透明染色皮革，细密镂空刻线，关节结构清楚，传统服饰。"
        )
    if role == "scene":
        return (
            f"piying_china_style, traditional Chinese shadow-puppet tableau and scenery, {title}. "
            "Layered flat carved-leather figures and scenery elements, translucent mineral colors, fine punched "
            "perforations, dark engraved outlines, balanced horizontal storytelling composition, warm backlit "
            "parchment character. "
            f"中国传统皮影场面，{title}，平面分层构图，半透明染色皮革，镂空与深色刻线，传统叙事场景。"
        )
    return (
        f"piying_china_style, close craftsmanship study of a traditional Chinese shadow puppet, {title}. "
        "Translucent dyed hide, hand-carved perforations, engraved dark contour lines, articulated construction "
        "and saturated mineral colors under warm backlight. "
        f"中国传统皮影工艺细节，{title}，半透明皮革，手工镂空，深色刻线和关节结构。"
    )


def split_for(display_id: int) -> str:
    if display_id in VALIDATION_IDS:
        return "validation"
    if display_id in TEST_IDS:
        return "test"
    return "train"


def role_for(display_id: int) -> str:
    if display_id in CHARACTER_IDS:
        return "character"
    if display_id in SCENE_IDS:
        return "scene"
    return "detail"


def grade_for(display_id: int, role: str) -> str:
    if role == "character" and display_id in CHARACTER_B_GRADE:
        return "B"
    if role == "scene" and display_id in SCENE_B_GRADE:
        return "B"
    if role == "detail" and display_id in DETAIL_B_GRADE:
        return "B"
    return "A"


def fit_image(source: Path, role: str, destination: Path) -> tuple[int, int, int, int]:
    target = (1024, 576) if role == "scene" else (1024, 1024)
    margin = 18 if role == "scene" else 44
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        original = image.size
        contained = ImageOps.contain(
            image,
            (target[0] - 2 * margin, target[1] - 2 * margin),
            method=Image.Resampling.LANCZOS,
        )
        canvas = Image.new("RGB", target, "#F3EEDF")
        canvas.paste(contained, ((target[0] - contained.width) // 2, (target[1] - contained.height) // 2))
        canvas.save(destination, quality=95, optimize=True)
    return original[0], original[1], target[0], target[1]


def dhash(path: Path) -> int:
    with Image.open(path) as image:
        gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        pixels = list(gray.getdata())
    value = 0
    for row in range(8):
        for column in range(8):
            value = (value << 1) | (pixels[row * 9 + column] > pixels[row * 9 + column + 1])
    return value


def write_csv(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-index", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    selected_ids = CHARACTER_IDS | SCENE_IDS | DETAIL_IDS
    assert len(CHARACTER_IDS) == 56
    assert len(SCENE_IDS) == 28
    assert len(DETAIL_IDS) == 12
    assert len(selected_ids) == 96
    assert not (VALIDATION_IDS & TEST_IDS)
    assert VALIDATION_IDS | TEST_IDS <= selected_ids

    candidates = read_records(args.candidate_index)
    missing = sorted(selected_ids - set(candidates))
    if missing:
        raise ValueError(f"missing candidate IDs: {missing}")

    output_dir = args.output.resolve()
    image_dir = output_dir / "images"
    # Rebuild generated outputs atomically enough for repeatable review: stale files
    # from an earlier selection must never be mistaken for manifest members.
    if image_dir.exists():
        shutil.rmtree(image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []

    for dataset_index, display_id in enumerate(sorted(selected_ids), start=1):
        source = candidates[display_id]
        role = role_for(display_id)
        split = split_for(display_id)
        suffix = "jpg"
        dataset_id = f"PYS{dataset_index:03d}"
        filename = f"{dataset_id}_{role}_{split}.{suffix}"
        destination = image_dir / filename
        original_width, original_height, width, height = fit_image(Path(source["image_path"]), role, destination)
        payload = destination.read_bytes()
        source_page = source.get("source_page", "")
        if not source_page and source.get("source") == "Wikimedia Commons":
            source_page = f"https://commons.wikimedia.org/?curid={source['source_id']}"
        license_url = source.get("license_url", "")
        if not license_url and source.get("license", "").strip().lower() == "public domain":
            license_url = "https://creativecommons.org/publicdomain/mark/1.0/"
        records.append(
            {
                "dataset_id": dataset_id,
                "candidate_id": f"C{display_id:03d}",
                "split": split,
                "dataset_role": role,
                "quality_grade": grade_for(display_id, role),
                "source_group": SOURCE_GROUPS.get(display_id, f"{source['source']}_{source['source_id']}"),
                "title": normalized_title(source["title"]),
                "filename": filename,
                "relative_path": f"images/{filename}",
                "server_path": f"/home/ma-user/work/longcat_lora/data/mvp_v1/images/{filename}",
                "width": width,
                "height": height,
                "original_width": original_width,
                "original_height": original_height,
                "source": source["source"],
                "source_id": source["source_id"],
                "source_page": source_page,
                "original_url": source["original_url"],
                "artist": source.get("artist") or "Unknown / not stated by source",
                "credit": source.get("credit") or "See source page",
                "license": source["license"],
                "license_url": license_url,
                "attribution_required": source.get("attribution_required", ""),
                "noncommercial_only": bool(source.get("noncommercial_only", False)),
                "project_usage": "noncommercial_course_demonstration_only",
                "source_sha256": source["sha256"],
                "downloaded_at": source.get("downloaded_at", "2026-09-08"),
                "processed_sha256": hashlib.sha256(payload).hexdigest(),
                "processing": "EXIF transpose; RGB; aspect-preserving contain; ivory canvas; no generative edit",
                "caption": caption(role, source["title"]),
                "review_status": "selected_for_mvp_v1",
                "review_notes": "A=clean isolated reference; B=authentic but group/display/tableau reference",
            }
        )

    write_csv(output_dir / "dataset_manifest.csv", records)
    (output_dir / "dataset_manifest.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records), encoding="utf-8"
    )
    (output_dir / "train_prompts.jsonl").write_text(
        "".join(
            json.dumps(
                {"dataset_id": item["dataset_id"], "img_path": item["server_path"], "prompt": item["caption"], "width": item["width"], "height": item["height"]},
                ensure_ascii=False,
            )
            + "\n"
            for item in records
            if item["split"] == "train"
        ),
        encoding="utf-8",
    )
    for split in ("train", "validation", "test"):
        (output_dir / f"{split}_data_info.jsonl").write_text(
            "".join(
                json.dumps(
                    {"img_path": item["server_path"], "prompt": item["caption"], "width": item["width"], "height": item["height"]},
                    ensure_ascii=False,
                )
                + "\n"
                for item in records
                if item["split"] == split
            ),
            encoding="utf-8",
        )

    hashes = [(item["dataset_id"], dhash(image_dir / item["filename"])) for item in records]
    near_duplicates: list[tuple[str, str, int]] = []
    for left_index, (left_id, left_hash) in enumerate(hashes):
        for right_id, right_hash in hashes[left_index + 1 :]:
            distance = (left_hash ^ right_hash).bit_count()
            if distance <= 4:
                near_duplicates.append((left_id, right_id, distance))

    role_counts = Counter(item["dataset_role"] for item in records)
    split_counts = Counter(item["split"] for item in records)
    grade_counts = Counter(item["quality_grade"] for item in records)
    license_counts = Counter(item["license"] for item in records)
    low_resolution = [
        item["dataset_id"] for item in records if min(item["original_width"], item["original_height"]) < 512
    ]
    summary = {
        "total": len(records),
        "role_counts": role_counts,
        "split_counts": split_counts,
        "grade_counts": grade_counts,
        "license_counts": license_counts,
        "noncommercial_only_count": sum(bool(item["noncommercial_only"]) for item in records),
        "low_resolution": low_resolution,
        "near_duplicate_candidates": near_duplicates,
    }
    (output_dir / "dataset_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=dict) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=dict))


if __name__ == "__main__":
    main()
