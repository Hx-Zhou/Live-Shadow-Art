# Architecture

The MVP is split into three replaceable lines:

- A: texture generation provider under `server/app/generation/`.
- B: gesture source under `web/src/gesture/GestureSource.ts`.
- C: stage, controls, assets and integration under `web/src/theater/`, `web/src/control/`, `server/app/api/` and `assets/`.

Frozen boundaries:

- `packages/schemas/openapi.yaml`
- `packages/schemas/*.schema.json`
- `web/src/gesture/GestureSource.ts`
- `controls/controls.json`
- `assets/characters/*/rig.json`
- `assets/characters/*/manifest.json`
