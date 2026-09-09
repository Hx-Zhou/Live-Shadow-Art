import pytest

from remote_server.longcat_deploy.root.api_service.config import (
    FINAL_ADAPTER_REVISION,
    Settings,
)
from remote_server.longcat_deploy.root.api_service.runtime import (
    DiffusersLoraRuntime,
    create_runtime,
)


def test_default_runtime_is_final_lora(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "LONGCAT_API_ENGINE",
        "LONGCAT_API_ADAPTER_DIR",
        "LONGCAT_API_ADAPTER_REVISION",
        "LONGCAT_API_ADAPTER_SCALE",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_env()

    assert settings.engine == "diffusers-lora"
    assert settings.adapter_revision == FINAL_ADAPTER_REVISION
    assert settings.adapter_scale == 0.8
    assert settings.adapter_dir is not None
    settings.validate(require_model=False)


def test_non_lora_runtime_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LONGCAT_API_ENGINE", "omni")

    with pytest.raises(ValueError, match="must be diffusers-lora"):
        Settings.from_env().validate(require_model=False)


def test_runtime_factory_only_returns_final_lora() -> None:
    runtime = create_runtime(Settings.from_env())

    assert isinstance(runtime, DiffusersLoraRuntime)
