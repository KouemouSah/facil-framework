from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/modules/alpha", tags=["alpha"])


@router.get("/ping")
async def ping() -> dict:
    return {"module": "alpha", "pong": True}
