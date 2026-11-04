"""Main entry point for the FastAPI backend application."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.analytics import router as analytics_router
from backend.app.api.dss import router as dss_router
from backend.app.api.metadata import router as metadata_router
from backend.app.api.reports import router as reports_router
from backend.app.core.config import get_settings


def create_app(dbname: str | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance.

    Vai trò (Role):
        Khởi tạo ứng dụng FastAPI chính cho hệ thống DWDSS Hotel Booking (Operations Mart),
        cấu hình middleware CORS, gắn thông tin override database (nếu có dùng cho kiểm thử),
        và đăng ký toàn bộ các API router (Metadata, Analytics, Reports, DSS).

    Input:
        - dbname (str | None, mặc định=None): Tên cơ sở dữ liệu PostgreSQL tùy chọn để ghi đè
          cấu hình mặc định trong `app.state.dbname` (thường phục vụ kiểm thử tích hợp).

    Output:
        - FastAPI: Thực thể ứng dụng FastAPI đã được cấu hình đầy đủ middleware và routers.
    """
    settings = get_settings()
    app = FastAPI(
        title="DWDSS Hotel Booking API - Operations Mart (City Hotel)",
        version="1.0.0",
        description="FastAPI backend serving Analytics, Reports, and DSS endpoints for City Hotel Lisbon.",
    )

    # Attach dbname override if provided (useful for integration test fixtures)
    app.state.dbname = dbname

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(metadata_router)
    app.include_router(analytics_router)
    app.include_router(reports_router)
    app.include_router(dss_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
