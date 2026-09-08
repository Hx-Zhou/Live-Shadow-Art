from fastapi import APIRouter, Depends, status

from server.app.dependencies import get_generation_provider, get_task_queue
from server.app.generation.provider import GenerationProvider, GenerationProviderUnavailable
from server.app.generation.task_queue import TaskQueue
from server.app.schemas import TaskStatus, TextureGenerateRequest

router = APIRouter(prefix="/api/textures", tags=["textures"])


@router.post("/generate", response_model=TaskStatus, status_code=status.HTTP_202_ACCEPTED)
def generate_texture(
  request: TextureGenerateRequest,
  queue: TaskQueue = Depends(get_task_queue),
  provider: GenerationProvider = Depends(get_generation_provider),
) -> TaskStatus:
  task = queue.create(request)
  queue.start(task.task_id)
  try:
    result = provider.generate(request)
  except GenerationProviderUnavailable as exc:
    task = queue.fail(task.task_id, str(exc))
  except Exception as exc:
    task = queue.fail(task.task_id, f"Generation failed: {exc}")
  else:
    task = queue.succeed(task.task_id, result.asset_id, result.message)
  return task.to_status()
