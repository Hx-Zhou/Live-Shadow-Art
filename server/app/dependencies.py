from functools import lru_cache

from server.app.assets.repository import AssetRepository
from server.app.generation.ascend_provider import AscendGenerationProvider
from server.app.generation.cache_provider import CacheGenerationProvider
from server.app.generation.mock_provider import MockGenerationProvider
from server.app.generation.provider import GenerationProvider
from server.app.generation.task_queue import TaskQueue
from server.app.settings import Settings


@lru_cache
def get_settings() -> Settings:
  return Settings.from_env()


@lru_cache
def get_task_queue() -> TaskQueue:
  return TaskQueue()


@lru_cache
def get_asset_repository() -> AssetRepository:
  return AssetRepository(get_settings().resolved_asset_root)


@lru_cache
def get_generation_provider() -> GenerationProvider:
  settings = get_settings()
  if settings.provider == "cache":
    return CacheGenerationProvider(get_asset_repository())
  if settings.provider == "ascend":
    return AscendGenerationProvider()
  return MockGenerationProvider()
