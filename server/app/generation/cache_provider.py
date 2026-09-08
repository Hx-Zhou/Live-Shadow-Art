from server.app.assets.repository import AssetRepository
from server.app.schemas import TextureGenerateRequest

from .provider import GenerationResult


class CacheGenerationProvider:
  name = "cache"

  def __init__(self, repository: AssetRepository):
    self.repository = repository

  def generate(self, request: TextureGenerateRequest) -> GenerationResult:
    record = self.repository.first(request.kind)
    return GenerationResult(asset_id=record.id, message="Cached asset selected")
