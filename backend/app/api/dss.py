"""Decision Support System (DSS) API endpoints for demand forecasting (DO-M01)."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/dss", tags=["DSS"])


@router.get("/status")
def dss_status():
    return {"module": "dss", "status": "scaffolded", "target_model": "DO-M01 Demand Forecast (7-day horizon)"}
