from fastapi import APIRouter, Depends, HTTPException

from server.app.dependencies import get_task_queue
from server.app.generation.task_queue import TaskQueue
from server.app.schemas import TaskStatus

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=TaskStatus)
def get_task(task_id: str, queue: TaskQueue = Depends(get_task_queue)) -> TaskStatus:
  try:
    return queue.require(task_id).to_status()
  except KeyError as exc:
    raise HTTPException(status_code=404, detail="Task not found") from exc
