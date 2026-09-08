from fastapi import APIRouter, Depends, HTTPException

from server.app.assets.repository import AssetNotFoundError, AssetRepository
from server.app.dependencies import get_asset_repository
from server.app.schemas import AssetResponse

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("/{asset_id}", response_model=AssetResponse)
def get_asset(
  asset_id: str,
  repository: AssetRepository = Depends(get_asset_repository),
) -> AssetResponse:
  try:
    record = repository.get(asset_id)
  except AssetNotFoundError as exc:
    raise HTTPException(status_code=404, detail="Asset not found") from exc
  return AssetResponse(
    id=record.id,
    kind=record.kind,
    name=record.name,
    baseUrl=record.base_url,
    manifestUrl=record.manifest_url,
    previewUrl=record.preview_url,
  )
