from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

from server.app.schemas import TaskStatus, TextureGenerateRequest


TaskState = Literal["queued", "running", "succeeded", "failed"]


@dataclass
class TaskRecord:
  task_id: str
  request: TextureGenerateRequest
  status: TaskState = "queued"
  progress: float = 0
  message: str | None = None
  asset_id: str | None = None
  error: str | None = None

  def to_status(self) -> TaskStatus:
    return TaskStatus(
      taskId=self.task_id,
      status=self.status,
      progress=self.progress,
      message=self.message,
      assetId=self.asset_id,
      error=self.error,
    )


class TaskQueue:
  def __init__(self):
    self.tasks: dict[str, TaskRecord] = {}

  def create(self, request: TextureGenerateRequest) -> TaskRecord:
    task = TaskRecord(task_id=uuid4().hex, request=request)
    self.tasks[task.task_id] = task
    return task

  def start(self, task_id: str) -> TaskRecord:
    task = self.require(task_id)
    task.status = "running"
    task.progress = 0.2
    return task

  def succeed(self, task_id: str, asset_id: str, message: str) -> TaskRecord:
    task = self.require(task_id)
    task.status = "succeeded"
    task.progress = 1
    task.asset_id = asset_id
    task.message = message
    return task

  def fail(self, task_id: str, error: str) -> TaskRecord:
    task = self.require(task_id)
    task.status = "failed"
    task.progress = 1
    task.error = error
    return task

  def require(self, task_id: str) -> TaskRecord:
    task = self.tasks.get(task_id)
    if not task:
      raise KeyError(task_id)
    return task
