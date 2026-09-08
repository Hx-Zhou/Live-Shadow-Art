from dataclasses import dataclass
from typing import Protocol

from server.app.schemas import TextureGenerateRequest


class GenerationProviderUnavailable(RuntimeError):
  pass


@dataclass(frozen=True)
class GenerationResult:
  asset_id: str
  message: str


class GenerationProvider(Protocol):
  name: str

  def generate(self, request: TextureGenerateRequest) -> GenerationResult:
    ...
