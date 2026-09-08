from server.app.schemas import TextureGenerateRequest

from .provider import GenerationResult


class MockGenerationProvider:
  name = "mock"

  def generate(self, request: TextureGenerateRequest) -> GenerationResult:
    if request.kind == "background":
      return GenerationResult(asset_id="paper_curtain", message="Mock background selected")
    if request.rig_type == "animal":
      return GenerationResult(asset_id="forest_fox", message="Mock animal character selected")
    return GenerationResult(asset_id="hero_rabbit", message="Mock humanoid character selected")
