# Ascend Deploy

Current status: the remote LongCat-Image model has a queue-based API under
`remote_server/longcat_deploy/root/api_service/`. The verified base runtime uses BF16, 50 steps,
guidance 4.0 and TP=2. It is reached through an SSH tunnel rather than a public listener.

To complete this line:

1. Follow `remote_server/longcat_deploy/API使用说明.md` to start and verify the remote API.
2. Keep model weights, SSH keys and API tokens outside Git.
3. Complete the final LoRA comparison before switching the API engine from `omni` to
   `diffusers-lora`.
4. Implement the application-side asset post-processing bridge before changing
   `server/app/generation/ascend_provider.py`; raw generated images are not yet rigged asset packs.
5. Keep `PROVIDER=cache` as the classroom-demo fallback.
