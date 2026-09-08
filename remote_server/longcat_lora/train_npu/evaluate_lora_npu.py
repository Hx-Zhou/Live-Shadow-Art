#!/usr/bin/env python3
"""Generate reproducible LongCat-Image base/LoRA evaluation images on one NPU."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from diffusers import LongCatImagePipeline, LongCatImageTransformer2DModel

try:
    import torch_npu  # noqa: F401
except ImportError as exc:  # pragma: no cover - server-only entry point
    raise RuntimeError("torch_npu is required for NPU evaluation") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompts", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--adapter")
    parser.add_argument("--adapter-scale", type=float, default=1.0)
    parser.add_argument("--device", default="npu:0")
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--guidance-scale", type=float, default=4.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-edge", type=int)
    parser.add_argument("--case-ids", help="comma-separated case IDs; default is every case")
    return parser.parse_args()


def scaled_size(width: int, height: int, max_edge: int | None) -> tuple[int, int]:
    if not max_edge or max(width, height) <= max_edge:
        return width, height
    factor = max_edge / max(width, height)
    return max(32, round(width * factor / 16) * 16), max(32, round(height * factor / 16) * 16)


def scale_loaded_adapter(model, factor: float) -> None:
    if factor == 1.0:
        return
    from peft.tuners.lora import LoraLayer

    for module in model.modules():
        if isinstance(module, LoraLayer):
            for adapter_name in module.active_adapters:
                module.scaling[adapter_name] *= factor


def main() -> None:
    args = parse_args()
    if not 0.0 <= args.adapter_scale <= 2.0:
        raise ValueError("adapter scale must be between 0 and 2")

    model_path = Path(args.model).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    prompt_spec = json.loads(Path(args.prompts).read_text(encoding="utf-8"))
    requested = set(args.case_ids.split(",")) if args.case_ids else None
    cases = [case for case in prompt_spec["cases"] if requested is None or case["id"] in requested]
    if not cases:
        raise ValueError("no validation cases selected")

    device = torch.device(args.device)
    torch.npu.set_device(device)
    torch.npu.reset_peak_memory_stats(device)
    transformer = LongCatImageTransformer2DModel.from_pretrained(
        str(model_path), subfolder="transformer", torch_dtype=torch.bfloat16, use_safetensors=True
    )
    adapter_label = "base"
    if args.adapter:
        from peft import PeftModel

        adapter_path = Path(args.adapter).resolve()
        transformer = PeftModel.from_pretrained(transformer, str(adapter_path), is_trainable=False)
        scale_loaded_adapter(transformer, args.adapter_scale)
        transformer = transformer.merge_and_unload(safe_merge=True)
        adapter_label = f"lora_s{args.adapter_scale:g}"

    pipeline = LongCatImagePipeline.from_pretrained(
        str(model_path), transformer=transformer, torch_dtype=torch.bfloat16
    ).to(device, dtype=torch.bfloat16)
    pipeline.set_progress_bar_config(desc=adapter_label, leave=False)
    metadata_path = output_dir / "generation_metadata.jsonl"
    completed = {path.stem for path in output_dir.glob("*.png")}

    for case in cases:
        width, height = scaled_size(int(case["width"]), int(case["height"]), args.max_edge)
        stem = f"{case['id']}__seed{args.seed}__{adapter_label}"
        if stem in completed:
            print(f"SKIP {stem}", flush=True)
            continue
        torch.npu.synchronize(device)
        started = time.time()
        image = pipeline(
            prompt=case["prompt"],
            negative_prompt=prompt_spec["shared_negative_prompt"],
            height=height,
            width=width,
            guidance_scale=args.guidance_scale,
            num_inference_steps=args.steps,
            num_images_per_prompt=1,
            generator=torch.Generator("cpu").manual_seed(args.seed),
            enable_cfg_renorm=True,
            enable_prompt_rewrite=False,
        ).images[0]
        torch.npu.synchronize(device)
        elapsed = time.time() - started
        image_path = output_dir / f"{stem}.png"
        image.save(image_path)
        record = {
            "case_id": case["id"],
            "category": case["category"],
            "prompt": case["prompt"],
            "negative_prompt": prompt_spec["shared_negative_prompt"],
            "seed": args.seed,
            "width": width,
            "height": height,
            "steps": args.steps,
            "guidance_scale": args.guidance_scale,
            "adapter": str(Path(args.adapter).resolve()) if args.adapter else None,
            "adapter_scale": args.adapter_scale if args.adapter else 0.0,
            "seconds": elapsed,
            "npu_peak_gib": torch.npu.max_memory_allocated(device) / 1024**3,
            "image": str(image_path),
        }
        with metadata_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"DONE {stem} {width}x{height} {elapsed:.1f}s", flush=True)


if __name__ == "__main__":
    main()
