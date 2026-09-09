import json
from pathlib import Path

import pytest

from server.app.api.textures import run_generation
from server.app.assets.repository import AssetRepository
from server.app.generation.ascend_provider import AscendGenerationProvider
from server.app.generation.provider import GenerationProviderUnavailable, GenerationResult
from server.app.generation.task_queue import TaskQueue
from server.app.schemas import TextureGenerateRequest
from server.app.settings import CURRENT_LONGCAT_LORA_REVISION, Settings


PNG_STUB = b"\x89PNG\r\n\x1a\nunit-test"


def make_repository(root: Path) -> AssetRepository:
  (root / "demo").mkdir(parents=True)
  (root / "demo" / "catalog.json").write_text(
    json.dumps({"characters": [], "backgrounds": []}), encoding="utf-8"
  )
  return AssetRepository(root)


def make_provider(tmp_path: Path) -> AscendGenerationProvider:
  settings = Settings(
    PROVIDER="ascend",
    ASSET_ROOT=tmp_path,
    ASCEND_API_POLL_INTERVAL_SECONDS=0,
  )
  return AscendGenerationProvider(settings, make_repository(tmp_path))


def test_background_generation_uses_final_lora_and_registers_asset(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  provider = make_provider(tmp_path)
  calls: list[tuple[str, str, dict | None]] = []

  def fake_json(method: str, path: str, payload: dict | None = None) -> dict:
    calls.append((method, path, payload))
    if path == "/health":
      return {
        "ok": True,
        "ready": True,
        "engine": "diffusers-lora",
        "adapterRevision": CURRENT_LONGCAT_LORA_REVISION,
        "adapterScale": 0.8,
      }
    if path == "/api/v1/generations":
      return {"taskId": "remote-1", "status": "queued"}
    return {
      "taskId": "remote-1",
      "status": "succeeded",
      "request": {
        "prompt": "final server prompt",
        "negativePrompt": "no text",
        "seed": 3407,
      },
      "result": {"seed": 3407},
    }

  monkeypatch.setattr(provider, "_request_json", fake_json)
  monkeypatch.setattr(provider, "_request_bytes", lambda *_: PNG_STUB)

  result = provider.generate(
    TextureGenerateRequest(
      kind="background",
      style="traditional_shadow_puppet",
      prompt="江南水乡，中央留白",
      seed=3407,
    )
  )

  assert result.asset_id.startswith("longcat_background_")
  assert "待审核场景图" in result.message
  assert (tmp_path / "backgrounds" / f"{result.asset_id}.png").read_bytes() == PNG_STUB
  metadata = json.loads(
    (tmp_path / "backgrounds" / f"{result.asset_id}.json").read_text(encoding="utf-8")
  )
  assert metadata["source"]["adapterRevision"] == CURRENT_LONGCAT_LORA_REVISION
  assert metadata["source"]["prompt"] == "final server prompt"
  submitted = calls[1][2]
  assert submitted is not None
  assert submitted["steps"] == 50
  assert submitted["guidanceScale"] == 4.0
  assert submitted["applyStyleTemplate"] is True


def test_character_generation_is_marked_unrigged(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  provider = make_provider(tmp_path)
  responses = iter(
    [
      {
        "ok": True,
        "ready": True,
        "engine": "diffusers-lora",
        "adapterRevision": CURRENT_LONGCAT_LORA_REVISION,
        "adapterScale": 0.8,
      },
      {"taskId": "remote-2"},
      {
        "status": "succeeded",
        "request": {"prompt": "final character prompt", "seed": 42},
        "result": {"seed": 42},
      },
    ]
  )
  monkeypatch.setattr(provider, "_request_json", lambda *_args, **_kwargs: next(responses))
  monkeypatch.setattr(provider, "_request_bytes", lambda *_: PNG_STUB)

  result = provider.generate(
    TextureGenerateRequest(
      kind="character",
      style="traditional_shadow_puppet",
      prompt="哪吒侧身全身",
      rigType="humanoid",
      seed=42,
    )
  )

  manifest_path = tmp_path / "characters" / result.asset_id / "manifest.json"
  manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
  assert manifest["parts"] == []
  assert manifest["rig"] is None
  assert "unrigged" in manifest["tags"]
  assert "待分件角色审核图" in result.message


def test_provider_rejects_base_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  provider = make_provider(tmp_path)
  monkeypatch.setattr(
    provider,
    "_request_json",
    lambda *_args, **_kwargs: {
      "ok": True,
      "ready": True,
      "engine": "omni",
      "adapterRevision": None,
    },
  )

  with pytest.raises(GenerationProviderUnavailable, match="expected 'diffusers-lora'"):
    provider.generate(
      TextureGenerateRequest(
        kind="background",
        style="traditional_shadow_puppet",
        prompt="山水",
      )
    )


def test_provider_rejects_wrong_adapter_revision(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  provider = make_provider(tmp_path)
  monkeypatch.setattr(
    provider,
    "_request_json",
    lambda *_args, **_kwargs: {
      "ok": True,
      "ready": True,
      "engine": "diffusers-lora",
      "adapterRevision": "older-adapter",
    },
  )

  with pytest.raises(GenerationProviderUnavailable, match="Refusing adapter revision"):
    provider.generate(
      TextureGenerateRequest(
        kind="character",
        style="traditional_shadow_puppet",
        prompt="武将",
      )
    )


def test_background_task_updates_local_task_status() -> None:
  class FakeProvider:
    name = "fake"

    def generate(self, _request: TextureGenerateRequest) -> GenerationResult:
      return GenerationResult(asset_id="generated-asset", message="done")

  request = TextureGenerateRequest(
    kind="background",
    style="traditional_shadow_puppet",
    prompt="山水",
  )
  queue = TaskQueue()
  task = queue.create(request)

  run_generation(task.task_id, request, queue, FakeProvider())

  finished = queue.require(task.task_id)
  assert finished.status == "succeeded"
  assert finished.asset_id == "generated-asset"
  assert finished.progress == 1
