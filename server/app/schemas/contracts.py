from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
  model_config = ConfigDict(populate_by_name=True, extra="forbid")


class HealthResponse(APIModel):
  ok: bool
  provider: Literal["mock", "cache", "ascend"]


class TextureGenerateRequest(APIModel):
  kind: Literal["character", "background"]
  style: str
  prompt: str
  negative_prompt: str | None = Field(default=None, alias="negativePrompt")
  rig_type: Literal["humanoid", "animal"] | None = Field(default=None, alias="rigType")
  palette: list[str] | None = None
  seed: int | None = None
  count: int = 1


class TaskStatus(APIModel):
  task_id: str = Field(alias="taskId")
  status: Literal["queued", "running", "succeeded", "failed"]
  progress: float
  message: str | None = None
  asset_id: str | None = Field(default=None, alias="assetId")
  error: str | None = None


class AssetResponse(APIModel):
  id: str
  kind: Literal["character", "background"]
  name: str
  base_url: str = Field(alias="baseUrl")
  manifest_url: str = Field(alias="manifestUrl")
  preview_url: str | None = Field(default=None, alias="previewUrl")


class ScriptGenerateRequest(APIModel):
  theme: str
  actors: list[str]
  duration_seconds: int = Field(alias="durationSeconds")


class ScriptAct(APIModel):
  id: str
  actor: str
  action: str
  duration_ms: int = Field(alias="durationMs")
  dialogue: str | None = None
  background: str | None = None


class ScriptGenerateResponse(APIModel):
  acts: list[ScriptAct]
