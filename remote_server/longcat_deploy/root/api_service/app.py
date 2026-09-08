from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import FileResponse

from .config import Settings
from .schemas import GenerationRequest, HealthResponse, JobAccepted, JobStatus
from .store import JobStore


settings = Settings.from_env()
settings.validate(require_model=False)
store = JobStore(settings.database_path)
store.initialize()

app = FastAPI(
    title="LongCat-Image Ascend API",
    version="0.1.0",
    description="Queue-based LongCat-Image inference API for the remote Ascend 910B3 host.",
)


def require_token(authorization: str | None = Header(default=None)) -> None:
    if settings.api_token is None:
        return
    if authorization != f"Bearer {settings.api_token}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token")


def _public_job(job: dict) -> dict:
    result = job["result"]
    task_id = job["task_id"]
    return {
        "taskId": task_id,
        "status": job["status"],
        "createdAt": job["created_at"],
        "updatedAt": job["updated_at"],
        "queuePosition": job["queue_position"],
        "imageUrl": f"/api/v1/tasks/{task_id}/image" if result else None,
        "metadataUrl": f"/api/v1/tasks/{task_id}/metadata" if result else None,
        "error": job["error"],
        "request": job["request"],
        "result": result,
    }


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    state = store.get_state()
    worker_pid = state.get("worker_pid")
    worker_alive = False
    if isinstance(worker_pid, int) and worker_pid > 0:
        try:
            os.kill(worker_pid, 0)
        except OSError:
            pass
        else:
            worker_alive = True
    ready = bool(state.get("ready", False)) and worker_alive
    return HealthResponse(
        ok=ready and not state.get("error"),
        ready=ready,
        engine=state.get("engine", settings.engine),
        model=str(settings.model_dir),
        modelRevision=state.get("model_revision"),
        adapter=str(settings.adapter_dir) if settings.adapter_dir else None,
        workerPid=worker_pid if worker_alive else None,
        workerHeartbeat=state.get("worker_heartbeat"),
        queueDepth=store.pending_count(),
        error=state.get("error"),
    )


@app.post(
    "/api/v1/generations",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_token)],
)
def create_generation(request: GenerationRequest) -> JobAccepted:
    if store.pending_count() >= settings.max_pending_jobs:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Queue is full")
    payload = request.model_dump(by_alias=True)
    payload["steps"] = request.steps or settings.default_steps
    payload["guidanceScale"] = (
        request.guidance_scale
        if request.guidance_scale is not None
        else settings.default_guidance_scale
    )
    if request.seed is None:
        from secrets import randbits

        payload["seed"] = randbits(63)
    job = store.create(payload)
    return JobAccepted(
        taskId=job["task_id"],
        status="queued",
        statusUrl=f"/api/v1/tasks/{job['task_id']}",
    )


@app.get(
    "/api/v1/tasks/{task_id}",
    response_model=JobStatus,
    dependencies=[Depends(require_token)],
)
def get_task(task_id: str) -> JobStatus:
    try:
        return JobStatus.model_validate(_public_job(store.require(task_id)))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc


def _result_file(task_id: str, filename: str) -> Path:
    try:
        job = store.require(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    if job["status"] != "succeeded" or not job["result"]:
        raise HTTPException(status_code=409, detail=f"Task is {job['status']}")
    task_dir = (settings.output_dir / task_id).resolve()
    output_root = settings.output_dir.resolve()
    if output_root not in task_dir.parents:
        raise HTTPException(status_code=400, detail="Invalid task path")
    path = task_dir / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Result file not found")
    return path


@app.get("/api/v1/tasks/{task_id}/image", dependencies=[Depends(require_token)])
def get_image(task_id: str) -> FileResponse:
    return FileResponse(_result_file(task_id, "image.png"), media_type="image/png")


@app.get("/api/v1/tasks/{task_id}/metadata", dependencies=[Depends(require_token)])
def get_metadata(task_id: str) -> dict:
    path = _result_file(task_id, "metadata.json")
    return json.loads(path.read_text(encoding="utf-8"))
