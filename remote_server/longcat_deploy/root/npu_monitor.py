#!/usr/bin/env python3
"""Sample physical Ascend NPU utilization/HBM counters to CSV."""

from __future__ import annotations

import argparse
import csv
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


FIELDS = {
    "HBM Capacity(MB)": "hbm_capacity_mb",
    "HBM Usage Rate(%)": "hbm_usage_percent",
    "Aicore Usage Rate(%)": "aicore_usage_percent",
    "Aivector Usage Rate(%)": "aivector_usage_percent",
    "HBM Bandwidth Usage Rate(%)": "hbm_bandwidth_usage_percent",
    "NPU Utilization(%)": "npu_utilization_percent",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stop-file", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--device-ids", default="4,7")
    return parser.parse_args()


def sample(device_id: int) -> dict[str, object]:
    result = subprocess.run(
        ["npu-smi", "info", "-t", "usages", "-i", str(device_id)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )
    row: dict[str, object] = {"physical_device_id": device_id}
    for raw in result.stdout.splitlines():
        if ":" not in raw:
            continue
        name, value = (part.strip() for part in raw.split(":", 1))
        if name in FIELDS:
            row[FIELDS[name]] = int(value)
    return row


def main() -> None:
    args = parse_args()
    device_ids = [int(value) for value in args.device_ids.split(",")]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["timestamp_utc", "monotonic_seconds", "physical_device_id", *FIELDS.values()]
    started = time.monotonic()
    with args.output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        while not args.stop_file.exists():
            timestamp = datetime.now(timezone.utc).isoformat()
            for device_id in device_ids:
                row = sample(device_id)
                row["timestamp_utc"] = timestamp
                row["monotonic_seconds"] = f"{time.monotonic() - started:.3f}"
                writer.writerow(row)
            handle.flush()
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
