from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


FINAL_ADAPTER_REVISION = (
    "01add3926eeb1cda1bbe5fcc4c6a61f6502a38cb2411633934202243c0b6898c"
)


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
    adapter_revision: str | None
    adapter_scale: float
    device: str
    vae_use_slicing: bool
    vae_use_tiling: bool
    default_steps: int
    default_guidance_scale: float
    max_pending_jobs: int

    @classmethod
    def from_env(cls) -> "Settings":
        deploy_root = Path(os.getenv("DEPLOY_ROOT", "/home/ma-user/work/longcat_deploy"))
        state_dir = Path(os.getenv("LONGCAT_API_STATE_DIR", str(deploy_root / "api_state_lora")))
        adapter_value = os.getenv(
            "LONGCAT_API_ADAPTER_DIR",
            "/home/ma-user/work/longcat_lora/outputs/mvp_1024_r16/adapter-final",
        ).strip()
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
            engine=os.getenv("LONGCAT_API_ENGINE", "diffusers-lora").strip().lower(),
            adapter_dir=Path(adapter_value) if adapter_value else None,
            adapter_revision=os.getenv("LONGCAT_API_ADAPTER_REVISION", FINAL_ADAPTER_REVISION),
            adapter_scale=float(os.getenv("LONGCAT_API_ADAPTER_SCALE", "0.8")),
            device=os.getenv("LONGCAT_API_DEVICE", "npu:0"),
            vae_use_slicing=_env_bool("LONGCAT_API_VAE_SLICING", False),
            vae_use_tiling=_env_bool("LONGCAT_API_VAE_TILING", False),
            default_steps=int(os.getenv("LONGCAT_API_DEFAULT_STEPS", "50")),
            default_guidance_scale=float(os.getenv("LONGCAT_API_DEFAULT_GUIDANCE", "4.0")),
            max_pending_jobs=int(os.getenv("LONGCAT_API_MAX_PENDING", "8")),
        )

    @property
    def database_path(self) -> Path:
        return self.state_dir / "jobs.sqlite3"

    def validate(self, *, require_model: bool) -> None:
        if self.engine != "diffusers-lora":
            raise ValueError("LONGCAT_API_ENGINE must be diffusers-lora")
        if self.adapter_dir is None:
            raise ValueError("diffusers-lora requires LONGCAT_API_ADAPTER_DIR")
        if not self.adapter_revision:
            raise ValueError("diffusers-lora requires LONGCAT_API_ADAPTER_REVISION")
        if not 0.0 <= self.adapter_scale <= 2.0:
            raise ValueError("LONGCAT_API_ADAPTER_SCALE must be between 0 and 2")
        if self.default_steps < 1 or self.default_steps > 100:
            raise ValueError("LONGCAT_API_DEFAULT_STEPS must be in [1, 100]")
        if self.max_pending_jobs < 1:
            raise ValueError("LONGCAT_API_MAX_PENDING must be positive")
        if require_model and not self.model_dir.is_dir():
            raise FileNotFoundError(self.model_dir)
        if require_model and self.adapter_dir is not None and not self.adapter_dir.is_dir():
            raise FileNotFoundError(self.adapter_dir)
