#!/usr/bin/env python3
"""Render the processed MVP dataset with role, split, grade, and license labels."""

from __future__ import annotations

import argparse
import json
import math
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def font(size: int) -> ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def render_page(records: list[dict], destination: Path, page: int, total_pages: int) -> None:
    columns, rows = 6, 6
    card_width, image_height, label_height = 240, 210, 94
    margin, title_height = 24, 58
    canvas = Image.new(
        "RGB",
        (margin * 2 + columns * card_width, margin * 2 + title_height + rows * (image_height + label_height)),
        "#F5F1E8",
    )
    draw = ImageDraw.Draw(canvas)
    draw.text(
        (margin, margin),
        f"LongCat 皮影 LoRA MVP 数据集  第 {page}/{total_pages} 页",
        fill="#3B2A1E",
        font=font(24),
    )
    id_font, label_font = font(17), font(12)
    split_colors = {"train": "#8C2F21", "validation": "#1D4E89", "test": "#6B3A7A"}

    for position, record in enumerate(records):
        row, column = divmod(position, columns)
        x = margin + column * card_width
        y = margin + title_height + row * (image_height + label_height)
        image_path = destination.parent.parent / record["relative_path"]
        image = Image.open(image_path).convert("RGB")
        image.thumbnail((card_width - 24, image_height - 20), Image.Resampling.LANCZOS)
        card = Image.new("RGB", (card_width - 12, image_height - 8), "white")
        card.paste(image, ((card.width - image.width) // 2, (card.height - image.height) // 2))
        canvas.paste(card, (x, y))
        color = split_colors[record["split"]]
        draw.rectangle((x, y, x + card.width, y + card.height), outline=color, width=2)
        draw.text((x + 3, y + image_height), record["dataset_id"], fill=color, font=id_font)
        title_lines = textwrap.wrap(record["title"], width=29)[:2]
        label = "\n".join(
            [
                f"{record['dataset_role']} | {record['split']} | {record['quality_grade']}",
                *title_lines,
                record["license"],
            ]
        )
        draw.multiline_text((x + 68, y + image_height), label, fill="#292929", font=label_font, spacing=1)
    canvas.save(destination, quality=93)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    records = [json.loads(line) for line in args.manifest.read_text(encoding="utf-8").splitlines() if line]
    args.output.mkdir(parents=True, exist_ok=True)
    page_size = 36
    total_pages = math.ceil(len(records) / page_size)
    for page_index in range(total_pages):
        render_page(
            records[page_index * page_size : (page_index + 1) * page_size],
            args.output / f"dataset_contact_sheet_{page_index + 1:02d}.jpg",
            page_index + 1,
            total_pages,
        )
    print(f"rendered {len(records)} records in {total_pages} sheets")


if __name__ == "__main__":
    main()

