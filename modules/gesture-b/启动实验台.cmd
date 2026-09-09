@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "GESTURE_NODE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
if exist "%GESTURE_NODE%" (
  "%GESTURE_NODE%" tools\serve.mjs
) else (
  node tools\serve.mjs
)
pause
