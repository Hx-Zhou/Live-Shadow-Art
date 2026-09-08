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


class OmniRuntime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.omni = None
        self.torch = None
        self.sampling_class = None
        self.output_class = None
        self.platform = None

    def load(self) -> dict[str, Any]:
        import torch
        import torch_npu  # noqa: F401
        from vllm_omni.diffusion.data import DiffusionParallelConfig
        from vllm_omni.entrypoints.omni import Omni
        from vllm_omni.inputs.data import OmniDiffusionSamplingParams
        from vllm_omni.outputs import OmniRequestOutput
        from vllm_omni.platforms import current_omni_platform

        parallel = DiffusionParallelConfig(
            tensor_parallel_size=self.settings.tensor_parallel_size,
            cfg_parallel_size=self.settings.cfg_parallel_size,
            ulysses_degree=self.settings.ulysses_degree,
            ring_degree=self.settings.ring_degree,
        )
        started = time.perf_counter()
        self.omni = Omni(
            model=str(self.settings.model_dir),
            dtype="bfloat16",
            quantization=None,
            enable_cpu_offload=False,
            enable_layerwise_offload=False,
            cache_backend=None,
            parallel_config=parallel,
            vae_use_slicing=self.settings.vae_use_slicing,
            vae_use_tiling=self.settings.vae_use_tiling,
            enforce_eager=False,
        )
        self.torch = torch
        self.sampling_class = OmniDiffusionSamplingParams
        self.output_class = OmniRequestOutput
        self.platform = current_omni_platform
        return {
            "engine": "omni",
            "loadSeconds": time.perf_counter() - started,
            "dtype": "bfloat16",
            "tensorParallelSize": self.settings.tensor_parallel_size,
            "cfgParallelSize": self.settings.cfg_parallel_size,
            "ulyssesDegree": self.settings.ulysses_degree,
            "ringDegree": self.settings.ring_degree,
            "vaeSlicing": self.settings.vae_use_slicing,
            "vaeTiling": self.settings.vae_use_tiling,
        }

    def generate(self, task_id: str, request: dict[str, Any]) -> dict[str, Any]:
        if self.omni is None:
            raise RuntimeError("Omni runtime is not loaded")
        seed = int(request["seed"])
        prompt, negative = resolve_prompts(
            request["prompt"],
            request["kind"],
            request.get("negativePrompt"),
            request["applyStyleTemplate"],
        )
        generator = self.torch.Generator(device=self.platform.device_type).manual_seed(seed)
        sampling = self.sampling_class(
            height=request["height"],
            width=request["width"],
            generator=generator,
            guidance_scale=request["guidanceScale"],
            num_inference_steps=request["steps"],
            num_outputs_per_prompt=1,
        )
        started = time.perf_counter()
        outputs = self.omni.generate(
            {"prompt": prompt, "negative_prompt": negative}, sampling, use_tqdm=False
        )
        elapsed = time.perf_counter() - started
        if not outputs or not getattr(outputs[0], "request_output", None):
            raise RuntimeError("model returned no output")
        item = outputs[0].request_output[0]
        if not isinstance(item, self.output_class) or not item.images:
            raise RuntimeError("model returned no image")
        return self._save(task_id, request, prompt, negative, seed, elapsed, item.images[0])

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
            "engine": self.settings.engine,
            "model": str(self.settings.model_dir),
            "adapter": None,
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
        if self.omni is not None:
            self.omni.close()
            self.omni = None


class DiffusersLoraRuntime(OmniRuntime):
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.pipeline = None
        self.device = None

    def load(self) -> dict[str, Any]:
        import torch
        import torch_npu  # noqa: F401
        from diffusers import LongCatImagePipeline, LongCatImageTransformer2DModel
        from peft import PeftModel

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
        self.pipeline.set_progress_bar_config(disable=True)
        self.torch = torch
        return {
            "engine": "diffusers-lora",
            "loadSeconds": time.perf_counter() - started,
            "dtype": "bfloat16",
            "device": str(self.device),
            "adapter": str(self.settings.adapter_dir),
            "adapterScale": self.settings.adapter_scale,
            "validationStatus": "requires final adapter smoke test before production use",
        }

    def generate(self, task_id: str, request: dict[str, Any]) -> dict[str, Any]:
        if self.pipeline is None:
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
        result = self._save(task_id, request, prompt, negative, seed, elapsed, image)
        result["adapter"] = str(self.settings.adapter_dir)
        result["adapterScale"] = self.settings.adapter_scale
        metadata_path = self.settings.output_dir / task_id / "metadata.json"
        metadata_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return result

    def close(self) -> None:
        self.pipeline = None


def create_runtime(settings: Settings):
    if settings.engine == "diffusers-lora":
        return DiffusersLoraRuntime(settings)
    return OmniRuntime(settings)
