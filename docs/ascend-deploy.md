# Ascend Deploy

Current status: the persistent remote service runs the final LongCat-Image LoRA through a
queue-based API under `remote_server/longcat_deploy/root/api_service/`. The selected runtime is
Ascend 910B3 BF16, 50 steps, guidance 4.0, adapter scale 0.8. The adapter revision is
`01add3926eeb1cda1bbe5fcc4c6a61f6502a38cb2411633934202243c0b6898c`.

The service only binds remote `127.0.0.1:8010`. It must be reached through the SSH tunnel created
by `scripts/connect-longcat-api.sh`; model weights, private keys and tokens remain outside Git.

## Power-off recovery boundary

`/home/ma-user/work` is the persistent volume and contains the model, adapter, environment, API
source, private configuration, queue database and recovery scripts. The notebook container root
filesystem is ephemeral. This ModelArts instance currently has no `container_post_start` hook,
user systemd is unavailable and user cron is prohibited, so repository code cannot power on the
instance or honestly guarantee an OS-boot daemon.

The supported workflow is therefore start-on-first-use:

1. Power on the ModelArts instance in the cloud console.
2. Run `./scripts/connect-longcat-api.sh /absolute/path/KeyPair-2133.pem` locally.
3. The connector executes remote `ensure_api.sh`, waits for the exact LoRA revision to report
   `ready=true`, and only then opens the tunnel.
4. Start the project backend with `PROVIDER=ascend`.

The recovery scripts validate command lines before signalling persisted PIDs. This prevents a PID
reused after reboot from causing an unrelated process to be killed. A verified recovery test
stopped both API processes, replaced both PID files with PID 1, and recovered to the exact final
LoRA while PID 1 remained alive.

## Application bridge

`server/app/generation/ascend_provider.py` now performs the complete application-side exchange:
health/version validation, queue submission, status polling, PNG download and asset registration.
It refuses every non-LoRA engine, a missing adapter revision or any revision other than the selected
final LoRA.
The public project endpoint schedules this work in a FastAPI background task, returns HTTP 202 with
a local task ID immediately, and exposes progress through `/api/tasks/{task_id}`.

Generated backgrounds are registered as readable but review-required scene assets. A generated
character is saved with `source.png`, `preview.png` and an `unrigged` manifest; raw text-to-image
output is not misrepresented as an articulated asset pack. Background central-space/pollution
review, transparent part segmentation and rig authoring remain separate production steps. Keep
`PROVIDER=cache` as the classroom-demo fallback.
