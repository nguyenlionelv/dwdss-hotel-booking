"""Reporting API endpoints for Operations Mart (DO-R01 to DO-R02)."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/status")
def reports_status():
    return {"module": "reports", "status": "scaffolded", "target_reports": ["DO-R01", "DO-R02"]}
