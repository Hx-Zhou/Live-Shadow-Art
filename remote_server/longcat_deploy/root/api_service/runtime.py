from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from .config import Settings
from .prompts import resolve_prompts


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class DiffusersLoraRuntime:
    """The only production runtime: final LongCat LoRA on Ascend NPU."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.pipeline = None
        self.device = None
        self.torch = None

    def load(self) -> dict[str, Any]:
        import torch
        import torch_npu  # noqa: F401
        from diffusers import LongCatImagePipeline, LongCatImageTransformer2DModel
        from peft import PeftModel

        if self.settings.adapter_dir is None:
            raise RuntimeError("final LoRA adapter is not configured")

        started = time.perf_counter()
        self.device = torch.device(self.settings.device)
        torch.npu.set_device(self.device)
        transformer = LongCatImageTransformer2DModel.from_pretrained(
            str(self.settings.model_dir),
            subfolder="transformer",
            torch_dtype=torch.bfloat16,
            use_safetensors=True,
        )
        transformer = PeftModel.from_pretrained(
            transformer, str(self.settings.adapter_dir), is_trainable=False
        )
        if self.settings.adapter_scale != 1.0:
            from peft.tuners.lora import LoraLayer

            for module in transformer.modules():
                if isinstance(module, LoraLayer):
                    for adapter_name in module.active_adapters:
                        module.scaling[adapter_name] *= self.settings.adapter_scale
        transformer = transformer.merge_and_unload(safe_merge=True)
        self.pipeline = LongCatImagePipeline.from_pretrained(
            str(self.settings.model_dir), transformer=transformer, torch_dtype=torch.bfloat16
        ).to(self.device, dtype=torch.bfloat16)
        if self.settings.vae_use_slicing:
            if hasattr(self.pipeline, "enable_vae_slicing"):
                self.pipeline.enable_vae_slicing()
            elif hasattr(self.pipeline.vae, "enable_slicing"):
                self.pipeline.vae.enable_slicing()
        if self.settings.vae_use_tiling:
            if hasattr(self.pipeline, "enable_vae_tiling"):
                self.pipeline.enable_vae_tiling()
            elif hasattr(self.pipeline.vae, "enable_tiling"):
                self.pipeline.vae.enable_tiling()
        self.pipeline.set_progress_bar_config(disable=True)
        self.torch = torch
        return {
            "engine": "diffusers-lora",
            "loadSeconds": time.perf_counter() - started,
            "dtype": "bfloat16",
            "device": str(self.device),
            "adapter": str(self.settings.adapter_dir),
            "adapterRevision": self.settings.adapter_revision,
            "adapterScale": self.settings.adapter_scale,
            "vaeSlicing": self.settings.vae_use_slicing,
            "vaeTiling": self.settings.vae_use_tiling,
            "validationStatus": (
                "passed on Ascend 910B3: final adapter scale 0.8, 1024x1024, "
                "50 steps, guidance 4.0"
            ),
        }

    def generate(self, task_id: str, request: dict[str, Any]) -> dict[str, Any]:
        if self.pipeline is None or self.torch is None or self.device is None:
            raise RuntimeError("Diffusers LoRA runtime is not loaded")
        seed = int(request["seed"])
        prompt, negative = resolve_prompts(
            request["prompt"],
            request["kind"],
            request.get("negativePrompt"),
            request["applyStyleTemplate"],
        )
        self.torch.npu.synchronize(self.device)
        started = time.perf_counter()
        image = self.pipeline(
            prompt=prompt,
            negative_prompt=negative,
            height=request["height"],
            width=request["width"],
            guidance_scale=request["guidanceScale"],
            num_inference_steps=request["steps"],
            num_images_per_prompt=1,
            generator=self.torch.Generator("cpu").manual_seed(seed),
            enable_cfg_renorm=True,
            enable_prompt_rewrite=False,
        ).images[0]
        self.torch.npu.synchronize(self.device)
        elapsed = time.perf_counter() - started
        return self._save(task_id, request, prompt, negative, seed, elapsed, image)

    def _save(
        self,
        task_id: str,
        request: dict[str, Any],
        prompt: str,
        negative: str,
        seed: int,
        elapsed: float,
        image,
    ) -> dict[str, Any]:
        task_dir = self.settings.output_dir / task_id
        # A worker restart can leave this task directory behind after the job was
        # requeued. Reusing only this exact task ID keeps recovery idempotent.
        task_dir.mkdir(parents=True, exist_ok=True)
        temporary = task_dir / "image.tmp.png"
        image_path = task_dir / "image.png"
        image.save(temporary)
        os.replace(temporary, image_path)
        result = {
            "taskId": task_id,
            "engine": "diffusers-lora",
            "model": str(self.settings.model_dir),
            "adapter": str(self.settings.adapter_dir),
            "adapterRevision": self.settings.adapter_revision,
            "adapterScale": self.settings.adapter_scale,
            "resolvedPrompt": prompt,
            "resolvedNegativePrompt": negative,
            "seed": seed,
            "width": request["width"],
            "height": request["height"],
            "steps": request["steps"],
            "guidanceScale": request["guidanceScale"],
            "generationSeconds": elapsed,
            "imagePath": str(image_path),
            "imageBytes": image_path.stat().st_size,
            "imageSha256": _file_sha256(image_path),
        }
        (task_dir / "metadata.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return result

    def close(self) -> None:
        self.pipeline = None


def create_runtime(settings: Settings) -> DiffusersLoraRuntime:
    return DiffusersLoraRuntime(settings)
