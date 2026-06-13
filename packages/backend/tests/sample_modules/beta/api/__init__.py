from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/modules/beta", tags=["beta"])


@router.get("/ping")
async def ping() -> dict:
    return {"module": "beta", "pong": True}
