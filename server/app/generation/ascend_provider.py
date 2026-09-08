from server.app.schemas import TextureGenerateRequest

from .provider import GenerationProviderUnavailable, GenerationResult


class AscendGenerationProvider:
  name = "ascend"

  def generate(self, request: TextureGenerateRequest) -> GenerationResult:
    raise GenerationProviderUnavailable(
      "Ascend provider is not configured yet. Use PROVIDER=mock or PROVIDER=cache for MVP demos."
    )
