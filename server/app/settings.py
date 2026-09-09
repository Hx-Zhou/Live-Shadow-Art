import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


CURRENT_LONGCAT_LORA_REVISION = (
  "01add3926eeb1cda1bbe5fcc4c6a61f6502a38cb2411633934202243c0b6898c"
)


class Settings(BaseModel):
  provider: Literal["mock", "cache", "ascend"] = Field(default="mock", alias="PROVIDER")
  asset_root: Path = Field(default=Path("assets"), alias="ASSET_ROOT")
  model_root: Path = Field(default=Path("models"), alias="MODEL_ROOT")
  ascend_api_base_url: str = Field(
    default="http://127.0.0.1:8010", alias="ASCEND_API_BASE_URL"
  )
  ascend_api_token: str | None = Field(default=None, alias="ASCEND_API_TOKEN")
  ascend_api_poll_timeout_seconds: float = Field(
    default=600.0, alias="ASCEND_API_POLL_TIMEOUT_SECONDS"
  )
  ascend_api_poll_interval_seconds: float = Field(
    default=2.0, alias="ASCEND_API_POLL_INTERVAL_SECONDS"
  )
  ascend_api_request_timeout_seconds: float = Field(
    default=30.0, alias="ASCEND_API_REQUEST_TIMEOUT_SECONDS"
  )
  ascend_api_steps: int = Field(default=50, alias="ASCEND_API_STEPS")
  ascend_api_guidance_scale: float = Field(default=4.0, alias="ASCEND_API_GUIDANCE_SCALE")
  ascend_api_required_engine: str = Field(
    default="diffusers-lora", alias="ASCEND_API_REQUIRED_ENGINE"
  )
  ascend_api_required_adapter_revision: str = Field(
    default=CURRENT_LONGCAT_LORA_REVISION,
    alias="ASCEND_API_REQUIRED_ADAPTER_REVISION",
  )

  @classmethod
  def from_env(cls) -> "Settings":
    return cls(
      PROVIDER=os.getenv("PROVIDER", "mock"),
      ASSET_ROOT=Path(os.getenv("ASSET_ROOT", "assets")),
      MODEL_ROOT=Path(os.getenv("MODEL_ROOT", "models")),
      ASCEND_API_BASE_URL=os.getenv("ASCEND_API_BASE_URL", "http://127.0.0.1:8010"),
      ASCEND_API_TOKEN=os.getenv("ASCEND_API_TOKEN") or None,
      ASCEND_API_POLL_TIMEOUT_SECONDS=float(
        os.getenv("ASCEND_API_POLL_TIMEOUT_SECONDS", "600")
      ),
      ASCEND_API_POLL_INTERVAL_SECONDS=float(
        os.getenv("ASCEND_API_POLL_INTERVAL_SECONDS", "2")
      ),
      ASCEND_API_REQUEST_TIMEOUT_SECONDS=float(
        os.getenv("ASCEND_API_REQUEST_TIMEOUT_SECONDS", "30")
      ),
      ASCEND_API_STEPS=int(os.getenv("ASCEND_API_STEPS", "50")),
      ASCEND_API_GUIDANCE_SCALE=float(os.getenv("ASCEND_API_GUIDANCE_SCALE", "4.0")),
      ASCEND_API_REQUIRED_ENGINE=os.getenv(
        "ASCEND_API_REQUIRED_ENGINE", "diffusers-lora"
      ),
      ASCEND_API_REQUIRED_ADAPTER_REVISION=os.getenv(
        "ASCEND_API_REQUIRED_ADAPTER_REVISION", CURRENT_LONGCAT_LORA_REVISION
      ),
    )

  @property
  def resolved_asset_root(self) -> Path:
    return self.asset_root.resolve()

  @property
  def resolved_model_root(self) -> Path:
    return self.model_root.resolve()
