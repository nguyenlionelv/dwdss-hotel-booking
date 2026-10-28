"""Analytics API endpoints for Operations Mart (DO-A01 to DO-A05)."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/status")
def analytics_status():
    return {"module": "analytics", "status": "scaffolded", "target_mart": "Operations Mart"}
