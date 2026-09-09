from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from server.app.assets.repository import AssetRepository
from server.app.schemas import TextureGenerateRequest
from server.app.settings import Settings

from .provider import GenerationProviderUnavailable, GenerationResult


class AscendGenerationProvider:
  """Bridge the project API to the persistent LongCat LoRA queue service."""

  name = "ascend"

  def __init__(self, settings: Settings, repository: AssetRepository):
    self.settings = settings
    self.repository = repository
    self.base_url = settings.ascend_api_base_url.rstrip("/")

  def generate(self, request: TextureGenerateRequest) -> GenerationResult:
    if request.count != 1:
      raise GenerationProviderUnavailable(
        "The Ascend bridge currently accepts count=1 so every task maps to one asset."
      )

    try:
      health = self._request_json("GET", "/health")
      self._validate_health(health)
      accepted = self._request_json(
        "POST",
        "/api/v1/generations",
        {
          "kind": request.kind,
          "prompt": request.prompt,
          "negativePrompt": request.negative_prompt,
          "steps": self.settings.ascend_api_steps,
          "guidanceScale": self.settings.ascend_api_guidance_scale,
          "seed": request.seed,
          "applyStyleTemplate": True,
        },
      )
      remote_task_id = self._required_string(accepted, "taskId")
      task = self._wait_for_task(remote_task_id)
      result = task.get("result") or {}
      final_seed = int(result.get("seed", task.get("request", {}).get("seed")))
      image = self._request_bytes("GET", f"/api/v1/tasks/{remote_task_id}/image")
      record = self.repository.save_generated_image(
        kind=request.kind,
        image=image,
        prompt=str(task.get("request", {}).get("prompt", request.prompt)),
        negative_prompt=task.get("request", {}).get("negativePrompt"),
        seed=final_seed,
        remote_task_id=remote_task_id,
        adapter_revision=self.settings.ascend_api_required_adapter_revision,
        adapter_scale=float(health.get("adapterScale", 0.8)),
      )
    except GenerationProviderUnavailable:
      raise
    except (
      HTTPError,
      URLError,
      TimeoutError,
      TypeError,
      ValueError,
      KeyError,
      json.JSONDecodeError,
    ) as exc:
      raise GenerationProviderUnavailable(f"LongCat LoRA API request failed: {exc}") from exc

    qualifier = "待审核场景图" if request.kind == "background" else "待分件角色审核图"
    return GenerationResult(
      asset_id=record.id,
      message=f"LongCat LoRA 已生成{qualifier}；远端任务 {remote_task_id}",
    )

  def _validate_health(self, health: dict[str, Any]) -> None:
    if not health.get("ok") or not health.get("ready"):
      error = health.get("error") or "model is not ready"
      raise GenerationProviderUnavailable(
        f"LongCat LoRA API is unavailable: {error}. Run scripts/connect-longcat-api.sh first."
      )
    engine = str(health.get("engine", ""))
    if engine != "diffusers-lora":
      raise GenerationProviderUnavailable(
        f"Refusing remote engine {engine!r}; expected 'diffusers-lora'."
      )
    revision = str(health.get("adapterRevision", ""))
    expected = self.settings.ascend_api_required_adapter_revision
    if revision != expected:
      raise GenerationProviderUnavailable(
        f"Refusing adapter revision {revision or '<missing>'}; expected {expected}."
      )

  def _wait_for_task(self, task_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + self.settings.ascend_api_poll_timeout_seconds
    while time.monotonic() < deadline:
      task = self._request_json("GET", f"/api/v1/tasks/{task_id}")
      status = task.get("status")
      if status == "succeeded":
        return task
      if status == "failed":
        raise GenerationProviderUnavailable(
          f"LongCat LoRA task {task_id} failed: {task.get('error') or 'unknown error'}"
        )
      if status not in {"queued", "running"}:
        raise GenerationProviderUnavailable(
          f"LongCat LoRA task {task_id} returned invalid status {status!r}."
        )
      time.sleep(self.settings.ascend_api_poll_interval_seconds)
    raise GenerationProviderUnavailable(
      f"LongCat LoRA task {task_id} exceeded "
      f"{self.settings.ascend_api_poll_timeout_seconds:g}s."
    )

  def _request_json(
    self, method: str, path: str, payload: dict[str, Any] | None = None
  ) -> dict[str, Any]:
    raw = None
    headers = {"Accept": "application/json"}
    if payload is not None:
      raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
      headers["Content-Type"] = "application/json"
    response = self._open(method, path, raw, headers)
    decoded = json.loads(response.decode("utf-8"))
    if not isinstance(decoded, dict):
      raise ValueError("LongCat LoRA API returned a non-object JSON response")
    return decoded

  def _request_bytes(self, method: str, path: str) -> bytes:
    content = self._open(method, path, None, {"Accept": "image/png"})
    if len(content) > 32 * 1024 * 1024:
      raise ValueError("LongCat LoRA image exceeds the 32 MiB safety limit")
    return content

  def _open(self, method: str, path: str, data: bytes | None, headers: dict[str, str]) -> bytes:
    if self.settings.ascend_api_token:
      headers["Authorization"] = f"Bearer {self.settings.ascend_api_token}"
    request = Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
    with urlopen(request, timeout=self.settings.ascend_api_request_timeout_seconds) as response:
      return response.read(32 * 1024 * 1024 + 1)

  @staticmethod
  def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
      raise ValueError(f"LongCat LoRA response is missing {key}")
    return value
