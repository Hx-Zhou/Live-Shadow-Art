#!/usr/bin/env python3
"""Summarize formal-suite integrity, stability, latency, and NPU telemetry."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

from PIL import Image


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def latency_stats(rows: list[dict[str, str]]) -> dict[str, float | int]:
    values = [float(row["latency_seconds"]) for row in rows]
    return {
        "count": len(values),
        "mean_seconds": round(statistics.fmean(values), 3),
        "median_seconds": round(statistics.median(values), 3),
        "p95_seconds": round(percentile(values, 0.95), 3),
        "min_seconds": round(min(values), 3),
        "max_seconds": round(max(values), 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite-dir", type=Path, required=True)
    args = parser.parse_args()

    with (args.suite_dir / "results.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError("results.csv is empty")

    longest = current = 0
    file_checks = []
    for row in rows:
        success = row["status"] == "success"
        current = current + 1 if success else 0
        longest = max(longest, current)
        path = Path(row["output_path"])
        with Image.open(path) as image:
            actual_size = image.size
            image.verify()
        expected_size = (int(row["width"]), int(row["height"]))
        file_checks.append(
            {
                "sequence": int(row["sequence"]),
                "path": str(path),
                "expected_size": list(expected_size),
                "actual_size": list(actual_size),
                "bytes_match": path.stat().st_size == int(row["bytes"]),
                "size_match": actual_size == expected_size,
            }
        )

    stability = {
        "status": "PASS" if longest >= 20 else "FAIL",
        "required_consecutive_successes": 20,
        "observed_consecutive_successes": longest,
        "total_attempts": len(rows),
        "total_successes": sum(row["status"] == "success" for row in rows),
        "first_20_all_success": len(rows) >= 20 and all(row["status"] == "success" for row in rows[:20]),
        "unique_image_hashes": len({row["sha256"] for row in rows}),
    }

    telemetry_rows = []
    for monitor in sorted(args.suite_dir.glob("npu_monitor_*.csv")):
        with monitor.open(encoding="utf-8-sig", newline="") as handle:
            telemetry_rows.extend(csv.DictReader(handle))
    telemetry = {}
    metrics = (
        "hbm_usage_percent",
        "aicore_usage_percent",
        "aivector_usage_percent",
        "hbm_bandwidth_usage_percent",
        "npu_utilization_percent",
    )
    for device in ("4", "7"):
        device_rows = [row for row in telemetry_rows if row["physical_device_id"] == device]
        telemetry[device] = {
            "samples": len(device_rows),
            **{
                f"max_{metric}": max((int(row[metric] or 0) for row in device_rows), default=0)
                for metric in metrics
            },
            **{
                f"mean_{metric}": round(
                    statistics.fmean(int(row[metric] or 0) for row in device_rows), 3
                ) if device_rows else 0.0
                for metric in metrics
            },
        }

    performance = {
        "status": "PASS",
        "all": latency_stats(rows),
        "character_1024x1024": latency_stats([row for row in rows if row["category"] == "character"]),
        "scene_1024x576": latency_stats([row for row in rows if row["category"] == "scene"]),
        "sum_generation_seconds": round(sum(float(row["latency_seconds"]) for row in rows), 3),
        "steady_state_images_per_minute": round(
            60 * len(rows) / sum(float(row["latency_seconds"]) for row in rows), 3
        ),
        "telemetry_by_physical_device": telemetry,
    }

    integrity = {
        "status": "PASS" if all(x["bytes_match"] and x["size_match"] for x in file_checks) else "FAIL",
        "checked_files": len(file_checks),
        "checks": file_checks,
    }
    for name, payload in (
        ("stability_validation.json", stability),
        ("performance_validation.json", performance),
        ("image_integrity_validation.json", integrity),
    ):
        (args.suite_dir / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(name, json.dumps(payload, ensure_ascii=False)[:2000])
    if stability["status"] != "PASS" or integrity["status"] != "PASS":
        raise RuntimeError("validation failed")


if __name__ == "__main__":
    main()
