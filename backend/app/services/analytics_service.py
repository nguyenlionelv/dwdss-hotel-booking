"""Business logic service for Operations Mart Analytics (API-02 / BI-01)."""

from __future__ import annotations

import psycopg

from backend.app.repositories.operations_repository import OperationsRepository
from backend.app.schemas.analytics import (
    HolidayImpactSummary,
    ImpactResponse,
    PeakDemandDayItem,
    PivotColumnDef,
    PivotResponse,
    PivotRowItem,
    TopCountryImpactItem,
    TrendCoverageSummary,
    TrendFiltersApplied,
    TrendResponse,
    TrendSeriesItem,
    TrendSummary,
    WeatherImpactSummary,
)

VALID_GRAINS = {"day", "week", "month", "quarter", "year"}


class AnalyticsService:
    """Service layer orchestrating OLAP trend, pivot, and impact queries."""

    @staticmethod
    def _parse_bool_filter(val: str | bool | None, *, mode: str = "generic") -> bool | None:
        """Normalize string or boolean query parameters into an optional boolean filter.

        Vai trò (Role):
            Chuẩn hóa giá trị bộ lọc đầu vào từ query string (như `"true"`, `"false"`, `"WEEKEND"`,
            `"WEEKDAY"`, `"HOLIDAY_ONLY"`, `"NON_HOLIDAY"`, `"ALL"`) thành giá trị `bool` (`True`/`False`)
            hoặc `None` (khi không lọc / lấy tất cả).

        Input:
            - val (str | bool | None): Giá trị bộ lọc cần phân tích.
            - mode (str, mặc định="generic"): Chế độ phân tích ngữ nghĩa (`"generic"`, `"day_type"` hoặc `"holiday"`).

        Output:
            - bool | None: Trả về `True`, `False` hoặc `None` nếu không áp dụng bộ lọc.
        """
        if val is None or isinstance(val, bool):
            return val
        norm = str(val).strip().upper()
        if norm in ("ALL", "", "NONE", "NULL"):
            return None
        if mode == "day_type":
            if norm == "WEEKEND":
                return True
            if norm == "WEEKDAY":
                return False
        if mode == "holiday":
            if norm in ("HOLIDAY_ONLY", "TRUE", "1", "HOLIDAY"):
                return True
            if norm in ("NON_HOLIDAY", "FALSE", "0"):
                return False
        if norm in ("TRUE", "1", "YES"):
            return True
        if norm in ("FALSE", "0", "NO"):
            return False
        return None

    @classmethod
    def get_operations_trend(
        cls,
        conn: psycopg.Connection,
        *,
        grain: str = "month",
        start_date: str | None = None,
        end_date: str | None = None,
        country_code: str | None = None,
        day_type: str | None = None,
        is_weekend: bool | str | None = None,
        is_holiday: bool | str | None = None,
    ) -> TrendResponse:
        """Orchestrate multi-grain OLAP demand trend retrieval and KPI reconciliation.

        Vai trò (Role):
            Xử lý nghiệp vụ phân tích xu hướng vận hành (OLAP Trend): kiểm tra trạng thái publish của mart,
            chuẩn hóa các tham số bộ lọc và `grain`, gọi `OperationsRepository.fetch_trend_rows()`,
            đối soát chất lượng dữ liệu (`COMPLETE` vs `PARTIAL` cho các trường `target_guests` / `strict_avg_guests_per_day`),
            xác định kỳ cao điểm (`is_peak`) và đóng gói kết quả vào schema `TrendResponse`.

        Input:
            - conn (psycopg.Connection): Kết nối cơ sở dữ liệu PostgreSQL.
            - grain (str, mặc định="month"): Độ mịn thời gian (`day` | `week` | `month` | `quarter` | `year`).
            - start_date (str | None, mặc định=None): Ngày bắt đầu (`YYYY-MM-DD`); mặc định lấy `actual_start` của mart.
            - end_date (str | None, mặc định=None): Ngày kết thúc (`YYYY-MM-DD`); mặc định lấy `actual_end` của mart.
            - country_code (str | None, mặc định=None): Mã quốc gia ISO cần lọc.
            - day_type (str | None, mặc định=None): Loại ngày (`Weekday` | `Weekend` | `ALL`).
            - is_weekend (bool | str | None, mặc định=None): Bộ lọc ngày cuối tuần.
            - is_holiday (bool | str | None, mặc định=None): Bộ lọc ngày lễ.

        Output:
            - TrendResponse: Đối tượng Pydantic chứa `data_version`, `grain`, `filters_applied`,
              `coverage`, `summary` và danh sách chuỗi thời gian `series`.
              Ném `ValueError` nếu `grain` không hợp lệ hoặc mart chưa được publish.
        """
        state = OperationsRepository.get_published_state(conn)
        data_version = str(state["data_version"])
        eff_start = start_date or state["actual_start"].isoformat()
        eff_end = end_date or state["actual_end"].isoformat()

        norm_grain = grain.lower().strip() if grain else "month"
        if norm_grain not in VALID_GRAINS:
            raise ValueError(f"Unsupported grain '{grain}'. Must be one of {sorted(VALID_GRAINS)}.")

        eff_weekend = cls._parse_bool_filter(is_weekend)
        if eff_weekend is None and day_type:
            eff_weekend = cls._parse_bool_filter(day_type, mode="day_type")

        eff_holiday = cls._parse_bool_filter(is_holiday, mode="holiday")
        eff_country = (
            country_code.upper().strip()
            if country_code and country_code.upper().strip() != "ALL"
            else None
        )

        series_rows, summary_row, peak_days = OperationsRepository.fetch_trend_rows(
            conn,
            grain=norm_grain,
            start_date=eff_start,
            end_date=eff_end,
            country_code=eff_country,
            is_weekend=eff_weekend,
            is_holiday=eff_holiday,
        )

        max_rn = max((int(r["observed_total_stay_nights"] or 0) for r in series_rows), default=0)
        peak_period_label = (
            next(
                (r["period_label"] for r in series_rows if int(r["observed_total_stay_nights"] or 0) == max_rn),
                series_rows[0]["period_label"] if series_rows else eff_start[:7],
            )
            if series_rows
            else eff_start[:7]
        )

        series_items: list[TrendSeriesItem] = []
        for r in series_rows:
            rn = int(r["observed_total_stay_nights"] or 0)
            guests = int(r["observed_total_guests"] or 0)
            arr = int(r["non_canceled_bookings"] or 0)
            adr_val = float(r["avg_adr"]) if r["avg_adr"] is not None else 0.0
            avg_g_day = (
                float(r["observed_avg_guests_per_day"])
                if r["observed_avg_guests_per_day"] is not None
                else 0.0
            )
            is_complete = r["guest_data_status"] == "COMPLETE"

            series_items.append(
                TrendSeriesItem(
                    period_key=r["period_key"],
                    period_label=r["period_label"],
                    period_start=r["period_start"],
                    period_end=r["period_end"],
                    calendar_days_count=int(r["calendar_days_count"] or 0),
                    guest_data_status=r["guest_data_status"],
                    total_bookings=int(r["total_bookings"] or 0),
                    non_canceled_bookings=arr,
                    total_cancellations=int(r["total_cancellations"] or 0),
                    cancellation_rate=float(r["cancellation_rate"]) if r["cancellation_rate"] is not None else None,
                    observed_total_guests=guests,
                    target_guests=guests if is_complete else None,
                    strict_avg_guests_per_day=avg_g_day if is_complete else None,
                    observed_avg_guests_per_day=avg_g_day,
                    observed_total_stay_nights=rn,
                    avg_party_size=float(r["avg_party_size"]) if r["avg_party_size"] is not None else None,
                    avg_stay_nights=float(r["avg_stay_nights"]) if r["avg_stay_nights"] is not None else None,
                    avg_lead_time=float(r["avg_lead_time"]) if r["avg_lead_time"] is not None else None,
                    avg_adr=adr_val if r["avg_adr"] is not None else None,
                    arrivals=arr,
                    room_nights=rn,
                    active_guests=guests,
                    adr=adr_val,
                    is_holiday_period=bool(r.get("is_holiday_period")),
                    is_peak=(rn == max_rn and max_rn > 0),
                )
            )

        overall_complete = summary_row.get("overall_guest_status") == "COMPLETE"
        tot_guests = int(summary_row.get("observed_total_guests") or 0)
        tot_rn = int(summary_row.get("observed_total_stay_nights") or 0)
        tot_arr = int(summary_row.get("non_canceled_bookings") or 0)
        obs_avg_g = (
            float(summary_row["observed_avg_guests_per_day"])
            if summary_row.get("observed_avg_guests_per_day") is not None
            else 0.0
        )

        return TrendResponse(
            data_version=data_version,
            grain=norm_grain,
            filters_applied=TrendFiltersApplied(
                start_date=eff_start,
                end_date=eff_end,
                grain=norm_grain,
                country_code=eff_country,
                day_type=day_type,
                is_weekend=eff_weekend,
                is_holiday=eff_holiday,
            ),
            coverage=TrendCoverageSummary(
                calendar_days_count=int(summary_row.get("calendar_days_count") or 0),
                booking_complete_days=int(summary_row.get("booking_complete_days") or 0),
                guest_complete_days=int(summary_row.get("guest_complete_days") or 0),
                guest_partial_days=int(summary_row.get("guest_partial_days") or 0),
                overall_guest_status=summary_row.get("overall_guest_status") or "MISSING",
                rejected_booking_count=int(summary_row.get("rejected_booking_count") or 0),
                guest_ineligible_booking_count=int(summary_row.get("guest_ineligible_booking_count") or 0),
            ),
            summary=TrendSummary(
                total_bookings=int(summary_row.get("total_bookings") or 0),
                non_canceled_bookings=tot_arr,
                total_cancellations=int(summary_row.get("total_cancellations") or 0),
                cancellation_rate=float(summary_row["cancellation_rate"])
                if summary_row.get("cancellation_rate") is not None
                else None,
                observed_total_adults=int(summary_row.get("observed_total_adults") or 0),
                observed_total_children=int(summary_row.get("observed_total_children") or 0),
                observed_total_babies=int(summary_row.get("observed_total_babies") or 0),
                observed_total_guests=tot_guests,
                target_guests=tot_guests if overall_complete else None,
                strict_avg_guests_per_day=obs_avg_g if overall_complete else None,
                observed_avg_guests_per_day=obs_avg_g,
                observed_total_stay_nights=tot_rn,
                avg_party_size=float(summary_row["avg_party_size"])
                if summary_row.get("avg_party_size") is not None
                else None,
                avg_stay_nights=float(summary_row["avg_stay_nights"])
                if summary_row.get("avg_stay_nights") is not None
                else None,
                avg_lead_time=float(summary_row["avg_lead_time"])
                if summary_row.get("avg_lead_time") is not None
                else None,
                avg_adr=float(summary_row["avg_adr"]) if summary_row.get("avg_adr") is not None else 0.0,
                peak_demand_days=[PeakDemandDayItem(**p) for p in peak_days],
                total_arrivals=tot_arr,
                total_room_nights=tot_rn,
                avg_daily_active_guests=round(obs_avg_g),
                peak_period=peak_period_label,
                peak_room_nights=max_rn,
            ),
            series=series_items,
        )

    @classmethod
    def get_operations_pivot(
        cls,
        conn: psycopg.Connection,
        *,
        row_dim: str = "quarter",
        col_dim: str = "country",
        measure: str = "room_nights",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> PivotResponse:
        """Orchestrate multi-dimensional OLAP pivot table generation.

        Vai trò (Role):
            Điều phối nghiệp vụ tạo bảng xoay đa chiều (OLAP Pivot): xác thực trạng thái mart,
            thiết lập khoảng thời gian mặc định nếu thiếu, gọi `OperationsRepository.fetch_pivot_data()`
            và chuyển đổi dữ liệu thô sang đối tượng phản hồi `PivotResponse`.

        Input:
            - conn (psycopg.Connection): Kết nối cơ sở dữ liệu PostgreSQL.
            - row_dim (str, mặc định="quarter"): Chiều dữ liệu theo hàng (`quarter` | `month` | `year`).
            - col_dim (str, mặc định="country"): Chiều dữ liệu theo cột (`country` | `day_type` | `is_weekend`).
            - measure (str, mặc định="room_nights"): Độ đo cần tổng hợp (`room_nights`, `arrivals`, `active_guests`,...).
            - start_date (str | None, mặc định=None): Ngày bắt đầu lọc (`YYYY-MM-DD`).
            - end_date (str | None, mặc định=None): Ngày kết thúc lọc (`YYYY-MM-DD`).

        Output:
            - PivotResponse: Đối tượng Pydantic chứa cấu trúc ma trận pivot hoàn chỉnh kèm tổng cột và tổng chung.
        """
        state = OperationsRepository.get_published_state(conn)
        data_version = str(state["data_version"])
        eff_start = start_date or state["actual_start"].isoformat()
        eff_end = end_date or state["actual_end"].isoformat()

        matrix = OperationsRepository.fetch_pivot_data(
            conn,
            row_dim=row_dim,
            col_dim=col_dim,
            measure=measure,
            start_date=eff_start,
            end_date=eff_end,
        )

        return PivotResponse(
            data_version=data_version,
            row_dim=row_dim,
            col_dim=col_dim,
            measure=measure,
            columns=matrix["columns"],
            column_defs=[PivotColumnDef(**cd) for cd in matrix["column_defs"]],
            rows=[PivotRowItem(**r) for r in matrix["rows"]],
            column_totals=matrix["column_totals"],
            grand_total=matrix["grand_total"],
        )

    @classmethod
    def get_operations_impact(
        cls,
        conn: psycopg.Connection,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> ImpactResponse:
        """Orchestrate Holiday Lift, Weather Band, and Top Source Market impact analysis.

        Vai trò (Role):
            Điều phối nghiệp vụ phân tích tác động ngoại cảnh (Impact Analysis): kiểm tra trạng thái mart,
            xác định khoảng ngày hiệu lực, gọi `OperationsRepository.fetch_impact_data()` và ánh xạ kết quả
            sang các schema `HolidayImpactSummary`, `WeatherImpactSummary` và `TopCountryImpactItem`.

        Input:
            - conn (psycopg.Connection): Kết nối cơ sở dữ liệu PostgreSQL.
            - start_date (str | None, mặc định=None): Ngày bắt đầu (`YYYY-MM-DD`); mặc định lấy đầu kỳ mart.
            - end_date (str | None, mặc định=None): Ngày kết thúc (`YYYY-MM-DD`); mặc định lấy cuối kỳ mart.

        Output:
            - ImpactResponse: Đối tượng Pydantic chứa `data_version`, `holiday_impact`,
              `weather_impact` và `top_countries`.
        """
        state = OperationsRepository.get_published_state(conn)
        data_version = str(state["data_version"])
        eff_start = start_date or state["actual_start"].isoformat()
        eff_end = end_date or state["actual_end"].isoformat()

        raw = OperationsRepository.fetch_impact_data(
            conn,
            start_date=eff_start,
            end_date=eff_end,
        )

        return ImpactResponse(
            data_version=data_version,
            holiday_impact=HolidayImpactSummary(**raw["holiday_impact"]),
            weather_impact=WeatherImpactSummary(**raw["weather_impact"]),
            top_countries=[TopCountryImpactItem(**c) for c in raw["top_countries"]],
        )
