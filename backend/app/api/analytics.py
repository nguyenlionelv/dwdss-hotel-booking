"""Analytics API endpoints for Operations Mart (DO-A01 to DO-A05)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
import psycopg

from backend.app.api.metadata import get_db
from backend.app.schemas.analytics import ImpactResponse, PivotResponse, TrendResponse
from backend.app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/status")
def analytics_status():
    """Return readiness status for the Analytics module.

    Vai trò (Role):
        API endpoint kiểm tra trạng thái hoạt động của phân hệ phân tích OLAP (Analytics)
        trên Operations Mart.

    Input:
        - Không có tham số đầu vào.

    Output:
        - dict[str, str]: Từ điển JSON gồm tên module (`"analytics"`), trạng thái (`"ready"`)
          và mart mục tiêu (`"Operations Mart"`).
    """
    return {"module": "analytics", "status": "ready", "target_mart": "Operations Mart"}


@router.get("/operations/trend", response_model=TrendResponse)
def get_operations_trend(
    grain: str = Query("month", description="Time grain: day | week | month | quarter | year"),
    start_date: str | None = Query(None, description="Start date YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date YYYY-MM-DD"),
    country_code: str | None = Query(None, description="ISO country code (e.g. PRT, FRA)"),
    country: str | None = Query(None, description="Alias for country_code"),
    day_type: str | None = Query(None, description="Weekday | Weekend | ALL"),
    is_weekend: str | None = Query(None, description="Boolean filter for weekend"),
    is_holiday: str | None = Query(None, description="Boolean or HOLIDAY_ONLY / NON_HOLIDAY filter"),
    conn: psycopg.Connection = Depends(get_db),
) -> TrendResponse:
    """Return multi-grain OLAP demand trend, coverage, and reconciled summary KPIs.

    Vai trò (Role):
        API endpoint truy vấn chuỗi thời gian xu hướng vận hành (OLAP demand trend) theo nhiều mức
        độ mịn thời gian (`day`, `week`, `month`, `quarter`, `year`), kết hợp bộ lọc quốc gia,
        loại ngày trong tuần/cuối tuần và ngày lễ. Trả về chuỗi dữ liệu, độ phủ dữ liệu và các KPI tổng hợp.

    Input:
        - grain (str, mặc định="month"): Độ mịn thời gian (`day` | `week` | `month` | `quarter` | `year`).
        - start_date (str | None, mặc định=None): Ngày bắt đầu lọc (`YYYY-MM-DD`).
        - end_date (str | None, mặc định=None): Ngày kết thúc lọc (`YYYY-MM-DD`).
        - country_code (str | None, mặc định=None): Mã quốc gia ISO 3 ký tự (ví dụ: `PRT`, `FRA`).
        - country (str | None, mặc định=None): Tham số bí danh (alias) dự phòng cho `country_code`.
        - day_type (str | None, mặc định=None): Bộ lọc loại ngày (`Weekday` | `Weekend` | `ALL`).
        - is_weekend (str | None, mặc định=None): Bộ lọc cờ ngày cuối tuần.
        - is_holiday (str | None, mặc định=None): Bộ lọc cờ ngày lễ (`true`/`false`/`HOLIDAY_ONLY`/`NON_HOLIDAY`).
        - conn (psycopg.Connection): Kết nối DB chỉ đọc được tiêm qua `Depends(get_db)`.

    Output:
        - TrendResponse: Đối tượng schema chứa phiên bản dữ liệu, bộ lọc đã áp dụng, thông tin độ phủ
          (`coverage`), các chỉ số tổng hợp (`summary`) và danh sách điểm dữ liệu theo kỳ (`series`).
          Ném `HTTPException(422)` nếu tham số không hợp lệ hoặc `HTTPException(503)` nếu lỗi DB/mart chưa publish.
    """
    eff_country = country_code or country
    try:
        return AnalyticsService.get_operations_trend(
            conn,
            grain=grain,
            start_date=start_date,
            end_date=end_date,
            country_code=eff_country,
            day_type=day_type,
            is_weekend=is_weekend,
            is_holiday=is_holiday,
        )
    except ValueError as exc:
        msg = str(exc)
        if "not published" in msg:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=msg)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error querying Operations Mart trend: {exc}",
        )


@router.get("/operations/pivot", response_model=PivotResponse)
def get_operations_pivot(
    row_dim: str = Query("quarter", description="Row dimension: quarter | month | year"),
    col_dim: str = Query("country", description="Column dimension: country | day_type | is_weekend"),
    measure: str = Query("room_nights", description="Measure name"),
    start_date: str | None = Query(None, description="Start date YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date YYYY-MM-DD"),
    conn: psycopg.Connection = Depends(get_db),
) -> PivotResponse:
    """Return multi-dimensional OLAP pivot matrix.

    Vai trò (Role):
        API endpoint cung cấp bảng chéo đa chiều (OLAP pivot matrix) phục vụ phân tích sâu
        theo chiều hàng (quý/tháng/năm) và chiều cột (quốc gia hoặc loại ngày thường/cuối tuần/ngày lễ)
        trên chỉ số đo lường được chọn.

    Input:
        - row_dim (str, mặc định="quarter"): Chiều dữ liệu theo hàng (`quarter` | `month` | `year`).
        - col_dim (str, mặc định="country"): Chiều dữ liệu theo cột (`country` | `day_type` | `is_weekend`).
        - measure (str, mặc định="room_nights"): Tên độ đo cần tổng hợp (ví dụ: `room_nights`, `arrivals`, `active_guests`).
        - start_date (str | None, mặc định=None): Ngày bắt đầu lọc (`YYYY-MM-DD`).
        - end_date (str | None, mặc định=None): Ngày kết thúc lọc (`YYYY-MM-DD`).
        - conn (psycopg.Connection): Kết nối DB chỉ đọc từ `Depends(get_db)`.

    Output:
        - PivotResponse: Đối tượng schema biểu diễn ma trận pivot gồm danh sách cột, định nghĩa cột,
          các hàng dữ liệu (kèm hàng con `children` có thể mở rộng), tổng theo cột (`column_totals`)
          và tổng toàn cục (`grand_total`).
    """
    try:
        return AnalyticsService.get_operations_pivot(
            conn,
            row_dim=row_dim,
            col_dim=col_dim,
            measure=measure,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        msg = str(exc)
        if "not published" in msg:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=msg)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error querying Operations Mart pivot: {exc}",
        )


@router.get("/operations/impact", response_model=ImpactResponse)
def get_operations_impact(
    start_date: str | None = Query(None, description="Start date YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date YYYY-MM-DD"),
    conn: psycopg.Connection = Depends(get_db),
) -> ImpactResponse:
    """Return Holiday Lift, Weather Temperature Bands, and Top 5 Source Markets.

    Vai trò (Role):
        API endpoint phân tích tác động ngoại cảnh và thị trường lên vận hành khách sạn,
        bao gồm: mức tăng trưởng ngày lễ (Holiday Lift), phân dải thời tiết/nhiệt độ (Weather Bands)
        và Top 5 thị trường quốc gia gửi khách lớn nhất.

    Input:
        - start_date (str | None, mặc định=None): Ngày bắt đầu khoảng phân tích (`YYYY-MM-DD`).
        - end_date (str | None, mặc định=None): Ngày kết thúc khoảng phân tích (`YYYY-MM-DD`).
        - conn (psycopg.Connection): Kết nối DB chỉ đọc từ `Depends(get_db)`.

    Output:
        - ImpactResponse: Đối tượng schema chứa kết quả phân tích `holiday_impact`,
          `weather_impact` và danh sách `top_countries`.
    """
    try:
        return AnalyticsService.get_operations_impact(
            conn,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error querying Operations Mart impact: {exc}",
        )
