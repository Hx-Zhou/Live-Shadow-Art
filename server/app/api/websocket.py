from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from server.app.dependencies import get_task_queue
from server.app.generation.task_queue import TaskQueue

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/generation/{sid}")
async def generation_progress(
  websocket: WebSocket,
  sid: str,
  queue: TaskQueue = Depends(get_task_queue),
) -> None:
  await websocket.accept()
  try:
    task = queue.require(sid)
    await websocket.send_json(task.to_status().model_dump(by_alias=True))
  except KeyError:
    await websocket.send_json({"taskId": sid, "status": "failed", "progress": 1, "error": "Task not found"})
  except WebSocketDisconnect:
    return
  finally:
    await websocket.close()
