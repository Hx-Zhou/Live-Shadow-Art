from __future__ import annotations

import logging
import os
import signal
import time
from pathlib import Path

from .config import Settings
from .runtime import create_runtime
from .store import JobStore, utc_now


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("longcat_api_worker")
stopping = False


def _request_stop(signum, _frame) -> None:
    global stopping
    logger.info("received signal %s; stopping after the current generation", signum)
    stopping = True


def _model_revision(model_dir: Path) -> str | None:
    path = model_dir / "MODEL_REVISION.txt"
    return path.read_text(encoding="utf-8").strip() if path.is_file() else None


def main() -> int:
    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    settings = Settings.from_env()
    settings.validate(require_model=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    store = JobStore(settings.database_path)
    store.initialize()
    recovered = store.recover_interrupted()
    store.set_state(
        ready=False,
        error=None,
        engine=settings.engine,
        model_revision=_model_revision(settings.model_dir),
        worker_pid=os.getpid(),
        worker_heartbeat=utc_now(),
        recovered_jobs=recovered,
    )
    runtime = create_runtime(settings)
    try:
        logger.info("loading engine=%s model=%s", settings.engine, settings.model_dir)
        runtime_info = runtime.load()
        store.set_state(ready=True, error=None, runtime=runtime_info, worker_heartbeat=utc_now())
        logger.info("runtime ready: %s", runtime_info)
        last_heartbeat = 0.0
        while not stopping:
            now = time.monotonic()
            if now - last_heartbeat >= 5:
                store.set_state(worker_heartbeat=utc_now())
                last_heartbeat = now
            job = store.claim_next()
            if job is None:
                time.sleep(0.5)
                continue
            task_id = job["task_id"]
            logger.info("starting task=%s", task_id)
            try:
                result = runtime.generate(task_id, job["request"])
            except Exception as exc:
                logger.exception("task failed task=%s", task_id)
                store.fail(task_id, f"{type(exc).__name__}: {exc}")
            else:
                store.finish(task_id, result)
                logger.info(
                    "task succeeded task=%s seconds=%.3f sha256=%s",
                    task_id,
                    result["generationSeconds"],
                    result["imageSha256"],
                )
    except Exception as exc:
        logger.exception("worker failed")
        store.set_state(ready=False, error=f"{type(exc).__name__}: {exc}", worker_heartbeat=utc_now())
        return 1
    finally:
        runtime.close()
        store.set_state(ready=False, worker_heartbeat=utc_now(), worker_pid=None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

