#!/usr/bin/env python3
"""Tiny local runner used only to validate benchmark orchestration without a model."""

from __future__ import annotations

import argparse
from pathlib import Path


PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415408d763f8ffff3f0005fe02fea73581580000000049454e44ae426082"
)


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--output", required=True, type=Path)
    args, _ = parser.parse_known_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(PNG_1X1)


if __name__ == "__main__":
    main()

