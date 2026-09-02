
from fastapi import APIRouter, HTTPException
from datetime import timedelta
from minio import Minio
from urllib.parse import quote
from ..config import settings

router = APIRouter(prefix="/files", tags=["files"]) 

# Init MinIO client (geen creds in URL; gebruik env)
_mclient = Minio(
    endpoint=settings.MINIO_ENDPOINT.replace('http://','').replace('https://',''),
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE,
)

# Zorg dat bucket bestaat
try:
    found = _mclient.bucket_exists(settings.MINIO_BUCKET)
    if not found:
        _mclient.make_bucket(settings.MINIO_BUCKET)
except Exception:
    # laat fouten pas op runtime zien
    pass

@router.post("/presign")
def presign_upload(object_name: str):
    """Maak een pre-signed PUT URL voor upload naar MinIO."""
    try:
        url = _mclient.presigned_put_object(
            settings.MINIO_BUCKET,
            object_name,
            expires=timedelta(hours=1)
        )
        return {"upload_url": url, "bucket": settings.MINIO_BUCKET, "object": object_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
