# Demo Runbook

MVP fallback path:

1. Start backend with `PROVIDER=mock`.
2. Start Vite frontend.
3. Use demo catalog assets.
4. Use `MockGestureSource` when camera or MediaPipe is unavailable.

Switch to `PROVIDER=cache` after reviewed generated assets are available.
