from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ai-engine"}

# ✅ ADD THIS
@router.get("/ping")
def ping() -> dict:
    return {"status": "ok", "message": "pong"}