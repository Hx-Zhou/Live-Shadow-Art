#!/usr/bin/env python3
"""Ascend NPU LoRA trainer for the official LongCat-Image architecture.

This is an adaptation of upstream commit f0e4c43c5ef74b011ff71570fbfc2bdffbc9ab06.
It keeps the Final/vLLM inference environment read-only and writes only below
the configured work_dir.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import shutil
import sys
import time
from pathlib import Path

import torch
import yaml
from accelerate import Accelerator
from accelerate.logging import get_logger
from accelerate.utils import DistributedDataParallelKwargs, ProjectConfiguration, set_seed
from diffusers import FlowMatchEulerDiscreteScheduler
from diffusers.models import AutoencoderKL
from diffusers.optimization import get_scheduler
from peft import LoraConfig, get_peft_model, set_peft_model_state_dict
from safetensors.torch import load_file
from transformers import AutoModel, AutoTokenizer

try:
    import torch_npu  # noqa: F401  # Registers the NPU backend with torch.
except ImportError as exc:  # pragma: no cover - must fail early on the server.
    raise RuntimeError("torch_npu is required for this training entry point") from exc

from train_dataset import build_dataloader
from longcat_image.models import LongCatImageTransformer2DModel
from longcat_image.utils import calculate_shift, pack_latents, prepare_pos_ids, unpack_latents


LOGGER = get_logger(__name__)
GIB = 1024**3
TARGET_MODULES = [
    "attn.to_k",
    "attn.to_q",
    "attn.to_v",
    "attn.to_out.0",
    "attn.add_k_proj",
    "attn.add_q_proj",
    "attn.add_v_proj",
    "attn.to_add_out",
    "ff.net.0.proj",
    "ff.net.2",
    "ff_context.net.0.proj",
    "ff_context.net.2",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    cli = parser.parse_args()
    with open(cli.config, "r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    config["config"] = str(Path(cli.config).resolve())
    return argparse.Namespace(**config)


def resolve_checkpoint(work_dir: Path, requested: str | None) -> Path | None:
    if not requested:
        return None
    if requested != "latest":
        candidate = Path(requested)
        if not candidate.is_absolute():
            candidate = work_dir / candidate
        return candidate if candidate.is_dir() else None
    candidates = []
    for item in work_dir.glob("checkpoint-*"):
        if not item.is_dir() or item.name.endswith(".tmp"):
            continue
        try:
            candidates.append((int(item.name.split("-")[-1]), item))
        except ValueError:
            continue
    return max(candidates, default=(0, None))[1]


def adapter_state_path(adapter_dir: Path) -> Path:
    safe = adapter_dir / "adapter_model.safetensors"
    if safe.is_file():
        return safe
    binary = adapter_dir / "adapter_model.bin"
    if binary.is_file():
        return binary
    raise FileNotFoundError(f"adapter weights not found below {adapter_dir}")


def npu_memory_gib() -> tuple[float, float]:
    allocated = torch.npu.memory_allocated() / GIB
    peak = torch.npu.max_memory_allocated() / GIB
    return allocated, peak


def write_jsonl(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main() -> None:
    args = parse_args()
    if getattr(args, "allow_tf32", False):
        raise ValueError("TF32 is CUDA-specific and is disabled on Ascend NPU")
    if getattr(args, "use_8bit_adam", False):
        raise ValueError("bitsandbytes Adam is CUDA-specific and is disabled on Ascend NPU")

    work_dir = Path(args.work_dir).resolve()
    log_dir = work_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    project_config = ProjectConfiguration(project_dir=str(work_dir), logging_dir=str(log_dir))
    ddp = DistributedDataParallelKwargs(find_unused_parameters=False)
    report_to = None if str(args.report_to).lower() in {"none", "null", ""} else args.report_to
    accelerator = Accelerator(
        mixed_precision=args.mixed_precision,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        log_with=report_to,
        project_config=project_config,
        kwargs_handlers=[ddp],
    )

    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )
    LOGGER.info(accelerator.state, main_process_only=False)
    if accelerator.device.type != "npu":
        raise RuntimeError(f"expected an NPU device, got {accelerator.device}")
    set_seed(args.seed, device_specific=True)
    torch.npu.set_device(accelerator.device)
    torch.npu.reset_peak_memory_stats(accelerator.device)

    weight_dtype = torch.bfloat16 if args.mixed_precision == "bf16" else torch.float32
    base_model = Path(args.pretrained_model_name_or_path).resolve()
    if not (base_model / "model_index.json").is_file():
        raise FileNotFoundError(f"incomplete base model: {base_model}")

    if accelerator.is_main_process:
        with (log_dir / "resolved_config.yaml").open("w", encoding="utf-8") as handle:
            yaml.safe_dump(vars(args), handle, allow_unicode=True, sort_keys=True)
        write_jsonl(
            log_dir / "events.jsonl",
            {
                "event": "start",
                "time": time.time(),
                "torch": torch.__version__,
                "torch_npu": getattr(torch_npu, "__version__", "unknown"),
                "device_count": torch.npu.device_count(),
                "base_model": str(base_model),
                "base_revision": (base_model / "MODEL_REVISION.txt").read_text(encoding="utf-8").strip()
                if (base_model / "MODEL_REVISION.txt").is_file()
                else "unknown",
            },
        )

    LOGGER.info("Loading LongCat transformer on CPU")
    transformer_path = (
        Path(args.diffusion_pretrain_weight).resolve()
        if getattr(args, "diffusion_pretrain_weight", None)
        else base_model / "transformer"
    )
    transformer = LongCatImageTransformer2DModel.from_pretrained(
        str(transformer_path), torch_dtype=weight_dtype, ignore_mismatched_sizes=False
    )
    transformer.requires_grad_(False)
    lora_config = LoraConfig(
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        init_lora_weights="gaussian",
        target_modules=TARGET_MODULES,
        use_dora=False,
        use_rslora=False,
    )
    transformer = get_peft_model(transformer, lora_config)
    transformer.print_trainable_parameters()
    trainable_params = [parameter for parameter in transformer.parameters() if parameter.requires_grad]
    trainable_count = sum(parameter.numel() for parameter in trainable_params)
    if not trainable_count:
        raise RuntimeError("LoRA injection produced zero trainable parameters")
    LOGGER.info("LoRA trainable parameters: %s", trainable_count)

    if args.gradient_checkpointing:
        transformer.enable_gradient_checkpointing()

    LOGGER.info("Loading frozen VAE and text encoder")
    vae = AutoencoderKL.from_pretrained(str(base_model), subfolder="vae", torch_dtype=weight_dtype)
    text_encoder = AutoModel.from_pretrained(
        str(base_model), subfolder="text_encoder", torch_dtype=weight_dtype, trust_remote_code=True
    )
    tokenizer = AutoTokenizer.from_pretrained(str(base_model), subfolder="tokenizer", trust_remote_code=True)
    vae.requires_grad_(False).eval().to(accelerator.device, dtype=weight_dtype)
    text_encoder.requires_grad_(False).eval().to(accelerator.device, dtype=weight_dtype)

    noise_scheduler = FlowMatchEulerDiscreteScheduler.from_pretrained(str(base_model), subfolder="scheduler")
    optimizer = torch.optim.AdamW(
        trainable_params,
        lr=args.learning_rate,
        betas=(args.adam_beta1, args.adam_beta2),
        weight_decay=args.adam_weight_decay,
        eps=args.adam_epsilon,
    )
    train_dataloader = build_dataloader(args, args.data_txt_root, tokenizer, args.resolution)
    updates_per_epoch = math.ceil(len(train_dataloader) / args.gradient_accumulation_steps)
    num_train_epochs = math.ceil(args.max_train_steps / updates_per_epoch)
    lr_scheduler = get_scheduler(
        args.lr_scheduler,
        optimizer=optimizer,
        num_warmup_steps=args.lr_warmup_steps * accelerator.num_processes,
        num_training_steps=args.max_train_steps * accelerator.num_processes,
        num_cycles=args.lr_num_cycles,
        power=args.lr_power,
    )

    def save_model_hook(models, weights, output_dir):
        if accelerator.is_main_process:
            for model in models:
                accelerator.unwrap_model(model).save_pretrained(Path(output_dir) / "transformer")
        weights.clear()

    def load_model_hook(models, input_dir):
        adapter_dir = Path(input_dir) / "transformer"
        weights_path = adapter_state_path(adapter_dir)
        if weights_path.suffix == ".safetensors":
            state_dict = load_file(str(weights_path), device="cpu")
        else:
            state_dict = torch.load(weights_path, map_location="cpu", weights_only=True)
        while models:
            model = models.pop()
            incompatible = set_peft_model_state_dict(accelerator.unwrap_model(model), state_dict)
            if getattr(incompatible, "unexpected_keys", None):
                raise RuntimeError(f"unexpected LoRA keys during resume: {incompatible.unexpected_keys}")

    accelerator.register_save_state_pre_hook(save_model_hook)
    accelerator.register_load_state_pre_hook(load_model_hook)
    transformer, optimizer, train_dataloader, lr_scheduler = accelerator.prepare(
        transformer, optimizer, train_dataloader, lr_scheduler
    )

    checkpoint = resolve_checkpoint(work_dir, getattr(args, "resume_from_checkpoint", None))
    global_step = 0
    first_epoch = 0
    if checkpoint:
        LOGGER.info("Resuming from %s", checkpoint)
        accelerator.load_state(str(checkpoint))
        global_step = int(checkpoint.name.split("-")[-1])
        first_epoch = global_step // max(1, updates_per_epoch)

    if report_to:
        accelerator.init_trackers("longcat_lora_npu", config=vars(args))

    total_batch_size = args.train_batch_size * accelerator.num_processes * args.gradient_accumulation_steps
    LOGGER.info(
        "Training examples=%s, epochs=%s, max_steps=%s, effective_batch=%s",
        len(train_dataloader.dataset),
        num_train_epochs,
        args.max_train_steps,
        total_batch_size,
    )

    metrics_path = log_dir / "metrics.jsonl"
    optimizer.zero_grad(set_to_none=True)
    last_log_time = time.time()
    transformer.train()

    for epoch in range(first_epoch, num_train_epochs):
        if hasattr(train_dataloader.sampler, "set_epoch"):
            train_dataloader.sampler.set_epoch(epoch)
        for batch in train_dataloader:
            image = batch["images"].to(accelerator.device, dtype=weight_dtype, non_blocking=True)
            with torch.no_grad(), accelerator.autocast():
                latents = vae.encode(image).latent_dist.sample()
                latents = (latents - vae.config.shift_factor) * vae.config.scaling_factor
                text_output = text_encoder(
                    input_ids=batch["input_ids"].to(accelerator.device),
                    attention_mask=batch["attention_mask"].to(accelerator.device),
                    output_hidden_states=True,
                )
                prompt_embeds = text_output.hidden_states[-1]
                prompt_embeds = prompt_embeds[
                    :, args.prompt_template_encode_start_idx : -args.prompt_template_encode_end_idx, :
                ].to(dtype=weight_dtype)

            with accelerator.accumulate(transformer):
                sigmas = torch.sigmoid(
                    torch.randn((latents.shape[0],), device=accelerator.device, dtype=weight_dtype)
                )
                if args.use_dynamic_shifting:
                    batch_mu = calculate_shift(
                        (latents.shape[2] // 2) * (latents.shape[3] // 2),
                        noise_scheduler.config.base_image_seq_len,
                        noise_scheduler.config.max_image_seq_len,
                        noise_scheduler.config.base_shift,
                        noise_scheduler.config.max_shift,
                    )
                    sigmas = noise_scheduler.time_shift(batch_mu, 1.0, sigmas)
                timesteps = sigmas * 1000.0
                sigma_view = sigmas.view(-1, 1, 1, 1)
                noise = torch.randn_like(latents)
                noisy_latents = ((1 - sigma_view) * latents + sigma_view * noise).to(weight_dtype)
                packed = pack_latents(
                    noisy_latents,
                    batch_size=latents.shape[0],
                    num_channels_latents=latents.shape[1],
                    height=latents.shape[2],
                    width=latents.shape[3],
                )
                img_ids = prepare_pos_ids(
                    modality_id=1,
                    type="image",
                    start=(prompt_embeds.shape[1], prompt_embeds.shape[1]),
                    height=latents.shape[2] // 2,
                    width=latents.shape[3] // 2,
                ).to(accelerator.device, dtype=torch.float32)
                text_ids = prepare_pos_ids(
                    modality_id=0, type="text", start=(0, 0), num_token=prompt_embeds.shape[1]
                ).to(accelerator.device, dtype=torch.float32)

                # Do not force CUDA Flash-SDPA. torch-npu dispatches the
                # supported attention path and may fall back when necessary.
                model_pred = transformer(
                    packed,
                    prompt_embeds,
                    timesteps / 1000.0,
                    img_ids,
                    text_ids,
                    None,
                    return_dict=False,
                )[0]
                model_pred = unpack_latents(
                    model_pred,
                    height=latents.shape[2] * 8,
                    width=latents.shape[3] * 8,
                    vae_scale_factor=16,
                )
                target = noise - latents
                loss = ((model_pred.float() - target.float()) ** 2).reshape(target.shape[0], -1).mean(1).mean()
                if not torch.isfinite(loss):
                    raise FloatingPointError(f"non-finite loss on rank {accelerator.process_index}: {loss.item()}")
                accelerator.backward(loss)
                grad_norm = None
                if accelerator.sync_gradients:
                    grad_norm = accelerator.clip_grad_norm_(trainable_params, args.gradient_clip)
                    if not torch.isfinite(torch.as_tensor(grad_norm)):
                        raise FloatingPointError(f"non-finite grad norm on rank {accelerator.process_index}")
                optimizer.step()
                lr_scheduler.step()
                optimizer.zero_grad(set_to_none=True)

            if not accelerator.sync_gradients:
                continue
            global_step += 1
            gathered_loss = accelerator.gather(loss.detach()).mean().item()
            gathered_grad = (
                accelerator.gather(torch.as_tensor(grad_norm, device=accelerator.device).detach()).mean().item()
                if grad_norm is not None
                else None
            )
            allocated, peak = npu_memory_gib()
            payload = {
                "step": global_step,
                "epoch": epoch,
                "loss": gathered_loss,
                "grad_norm": gathered_grad,
                "lr": lr_scheduler.get_last_lr()[0],
                "height": int(image.shape[-2]),
                "width": int(image.shape[-1]),
                "npu_allocated_gib_rank0": allocated,
                "npu_peak_gib_rank0": peak,
                "seconds_since_log": time.time() - last_log_time,
            }
            if accelerator.is_main_process:
                write_jsonl(metrics_path, payload)
            accelerator.log(payload, step=global_step)
            if global_step == 1 or global_step % args.log_interval == 0:
                LOGGER.info("METRICS %s", json.dumps(payload, ensure_ascii=False))
                last_log_time = time.time()

            if global_step % args.save_model_steps == 0:
                accelerator.wait_for_everyone()
                final_dir = work_dir / f"checkpoint-{global_step}"
                temp_dir = work_dir / f".checkpoint-{global_step}.tmp"
                if accelerator.is_main_process:
                    if temp_dir.exists():
                        shutil.rmtree(temp_dir)
                    temp_dir.mkdir(parents=True)
                accelerator.wait_for_everyone()
                accelerator.save_state(str(temp_dir))
                accelerator.wait_for_everyone()
                if accelerator.is_main_process:
                    os.replace(temp_dir, final_dir)
                    checkpoints = sorted(
                        ((int(item.name.split("-")[-1]), item) for item in work_dir.glob("checkpoint-*")),
                        key=lambda pair: pair[0],
                    )
                    for _, old in checkpoints[: -args.keep_last_checkpoints]:
                        shutil.rmtree(old)
                    LOGGER.info("Saved recoverable checkpoint %s", final_dir)
                accelerator.wait_for_everyone()

            if global_step >= args.max_train_steps:
                break
        if global_step >= args.max_train_steps:
            break

    accelerator.wait_for_everyone()
    if accelerator.is_main_process:
        final_adapter = work_dir / "adapter-final"
        accelerator.unwrap_model(transformer).save_pretrained(final_adapter)
        write_jsonl(log_dir / "events.jsonl", {"event": "complete", "time": time.time(), "step": global_step})
        LOGGER.info("Training complete at step %s; adapter=%s", global_step, final_adapter)
    accelerator.end_training()


if __name__ == "__main__":
    main()
