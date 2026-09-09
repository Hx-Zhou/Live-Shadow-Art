from fastapi import APIRouter, BackgroundTasks, Depends, status

from server.app.dependencies import get_generation_provider, get_task_queue
from server.app.generation.provider import GenerationProvider, GenerationProviderUnavailable
from server.app.generation.task_queue import TaskQueue
from server.app.schemas import TaskStatus, TextureGenerateRequest

router = APIRouter(prefix="/api/textures", tags=["textures"])


def run_generation(
  task_id: str,
  request: TextureGenerateRequest,
  queue: TaskQueue,
  provider: GenerationProvider,
) -> None:
  queue.start(task_id)
  try:
    result = provider.generate(request)
  except GenerationProviderUnavailable as exc:
    queue.fail(task_id, str(exc))
  except Exception as exc:
    queue.fail(task_id, f"Generation failed: {exc}")
  else:
    queue.succeed(task_id, result.asset_id, result.message)


@router.post("/generate", response_model=TaskStatus, status_code=status.HTTP_202_ACCEPTED)
def generate_texture(
  request: TextureGenerateRequest,
  background_tasks: BackgroundTasks,
  queue: TaskQueue = Depends(get_task_queue),
  provider: GenerationProvider = Depends(get_generation_provider),
) -> TaskStatus:
  task = queue.create(request)
  background_tasks.add_task(run_generation, task.task_id, request, queue, provider)
  return task.to_status()
