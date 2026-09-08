from fastapi import APIRouter

from server.app.schemas import ScriptAct, ScriptGenerateRequest, ScriptGenerateResponse

router = APIRouter(prefix="/api/script", tags=["script"])


@router.post("/generate", response_model=ScriptGenerateResponse)
def generate_script(request: ScriptGenerateRequest) -> ScriptGenerateResponse:
  duration = max(1000, int((request.duration_seconds * 1000) / max(1, len(request.actors))))
  acts = [
    ScriptAct(
      id=f"act_{index + 1}",
      actor=actor,
      action="idle" if index == 0 else "walk",
      durationMs=duration,
      dialogue=f"{request.theme}: {actor}",
      background=None,
    )
    for index, actor in enumerate(request.actors)
  ]
  return ScriptGenerateResponse(acts=acts)
