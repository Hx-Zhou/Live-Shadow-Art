#!/usr/bin/env python3
"""Load LongCat-Image once and run reproducible formal or stability suites."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
import time
from dataclasses import asdict
from pathlib import Path

import torch
import torch_npu  # noqa: F401 - register NPU backend

from vllm_omni.diffusion.data import DiffusionParallelConfig
from vllm_omni.entrypoints.omni import Omni
from vllm_omni.inputs.data import OmniDiffusionSamplingParams
from vllm_omni.outputs import OmniRequestOutput
from vllm_omni.platforms import current_omni_platform


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--negative-prompt-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seeds", default="42,3407,20260903")
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--guidance-scale", type=float, default=4.0)
    parser.add_argument("--tensor-parallel-size", type=int, default=1)
    parser.add_argument("--cfg-parallel-size", type=int, default=1)
    parser.add_argument("--ulysses-degree", type=int, default=2)
    parser.add_argument("--ring-degree", type=int, default=1)
    parser.add_argument("--stability-runs", type=int, default=0)
    parser.add_argument("--stability-seed-base", type=int, default=91000)
    parser.add_argument("--vae-use-slicing", action="store_true")
    parser.add_argument("--vae-use-tiling", action="store_true")
    parser.add_argument("--enforce-eager", action="store_true")
    return parser.parse_args()


def image_from_outputs(outputs: list[object]):
    if not outputs:
        raise RuntimeError("No output returned")
    first = outputs[0]
    if not hasattr(first, "request_output") or not first.request_output:
        raise RuntimeError("Output has no request_output")
    item = first.request_output[0]
    if not isinstance(item, OmniRequestOutput) or not item.images:
        raise RuntimeError("Output has no image")
    return item.images[0]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    if not args.model.is_dir():
        raise FileNotFoundError(args.model)
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    negative_prompt = args.negative_prompt_file.read_text(encoding="utf-8").strip()
    seeds = [int(value.strip()) for value in args.seeds.split(",") if value.strip()]
    if args.stability_runs:
        tasks = [
            (cases[index % len(cases)], args.stability_seed_base + index)
            for index in range(args.stability_runs)
        ]
    else:
        # Keep each seed's character and scene cases together so both asset
        # categories are validated early while preserving the full 10x3 set.
        tasks = [(case, seed) for seed in seeds for case in cases]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "cases.json").write_text(
        json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "negative_prompt.txt").write_text(
        negative_prompt + "\n", encoding="utf-8"
    )
    image_dir = args.output_dir / "images"
    image_dir.mkdir(exist_ok=True)
    csv_path = args.output_dir / "results.csv"
    parallel = DiffusionParallelConfig(
        tensor_parallel_size=args.tensor_parallel_size,
        cfg_parallel_size=args.cfg_parallel_size,
        ulysses_degree=args.ulysses_degree,
        ring_degree=args.ring_degree,
    )
    run_config = {
        "model": str(args.model.resolve()),
        "model_revision": (args.model / "MODEL_REVISION.txt").read_text(encoding="utf-8").strip(),
        "dtype": "bfloat16",
        "quantization": None,
        "cpu_offload": False,
        "layerwise_offload": False,
        "cache_backend": None,
        "steps": args.steps,
        "guidance_scale": args.guidance_scale,
        "parallel": asdict(parallel),
        "vae_use_slicing": args.vae_use_slicing,
        "vae_use_tiling": args.vae_use_tiling,
        "enforce_eager": args.enforce_eager,
        "task_count": len(tasks),
        "python": sys.version,
        "platform": platform.platform(),
        "torch": torch.__version__,
        "torch_npu": torch_npu.__version__,
        "visible_npus": torch.npu.device_count(),
        "started_epoch": time.time(),
    }
    (args.output_dir / "run_config.json").write_text(
        json.dumps(run_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("RUN_CONFIG=" + json.dumps(run_config, ensure_ascii=False), flush=True)

    init_started = time.perf_counter()
    omni = Omni(
        model=str(args.model),
        dtype="bfloat16",
        quantization=None,
        enable_cpu_offload=False,
        enable_layerwise_offload=False,
        cache_backend=None,
        parallel_config=parallel,
        vae_use_slicing=args.vae_use_slicing,
        vae_use_tiling=args.vae_use_tiling,
        enforce_eager=args.enforce_eager,
    )
    init_seconds = time.perf_counter() - init_started
    print(f"MODEL_INITIALIZED seconds={init_seconds:.3f}", flush=True)

    fields = [
        "sequence", "case_id", "category", "seed", "width", "height",
        "steps", "guidance_scale", "latency_seconds", "status",
        "bytes", "sha256", "output_path",
    ]
    completed = 0
    suite_started = time.perf_counter()
    try:
        with csv_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fields)
            writer.writeheader()
            for sequence, (case, seed) in enumerate(tasks, start=1):
                stem = f"{sequence:03d}__{case['id']}__seed_{seed}"
                output_path = image_dir / f"{stem}.png"
                generator = torch.Generator(device=current_omni_platform.device_type).manual_seed(seed)
                sampling = OmniDiffusionSamplingParams(
                    height=int(case["height"]),
                    width=int(case["width"]),
                    generator=generator,
                    guidance_scale=args.guidance_scale,
                    num_inference_steps=args.steps,
                    num_outputs_per_prompt=1,
                )
                print(
                    f"RUN sequence={sequence}/{len(tasks)} case={case['id']} seed={seed} "
                    f"size={case['width']}x{case['height']}",
                    flush=True,
                )
                started = time.perf_counter()
                outputs = omni.generate(
                    {
                        "prompt": case["prompt"],
                        "negative_prompt": case.get("negative_prompt", negative_prompt),
                    },
                    sampling,
                    use_tqdm=False,
                )
                elapsed = time.perf_counter() - started
                image = image_from_outputs(outputs)
                image.save(output_path)
                digest = file_sha256(output_path)
                writer.writerow(
                    {
                        "sequence": sequence,
                        "case_id": case["id"],
                        "category": case["category"],
                        "seed": seed,
                        "width": case["width"],
                        "height": case["height"],
                        "steps": args.steps,
                        "guidance_scale": args.guidance_scale,
                        "latency_seconds": f"{elapsed:.3f}",
                        "status": "success",
                        "bytes": output_path.stat().st_size,
                        "sha256": digest,
                        "output_path": str(output_path),
                    }
                )
                csv_file.flush()
                completed += 1
                print(f"PASS sequence={sequence} seconds={elapsed:.3f} sha256={digest}", flush=True)
    finally:
        omni.close()

    suite_seconds = time.perf_counter() - suite_started
    summary = {
        "status": "PASS" if completed == len(tasks) else "FAIL",
        "completed": completed,
        "expected": len(tasks),
        "model_init_seconds": init_seconds,
        "suite_seconds": suite_seconds,
        "average_generation_seconds": suite_seconds / completed if completed else None,
        "finished_epoch": time.time(),
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("SUMMARY=" + json.dumps(summary, ensure_ascii=False), flush=True)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
