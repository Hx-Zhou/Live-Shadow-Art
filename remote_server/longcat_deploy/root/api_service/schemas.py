from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class APIModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class GenerationRequest(APIModel):
    kind: Literal["character", "background"]
    prompt: str = Field(min_length=1, max_length=2000)
    negative_prompt: str | None = Field(default=None, alias="negativePrompt", max_length=2500)
    width: int | None = Field(default=None, ge=256, le=1536)
    height: int | None = Field(default=None, ge=256, le=1536)
    steps: int | None = Field(default=None, ge=1, le=100)
    guidance_scale: float | None = Field(default=None, alias="guidanceScale", ge=0, le=20)
    seed: int | None = Field(default=None, ge=0, le=2**63 - 1)
    apply_style_template: bool = Field(default=True, alias="applyStyleTemplate")

    @model_validator(mode="after")
    def validate_dimensions(self) -> "GenerationRequest":
        default_width, default_height = (
            (1024, 1024) if self.kind == "character" else (1024, 576)
        )
        self.width = self.width or default_width
        self.height = self.height or default_height
        if self.width % 16 or self.height % 16:
            raise ValueError("width and height must be multiples of 16")
        if self.width * self.height > 1024 * 1024:
            raise ValueError("width * height must not exceed 1024 * 1024")
        return self


class JobAccepted(APIModel):
    task_id: str = Field(alias="taskId")
    status: Literal["queued"]
    status_url: str = Field(alias="statusUrl")


class JobStatus(APIModel):
    task_id: str = Field(alias="taskId")
    status: Literal["queued", "running", "succeeded", "failed"]
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    queue_position: int | None = Field(default=None, alias="queuePosition")
    image_url: str | None = Field(default=None, alias="imageUrl")
    metadata_url: str | None = Field(default=None, alias="metadataUrl")
    error: str | None = None
    request: dict
    result: dict | None = None


class HealthResponse(APIModel):
    ok: bool
    ready: bool
    engine: str
    model: str
    model_revision: str | None = Field(alias="modelRevision")
    adapter: str | None
    worker_pid: int | None = Field(alias="workerPid")
    worker_heartbeat: str | None = Field(alias="workerHeartbeat")
    queue_depth: int = Field(alias="queueDepth")
    error: str | None = None

