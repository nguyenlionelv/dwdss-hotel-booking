"""Decision Support System (DSS) API endpoints for demand forecasting (DO-M01)."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/dss", tags=["DSS"])


@router.get("/status")
def dss_status():
    """Return readiness status for the DSS module.

    Vai trò (Role):
        API endpoint kiểm tra trạng thái sẵn sàng của phân hệ hệ hỗ trợ ra quyết định (DSS)
        cho mô hình dự báo nhu cầu lưu trú (DO-M01 Demand Forecast).

    Input:
        - Không có tham số đầu vào.

    Output:
        - dict[str, str]: Từ điển JSON chứa tên module (`"dss"`), trạng thái (`"scaffolded"`)
          và mô hình mục tiêu (`"DO-M01 Demand Forecast (7-day horizon)"`).
    """
    return {"module": "dss", "status": "scaffolded", "target_model": "DO-M01 Demand Forecast (7-day horizon)"}
