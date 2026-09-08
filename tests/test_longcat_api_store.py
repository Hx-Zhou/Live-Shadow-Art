from pathlib import Path

from remote_server.longcat_deploy.root.api_service.store import JobStore


def test_job_lifecycle_and_recovery(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "state" / "jobs.sqlite3")
    store.initialize()
    first = store.create({"prompt": "first"})
    second = store.create({"prompt": "second"})

    assert store.require(first["task_id"])["queue_position"] == 1
    assert store.require(second["task_id"])["queue_position"] == 2
    claimed = store.claim_next()
    assert claimed is not None
    assert claimed["task_id"] == first["task_id"]
    assert claimed["status"] == "running"

    assert store.recover_interrupted() == 1
    assert store.require(first["task_id"])["status"] == "queued"
    claimed_again = store.claim_next()
    assert claimed_again is not None
    store.finish(claimed_again["task_id"], {"imagePath": "/tmp/image.png"})
    assert store.require(first["task_id"])["status"] == "succeeded"

    claimed_second = store.claim_next()
    assert claimed_second is not None
    store.fail(claimed_second["task_id"], "expected")
    assert store.require(second["task_id"])["error"] == "expected"

