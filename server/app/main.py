from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.app.api import api_router
from server.app.dependencies import get_settings
from server.app.schemas import HealthResponse

settings = get_settings()

app = FastAPI(
  title="光影新生生成与资产服务",
  version="0.1.0",
  description="Texture generation, task tracking and asset lookup service.",
)

app.add_middleware(
  CORSMiddleware,
  allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

app.include_router(api_router)
app.mount("/static", StaticFiles(directory=settings.resolved_asset_root), name="static")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
  return HealthResponse(ok=True, provider=settings.provider)
