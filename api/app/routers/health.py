from fastapi import APIRouter
router=APIRouter()
@router.get("/healthz")
def h(): return {"status":"ok"}