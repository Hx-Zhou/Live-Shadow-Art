from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    deploy_root: Path
    model_dir: Path
    state_dir: Path
    output_dir: Path
    api_token: str | None
    engine: str
    adapter_dir: Path | None
    adapter_scale: float
    device: str
    tensor_parallel_size: int
    cfg_parallel_size: int
    ulysses_degree: int
    ring_degree: int
    vae_use_slicing: bool
    vae_use_tiling: bool
    default_steps: int
    default_guidance_scale: float
    max_pending_jobs: int

    @classmethod
    def from_env(cls) -> "Settings":
        deploy_root = Path(os.getenv("DEPLOY_ROOT", "/home/ma-user/work/longcat_deploy"))
        state_dir = Path(os.getenv("LONGCAT_API_STATE_DIR", str(deploy_root / "api_state")))
        adapter_value = os.getenv("LONGCAT_API_ADAPTER_DIR", "").strip()
        return cls(
            deploy_root=deploy_root,
            model_dir=Path(
                os.getenv("LONGCAT_API_MODEL_DIR", str(deploy_root / "models/LongCat-Image"))
            ),
            state_dir=state_dir,
            output_dir=Path(
                os.getenv("LONGCAT_API_OUTPUT_DIR", str(state_dir / "outputs"))
            ),
            api_token=os.getenv("LONGCAT_API_TOKEN") or None,
            engine=os.getenv("LONGCAT_API_ENGINE", "omni").strip().lower(),
            adapter_dir=Path(adapter_value) if adapter_value else None,
            adapter_scale=float(os.getenv("LONGCAT_API_ADAPTER_SCALE", "1.0")),
            device=os.getenv("LONGCAT_API_DEVICE", "npu:0"),
            tensor_parallel_size=int(os.getenv("LONGCAT_API_TP", "2")),
            cfg_parallel_size=int(os.getenv("LONGCAT_API_CFG_PARALLEL", "1")),
            ulysses_degree=int(os.getenv("LONGCAT_API_ULYSSES", "1")),
            ring_degree=int(os.getenv("LONGCAT_API_RING", "1")),
            vae_use_slicing=_env_bool("LONGCAT_API_VAE_SLICING", True),
            vae_use_tiling=_env_bool("LONGCAT_API_VAE_TILING", True),
            default_steps=int(os.getenv("LONGCAT_API_DEFAULT_STEPS", "50")),
            default_guidance_scale=float(os.getenv("LONGCAT_API_DEFAULT_GUIDANCE", "4.0")),
            max_pending_jobs=int(os.getenv("LONGCAT_API_MAX_PENDING", "8")),
        )

    @property
    def database_path(self) -> Path:
        return self.state_dir / "jobs.sqlite3"

    def validate(self, *, require_model: bool) -> None:
        if self.engine not in {"omni", "diffusers-lora"}:
            raise ValueError("LONGCAT_API_ENGINE must be omni or diffusers-lora")
        if self.engine == "diffusers-lora" and self.adapter_dir is None:
            raise ValueError("diffusers-lora requires LONGCAT_API_ADAPTER_DIR")
        if not 0.0 <= self.adapter_scale <= 2.0:
            raise ValueError("LONGCAT_API_ADAPTER_SCALE must be between 0 and 2")
        if min(
            self.tensor_parallel_size,
            self.cfg_parallel_size,
            self.ulysses_degree,
            self.ring_degree,
        ) < 1:
            raise ValueError("parallel degrees must be positive")
        if self.default_steps < 1 or self.default_steps > 100:
            raise ValueError("LONGCAT_API_DEFAULT_STEPS must be in [1, 100]")
        if self.max_pending_jobs < 1:
            raise ValueError("LONGCAT_API_MAX_PENDING must be positive")
        if require_model and not self.model_dir.is_dir():
            raise FileNotFoundError(self.model_dir)
        if require_model and self.adapter_dir is not None and not self.adapter_dir.is_dir():
            raise FileNotFoundError(self.adapter_dir)
