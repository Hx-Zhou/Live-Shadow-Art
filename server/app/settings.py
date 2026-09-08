import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class Settings(BaseModel):
  provider: Literal["mock", "cache", "ascend"] = Field(default="mock", alias="PROVIDER")
  asset_root: Path = Field(default=Path("assets"), alias="ASSET_ROOT")
  model_root: Path = Field(default=Path("models"), alias="MODEL_ROOT")

  @classmethod
  def from_env(cls) -> "Settings":
    return cls(
      PROVIDER=os.getenv("PROVIDER", "mock"),
      ASSET_ROOT=Path(os.getenv("ASSET_ROOT", "assets")),
      MODEL_ROOT=Path(os.getenv("MODEL_ROOT", "models")),
    )

  @property
  def resolved_asset_root(self) -> Path:
    return self.asset_root.resolve()

  @property
  def resolved_model_root(self) -> Path:
    return self.model_root.resolve()
