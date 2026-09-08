#!/usr/bin/env python3
"""Run the fixed shadow-puppet benchmark through vLLM-Omni's official CLI."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--negative-prompt-file", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--seeds", default="42,3407,20260903")
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--guidance-scale", type=float, default=4.0)
    parser.add_argument("--tensor-parallel-size", type=int, default=1)
    parser.add_argument("--cfg-parallel-size", type=int, default=1)
    parser.add_argument("--ulysses-degree", type=int, default=1)
    parser.add_argument("--ring-degree", type=int, default=1)
    parser.add_argument("--vae-memory-opts", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.runner.is_file():
        raise FileNotFoundError(f"runner not found: {args.runner}")
    if args.steps <= 0:
        raise ValueError("steps must be positive")

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    negative_prompt = args.negative_prompt_file.read_text(encoding="utf-8").strip()
    seeds = [int(item.strip()) for item in args.seeds.split(",") if item.strip()]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = args.output_dir / "logs"
    image_dir = args.output_dir / "images"
    log_dir.mkdir(exist_ok=True)
    image_dir.mkdir(exist_ok=True)
    csv_path = args.output_dir / "performance.csv"

    fieldnames = [
        "case_id", "category", "seed", "width", "height", "steps",
        "guidance_scale", "tensor_parallel_size", "cfg_parallel_size",
        "ulysses_degree", "ring_degree", "status", "return_code",
        "latency_seconds", "output_path", "log_path",
    ]
    write_header = not csv_path.exists() or not args.resume
    mode = "a" if args.resume else "w"

    failures = 0
    with csv_path.open(mode, newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()

        for case in cases:
            for seed in seeds:
                stem = f"{case['id']}__seed_{seed}"
                output_path = image_dir / f"{stem}.png"
                log_path = log_dir / f"{stem}.log"
                if args.resume and output_path.is_file() and output_path.stat().st_size > 0:
                    print(f"[SKIP] {stem}: output exists")
                    continue

                command = [
                    sys.executable,
                    str(args.runner),
                    "--model", args.model,
                    "--prompt", case["prompt"],
                    "--negative-prompt", negative_prompt,
                    "--seed", str(seed),
                    "--guidance-scale", str(args.guidance_scale),
                    "--num-inference-steps", str(args.steps),
                    "--width", str(case["width"]),
                    "--height", str(case["height"]),
                    "--tensor-parallel-size", str(args.tensor_parallel_size),
                    "--cfg-parallel-size", str(args.cfg_parallel_size),
                    "--ulysses-degree", str(args.ulysses_degree),
                    "--ring-degree", str(args.ring_degree),
                    "--output", str(output_path),
                ]
                if args.vae_memory_opts:
                    command.extend(["--vae-use-slicing", "--vae-use-tiling"])

                print(f"[RUN] {stem} ({case['width']}x{case['height']})")
                started = time.perf_counter()
                with log_path.open("w", encoding="utf-8") as log_file:
                    result = subprocess.run(
                        command,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        text=True,
                        check=False,
                    )
                latency = time.perf_counter() - started
                success = result.returncode == 0 and output_path.is_file() and output_path.stat().st_size > 0
                if not success:
                    failures += 1
                writer.writerow({
                    "case_id": case["id"],
                    "category": case["category"],
                    "seed": seed,
                    "width": case["width"],
                    "height": case["height"],
                    "steps": args.steps,
                    "guidance_scale": args.guidance_scale,
                    "tensor_parallel_size": args.tensor_parallel_size,
                    "cfg_parallel_size": args.cfg_parallel_size,
                    "ulysses_degree": args.ulysses_degree,
                    "ring_degree": args.ring_degree,
                    "status": "success" if success else "failed",
                    "return_code": result.returncode,
                    "latency_seconds": f"{latency:.3f}",
                    "output_path": str(output_path),
                    "log_path": str(log_path),
                })
                csv_file.flush()
                print(f"[{'OK' if success else 'FAIL'}] {stem}: {latency:.3f}s")

    print(f"Performance CSV: {csv_path}")
    print(f"Failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

