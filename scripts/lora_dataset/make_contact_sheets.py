#!/usr/bin/env python3
"""Build labeled contact sheets for human review of candidate images."""

from __future__ import annotations

import argparse
import json
import math
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def load_records(paths: list[Path]) -> list[dict]:
    records: list[dict] = []
    for manifest_path in paths:
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            record["manifest_path"] = str(manifest_path)
            record["image_path"] = str(manifest_path.parent / record["relative_path"])
            records.append(record)
    records.sort(key=lambda item: (item["source"], item["source_id"]))
    for index, record in enumerate(records, start=1):
        record["display_id"] = f"C{index:03d}"
    return records


def render_sheet(records: list[dict], destination: Path, columns: int, rows: int) -> None:
    card_width = 240
    image_height = 210
    label_height = 92
    margin = 24
    title_height = 56
    width = margin * 2 + columns * card_width
    height = margin * 2 + title_height + rows * (image_height + label_height)
    canvas = Image.new("RGB", (width, height), "#F5F1E8")
    draw = ImageDraw.Draw(canvas)
    title_font = font(24)
    id_font = font(18)
    label_font = font(12)
    draw.text((margin, margin), f"LongCat 皮影 LoRA 候选数据  {destination.stem}", fill="#3B2A1E", font=title_font)

    for position, record in enumerate(records):
        row, column = divmod(position, columns)
        x = margin + column * card_width
        y = margin + title_height + row * (image_height + label_height)
        card = Image.new("RGB", (card_width - 12, image_height - 8), "white")
        try:
            image = Image.open(record["image_path"]).convert("RGB")
            image.thumbnail((card_width - 24, image_height - 20), Image.Resampling.LANCZOS)
            px = (card.width - image.width) // 2
            py = (card.height - image.height) // 2
            card.paste(image, (px, py))
        except Exception as error:
            ImageDraw.Draw(card).text((8, 8), f"读取失败\n{error}", fill="#B91C1C", font=label_font)
        canvas.paste(card, (x, y))
        draw.rectangle((x, y, x + card.width, y + card.height), outline="#C7B9A3", width=1)
        draw.text((x + 4, y + image_height), record["display_id"], fill="#7A1F1F", font=id_font)
        title = " ".join(record.get("title", "").split())
        source = "Commons" if record["source"] == "Wikimedia Commons" else "The Met"
        license_name = record.get("license", "")
        lines = textwrap.wrap(title, width=30)[:2]
        label = "\n".join(lines + [f"{source} | {license_name}"])
        draw.multiline_text((x + 52, y + image_height), label, fill="#2F2F2F", font=label_font, spacing=2)
    canvas.save(destination, quality=92)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifests", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--columns", type=int, default=6)
    parser.add_argument("--rows", type=int, default=8)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    records = load_records(args.manifests)
    page_size = args.columns * args.rows
    for page_index in range(math.ceil(len(records) / page_size)):
        subset = records[page_index * page_size : (page_index + 1) * page_size]
        destination = args.output / f"candidates_{page_index + 1:02d}.jpg"
        render_sheet(subset, destination, args.columns, args.rows)
    (args.output / "candidate_index.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records), encoding="utf-8"
    )
    print(f"rendered {len(records)} records in {math.ceil(len(records) / page_size)} sheets")


if __name__ == "__main__":
    main()

