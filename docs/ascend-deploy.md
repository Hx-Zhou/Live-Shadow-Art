# Ascend Deploy

Current status: provider interface is ready; real Ascend runtime is not configured.

To complete this line:

1. Convert the selected generation model and LoRA into Ascend-compatible artifacts.
2. Record model paths and checksums in `models/generation/configs/model-versions.json`.
3. Implement `server/app/generation/ascend_provider.py`.
4. Keep `PROVIDER=cache` as fallback for demos.
