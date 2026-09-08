# Gesture Models

Gesture runtime code lives in `web/src/gesture/`. This directory stores model files, labels, datasets and metrics.

Expected layout:

- `mediapipe/`: MediaPipe model files or download notes.
- `classifier/`: exported MLP, ONNX or TFJS classifier.
- `dataset/`: captured landmark samples and labeling notes.
- `metrics/`: confusion matrices, Macro-F1, latency and false-trigger reports.
