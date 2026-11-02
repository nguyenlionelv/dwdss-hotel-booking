"""Reporting API endpoints for Operations Mart (DO-R01 & DO-R02)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
import psycopg

from backend.app.api.metadata import get_db
from backend.app.schemas.reports import CapacitySummaryResponse, WeeklyDemandResponse
from backend.app.services.reporting_service import ReportingService

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/status")
def reports_status():
    """Return readiness status for the Reports module.

    Vai trò (Role):
        API endpoint kiểm tra trạng thái sẵn sàng của phân hệ báo cáo vận hành (Reports)
        phục vụ các mẫu báo cáo chuẩn DO-R01 và DO-R02.

    Input:
        - Không có tham số đầu vào.

    Output:
        - dict[str, Any]: Từ điển JSON chứa tên module (`"reports"`), trạng thái (`"ready"`)
          và danh sách mã báo cáo hỗ trợ (`["DO-R01", "DO-R02"]`).
    """
    return {"module": "reports", "status": "ready", "target_reports": ["DO-R01", "DO-R02"]}


@router.get("/operations/weekly-demand", response_model=WeeklyDemandResponse)
@router.get("/operations/weekly", response_model=WeeklyDemandResponse)
def get_weekly_demand_report(
    week: str | None = Query(None, description="ISO Week key e.g. 2017-W32"),
    iso_year: int | None = Query(None, description="ISO Year e.g. 2017"),
    iso_week: int | None = Query(None, description="ISO Week number 1..53"),
    start_date: str | None = Query(None, description="Explicit start date YYYY-MM-DD"),
    end_date: str | None = Query(None, description="Explicit end date YYYY-MM-DD"),
    conn: psycopg.Connection = Depends(get_db),
) -> WeeklyDemandResponse:
    """Return DO-R01 Weekly Demand Report with reconciled daily log and DO-R02 capacity directives.

    Vai trò (Role):
        API endpoint kết xuất Báo cáo nhu cầu vận hành hàng tuần (DO-R01 Weekly Demand Report),
        cung cấp bảng nhật ký chi tiết từng ngày trong tuần đã đối soát, thống kê tổng hợp tuần
        và các khuyến nghị điều phối ca/công suất (DO-R02 capacity directives).

    Input:
        - week (str | None, mặc định=None): Chuỗi tuần chuẩn ISO (ví dụ: `"2017-W32"`).
        - iso_year (int | None, mặc định=None): Năm ISO (ví dụ: `2017`).
        - iso_week (int | None, mặc định=None): Số thứ tự tuần ISO (`1..53`).
        - start_date (str | None, mặc định=None): Ngày bắt đầu tùy chỉnh (`YYYY-MM-DD`).
        - end_date (str | None, mặc định=None): Ngày kết thúc tùy chỉnh (`YYYY-MM-DD`).
        - conn (psycopg.Connection): Kết nối DB chỉ đọc từ `Depends(get_db)`.

    Output:
        - WeeklyDemandResponse: Đối tượng schema chứa thông tin kỳ báo cáo, KPI tổng hợp tuần (`summary`),
          nhật ký từng ngày (`daily_rows`) và khuyến nghị bố trí nhân sự (`capacity_summary`).
          Ném `HTTPException(404)` nếu không có dữ liệu hoặc `HTTPException(503)` nếu lỗi DB/mart.
    """
    try:
        return ReportingService.get_weekly_demand_report(
            conn,
            week=week,
            iso_year=iso_year,
            iso_week=iso_week,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        msg = str(exc)
        if "not published" in msg:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=msg)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error generating Weekly Demand Report: {exc}",
        )


@router.get("/operations/capacity-summary", response_model=CapacitySummaryResponse)
def get_capacity_summary_report(
    week: str | None = Query(None, description="ISO Week key e.g. 2017-W32"),
    iso_year: int | None = Query(None, description="ISO Year e.g. 2017"),
    iso_week: int | None = Query(None, description="ISO Week number 1..53"),
    start_date: str | None = Query(None, description="Explicit start date YYYY-MM-DD"),
    end_date: str | None = Query(None, description="Explicit end date YYYY-MM-DD"),
    conn: psycopg.Connection = Depends(get_db),
) -> CapacitySummaryResponse:
    """Return DO-R02 Operations Capacity Summary & Shift Allocation directives.

    Vai trò (Role):
        API endpoint kết xuất Báo cáo tóm tắt công suất vận hành và phân bổ ca làm việc (DO-R02),
        so sánh tải công việc giữa nhóm ngày trong tuần (`Weekday`) và cuối tuần (`Weekend`)
        để đưa ra chỉthị điều phối cho Lễ tân (Front Desk), Buồng phòng (Housekeeping) và Nhà hàng (F&B).

    Input:
        - week (str | None, mặc định=None): Chuỗi tuần chuẩn ISO (ví dụ: `"2017-W32"`).
        - iso_year (int | None, mặc định=None): Năm ISO (ví dụ: `2017`).
        - iso_week (int | None, mặc định=None): Số thứ tự tuần ISO (`1..53`).
        - start_date (str | None, mặc định=None): Ngày bắt đầu tùy chỉnh (`YYYY-MM-DD`).
        - end_date (str | None, mặc định=None): Ngày kết thúc tùy chỉnh (`YYYY-MM-DD`).
        - conn (psycopg.Connection): Kết nối DB chỉ đọc từ `Depends(get_db)`.

    Output:
        - CapacitySummaryResponse: Đối tượng schema chứa thông tin tuần, bảng phân rã theo nhóm
          `Weekday`/`Weekend` (`groups`) và tóm tắt chỉ thị điều phối ca (`capacity_summary`).
    """
    try:
        return ReportingService.get_capacity_summary_report(
            conn,
            week=week,
            iso_year=iso_year,
            iso_week=iso_week,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        msg = str(exc)
        if "not published" in msg:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=msg)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error generating Capacity Summary Report: {exc}",
        )


@router.get("/operations/export.csv")
def export_weekly_report_csv(
    week: str | None = Query(None, description="ISO Week key e.g. 2017-W32"),
    iso_year: int | None = Query(None, description="ISO Year e.g. 2017"),
    iso_week: int | None = Query(None, description="ISO Week number 1..53"),
    start_date: str | None = Query(None, description="Explicit start date YYYY-MM-DD"),
    end_date: str | None = Query(None, description="Explicit end date YYYY-MM-DD"),
    conn: psycopg.Connection = Depends(get_db),
) -> Response:
    """Export DO-R01 Weekly Demand Report as a UTF-8 CSV attachment.

    Vai trò (Role):
        API endpoint xuất dữ liệu Báo cáo nhu cầu hàng tuần (DO-R01) thành tệp đính kèm CSV
        mã hóa UTF-8 (có BOM để hiển thị đúng tiếng Việt trong Microsoft Excel).

    Input:
        - week (str | None, mặc định=None): Chuỗi tuần chuẩn ISO (ví dụ: `"2017-W32"`).
        - iso_year (int | None, mặc định=None): Năm ISO (ví dụ: `2017`).
        - iso_week (int | None, mặc định=None): Số thứ tự tuần ISO (`1..53`).
        - start_date (str | None, mặc định=None): Ngày bắt đầu tùy chỉnh (`YYYY-MM-DD`).
        - end_date (str | None, mặc định=None): Ngày kết thúc tùy chỉnh (`YYYY-MM-DD`).
        - conn (psycopg.Connection): Kết nối DB chỉ đọc từ `Depends(get_db)`.

    Output:
        - Response: Đối tượng FastAPI `Response` mang nội dung CSV (`text/csv; charset=utf-8`)
          kèm header `Content-Disposition: attachment` chứa tên tệp chuẩn `DO-R01_City_Hotel_<week>.csv`.
    """
    try:
        filename, csv_content = ReportingService.generate_weekly_csv(
            conn,
            week=week,
            iso_year=iso_year,
            iso_week=iso_week,
            start_date=start_date,
            end_date=end_date,
        )
        return Response(
            content=csv_content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except ValueError as exc:
        msg = str(exc)
        if "not published" in msg:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=msg)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error exporting CSV: {exc}",
        )
