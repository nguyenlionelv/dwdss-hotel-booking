"""Business logic service for Operations Mart Reports (API-02 / BI-05: DO-R01 & DO-R02)."""

from __future__ import annotations

import csv
import io
import re
import psycopg

from backend.app.repositories.operations_repository import DAY_NAMES_VI, OperationsRepository
from backend.app.schemas.reports import (
    CapacityGroupBreakdown,
    CapacityShiftSummary,
    CapacitySummaryResponse,
    ReportPeriodInfo,
    WeeklyDailyLogRow,
    WeeklyDemandResponse,
    WeeklyDemandSummary,
)


class ReportingService:
    """Service layer generating reconciled DO-R01 Weekly Demand and DO-R02 Capacity Reports."""

    @staticmethod
    def parse_week_param(
        week: str | None,
        iso_year: int | None,
        iso_week: int | None,
    ) -> tuple[int | None, int | None]:
        """Parse an ISO week string or explicit year/week integers into (iso_year, iso_week).

        Vai trò (Role):
            Phân tích và chuẩn hóa tham số tuần đầu vào từ chuỗi định dạng ISO (ví dụ: `"2017-W32"`
            hoặc `"2017W32"`) hoặc từ cặp số nguyên `(iso_year, iso_week)` thành bộ `(năm, tuần)`.

        Input:
            - week (str | None): Chuỗi mã tuần chuẩn ISO (ví dụ: `"2017-W32"`).
            - iso_year (int | None): Năm ISO dạng số nguyên.
            - iso_week (int | None): Tuần ISO dạng số nguyên (`1..53`).

        Output:
            - tuple[int | None, int | None]: Bộ 2 phần tử `(parsed_iso_year, parsed_iso_week)`.
        """
        if iso_year is not None and iso_week is not None:
            return iso_year, iso_week
        if week:
            match = re.match(r"^(\d{4})-?W(\d{1,2})$", week.strip(), re.IGNORECASE)
            if match:
                return int(match.group(1)), int(match.group(2))
        return iso_year, iso_week

    @staticmethod
    def _weather_status_label(temp: float | None, precip: float | None) -> str:
        """Derive a human-readable weather condition label from temperature and precipitation.

        Vai trò (Role):
            Phân loại trạng thái thời tiết trong ngày thành nhãn mô tả ngắn gọn (`"Rainy"`, `"Clear"`,
            `"Hot Sunny"`, `"Sunny"`, `"Partly Cloudy"`, `"Cool"`) dựa trên lượng mưa và nhiệt độ trung bình.

        Input:
            - temp (float | None): Nhiệt độ trung bình trong ngày (°C).
            - precip (float | None): Tổng lượng mưa trong ngày (mm).

        Output:
            - str: Chuỗi nhãn trạng thái thời tiết phục vụ hiển thị trên báo cáo và xuất CSV.
        """
        if precip is not None and precip >= 2.0:
            return "Rainy"
        if temp is None:
            return "Clear"
        if temp >= 27.0:
            return "Hot Sunny"
        if temp >= 22.0:
            return "Sunny"
        if temp >= 16.0:
            return "Partly Cloudy"
        return "Cool"

    @classmethod
    def get_weekly_demand_report(
        cls,
        conn: psycopg.Connection,
        *,
        week: str | None = None,
        iso_year: int | None = None,
        iso_week: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> WeeklyDemandResponse:
        """Build the reconciled DO-R01 Weekly Demand Report and DO-R02 shift directives.

        Vai trò (Role):
            Tổng hợp và đối soát dữ liệu cho Báo cáo nhu cầu hàng tuần (DO-R01):
            lấy danh sách ngày trong tuần từ `OperationsRepository`, xác định ngày cao điểm (`peak_day`),
            tính toán các chỉ số trung bình có trọng số (ADR, tỷ lệ hủy, quy mô đoàn, số đêm lưu trú, lead time),
            so sánh mức tăng đột biến cuối tuần (`weekend_surge_pct`) và sinh các khuyến nghị điều phối ca (DO-R02).

        Input:
            - conn (psycopg.Connection): Kết nối cơ sở dữ liệu PostgreSQL.
            - week (str | None, mặc định=None): Chuỗi tuần ISO (ví dụ: `"2017-W32"`).
            - iso_year (int | None, mặc định=None): Năm ISO.
            - iso_week (int | None, mặc định=None): Số thứ tự tuần ISO (`1..53`).
            - start_date (str | None, mặc định=None): Ngày bắt đầu tùy chỉnh (`YYYY-MM-DD`).
            - end_date (str | None, mặc định=None): Ngày kết thúc tùy chỉnh (`YYYY-MM-DD`).

        Output:
            - WeeklyDemandResponse: Đối tượng Pydantic chứa toàn bộ dữ liệu báo cáo DO-R01 và tóm tắt DO-R02.
              Ném `ValueError` nếu mart chưa publish hoặc không tìm thấy dữ liệu cho kỳ yêu cầu.
        """
        state = OperationsRepository.get_published_state(conn)
        data_version = str(state["data_version"])
        release_id = f"v{data_version[:8]}"

        parsed_year, parsed_week = cls.parse_week_param(week, iso_year, iso_week)
        raw_rows = OperationsRepository.fetch_weekly_report_rows(
            conn,
            iso_year=parsed_year,
            iso_week=parsed_week,
            start_date=start_date,
            end_date=end_date,
        )
        if not raw_rows:
            raise ValueError("No operations rows found for the requested reporting period.")

        eff_iso_year = int(raw_rows[0]["iso_year"])
        eff_iso_week = int(raw_rows[0]["iso_week"])
        period_start = raw_rows[0]["full_date"].isoformat()
        period_end = raw_rows[-1]["full_date"].isoformat()
        days_count = len(raw_rows)

        # Find peak day by observed_total_guests (tie-break by non_canceled_bookings)
        peak_raw = max(
            raw_rows,
            key=lambda r: (
                int(r["observed_total_guests"] or 0),
                int(r["non_canceled_bookings"] or 0),
            ),
        )
        peak_date_str = peak_raw["full_date"].isoformat()
        peak_guests_val = int(peak_raw["observed_total_guests"] or 0)

        daily_items: list[WeeklyDailyLogRow] = []
        tot_bookings = 0
        tot_arrivals = 0
        tot_cancellations = 0
        tot_adults = 0
        tot_children = 0
        tot_babies = 0
        tot_guests = 0
        tot_room_nights = 0
        sum_adr_num = 0.0
        sum_adr_den = 0
        sum_lt_num = 0
        sum_lt_den = 0
        guest_valid_cnt = 0
        stay_valid_cnt = 0
        holiday_days = 0
        weather_obs_days = 0

        weekday_arr: list[int] = []
        weekend_arr: list[int] = []
        weekday_guests: list[int] = []
        weekend_guests: list[int] = []

        for r in raw_rows:
            fdate = r["full_date"]
            fdate_iso = fdate.isoformat()
            fdate_disp = fdate.strftime("%d/%m/%Y")
            dow_num = int(r["day_of_week"])
            dow_name = DAY_NAMES_VI.get(dow_num, f"Thứ {dow_num}")
            is_wknd = bool(r["is_weekend"])
            day_type_str = "Weekend" if is_wknd else "Weekday"
            is_hol = bool(r["is_holiday"])
            hol_names = list(r["holiday_names"] or [])

            tb = int(r["total_bookings"] or 0)
            arr = int(r["non_canceled_bookings"] or 0)
            canc = int(r["total_cancellations"] or 0)
            adults = int(r["observed_total_adults"] or 0)
            children = int(r["observed_total_children"] or 0)
            babies = int(r["observed_total_babies"] or 0)
            guests = int(r["observed_total_guests"] or 0)
            rn = int(r["observed_total_stay_nights"] or 0)
            adr_val = float(r["avg_adr"]) if r["avg_adr"] is not None else 0.0
            temp_val = float(r["temperature_mean"]) if r["temperature_mean"] is not None else 22.0
            precip_val = float(r["precipitation"]) if r["precipitation"] is not None else 0.0

            tot_bookings += tb
            tot_arrivals += arr
            tot_cancellations += canc
            tot_adults += adults
            tot_children += children
            tot_babies += babies
            tot_guests += guests
            tot_room_nights += rn
            sum_adr_num += float(r["sum_adr"] or 0.0)
            sum_adr_den += int(r["adr_valid_count"] or 0)
            sum_lt_num += int(r["sum_lead_time"] or 0)
            sum_lt_den += int(r["lead_time_valid_count"] or 0)
            guest_valid_cnt += int(r["guest_valid_booking_count"] or 0)
            stay_valid_cnt += int(r["stay_valid_booking_count"] or 0)

            if is_hol:
                holiday_days += 1
            if r["temperature_status"] == "OBSERVED":
                weather_obs_days += 1

            if is_wknd:
                weekend_arr.append(arr)
                weekend_guests.append(guests)
            else:
                weekday_arr.append(arr)
                weekday_guests.append(guests)

            daily_items.append(
                WeeklyDailyLogRow(
                    date_key=int(r["date_key"]),
                    full_date=fdate_iso,
                    day_of_week_num=dow_num,
                    is_weekend=is_wknd,
                    is_holiday=is_hol,
                    holiday_names=hol_names,
                    temperature_mean=float(r["temperature_mean"]) if r["temperature_mean"] is not None else None,
                    precipitation=float(r["precipitation"]) if r["precipitation"] is not None else None,
                    total_bookings=tb,
                    non_canceled_bookings=arr,
                    total_cancellations=canc,
                    cancellation_rate=float(r["cancellation_rate"]) if r["cancellation_rate"] is not None else None,
                    observed_total_adults=adults,
                    observed_total_children=children,
                    observed_total_babies=babies,
                    observed_total_guests=guests,
                    target_guests=int(r["target_guests"]) if r["target_guests"] is not None else None,
                    observed_total_stay_nights=rn,
                    avg_party_size=float(r["avg_party_size"]) if r["avg_party_size"] is not None else None,
                    avg_stay_nights=float(r["avg_stay_nights"]) if r["avg_stay_nights"] is not None else None,
                    avg_lead_time=float(r["avg_lead_time"]) if r["avg_lead_time"] is not None else None,
                    avg_adr=adr_val,
                    guest_data_status=r["guest_data_status"],
                    stay_date=fdate_iso,
                    date_display=fdate_disp,
                    day_of_week=dow_name,
                    day_type=day_type_str,
                    arrivals=arr,
                    departures=max(1, round(arr * 0.92)),
                    active_stays=rn,
                    room_nights=rn,
                    active_guests=guests,
                    adr=adr_val,
                    is_pt_holiday=is_hol,
                    holiday_local_name=hol_names[0] if hol_names else None,
                    weather_temp_mean=round(temp_val, 1),
                    weather_precip_sum=round(precip_val, 1),
                    weather_status=cls._weather_status_label(r["temperature_mean"], r["precipitation"]),
                    is_peak_day=(fdate_iso == peak_date_str),
                )
            )

        all_complete = all(r["guest_data_status"] == "COMPLETE" for r in raw_rows)
        overall_status = "COMPLETE" if all_complete else "PARTIAL"
        avg_daily_guests_float = round(tot_guests / max(1, days_count), 4)
        avg_daily_guests_int = round(tot_guests / max(1, days_count))
        reconciled_adr = round(sum_adr_num / sum_adr_den, 2) if sum_adr_den > 0 else 0.0
        reconciled_canc_rate = round(tot_cancellations / tot_bookings, 6) if tot_bookings > 0 else 0.0
        reconciled_party = round(tot_guests / guest_valid_cnt, 4) if guest_valid_cnt > 0 else None
        reconciled_stay = round(tot_room_nights / stay_valid_cnt, 4) if stay_valid_cnt > 0 else None
        reconciled_lt = round(sum_lt_num / sum_lt_den, 2) if sum_lt_den > 0 else None
        weather_comp = round(weather_obs_days / max(1, days_count), 4)

        wkday_avg_arr = round(sum(weekday_arr) / len(weekday_arr)) if weekday_arr else tot_arrivals
        wkend_avg_arr = round(sum(weekend_arr) / len(weekend_arr)) if weekend_arr else wkday_avg_arr
        wkday_avg_g = round(sum(weekday_guests) / len(weekday_guests)) if weekday_guests else avg_daily_guests_int
        wkend_avg_g = round(sum(weekend_guests) / len(weekend_guests)) if weekend_guests else wkday_avg_g
        surge_val = (
            round(((wkend_avg_arr - wkday_avg_arr) / max(1, wkday_avg_arr)) * 100.0, 1)
            if wkday_avg_arr > 0
            else 0.0
        )
        surge_str = f"{'+' if surge_val >= 0 else ''}{surge_val}%"

        week_key_str = f"{eff_iso_year}-W{eff_iso_week:02d}"
        start_short = raw_rows[0]["full_date"].strftime("%d/%m")
        end_short = raw_rows[-1]["full_date"].strftime("%d/%m")
        week_label_str = f"{eff_iso_year} - Week {eff_iso_week:02d} ({start_short} - {end_short})"

        period_info = ReportPeriodInfo(
            iso_year=eff_iso_year,
            iso_week=eff_iso_week,
            week_key=week_key_str,
            week_label=week_label_str,
            start_date=period_start,
            end_date=period_end,
            calendar_days_count=days_count,
            is_complete_week=(days_count == 7),
            overall_guest_status=overall_status,
            total_arrivals=tot_arrivals,
            total_departures=sum(d.departures for d in daily_items),
            total_room_nights=tot_room_nights,
            avg_daily_active_guests=avg_daily_guests_int,
            peak_day_date=peak_date_str,
            peak_day_guests=peak_guests_val,
            holiday_days_count=holiday_days,
            weather_Completeness_ratio=weather_comp,
        )

        capacity_summary = CapacityShiftSummary(
            report_code="DO-R02",
            weekday_avg_arrivals=wkday_avg_arr,
            weekend_avg_arrivals=wkend_avg_arr,
            weekend_surge_pct=surge_str,
            weekday_avg_guests=wkday_avg_g,
            weekend_avg_guests=wkend_avg_g,
            front_desk_directive=f"Tăng cường quầy Check-in nhanh (Express Desk) vào ngày cao điểm ({peak_date_str}).",
            housekeeping_directive=f"Bố trí ca buồng phòng theo tải {tot_room_nights} đêm phòng/tuần để đảm bảo bàn giao trước 14:00.",
            fb_directive=f"Chuẩn bị định lượng buffet sáng tối đa cho {peak_guests_val} khách vào ngày đỉnh tuần.",
        )

        return WeeklyDemandResponse(
            data_version=data_version,
            dataset_release_id=release_id,
            published_at=state["published_at"],
            period=period_info,
            period_summary=period_info,
            summary=WeeklyDemandSummary(
                total_bookings=tot_bookings,
                non_canceled_bookings=tot_arrivals,
                total_cancellations=tot_cancellations,
                cancellation_rate=reconciled_canc_rate,
                observed_total_adults=tot_adults,
                observed_total_children=tot_children,
                observed_total_babies=tot_babies,
                observed_total_guests=tot_guests,
                target_guests=tot_guests if all_complete else None,
                strict_avg_guests_per_day=avg_daily_guests_float if all_complete else None,
                observed_avg_guests_per_day=avg_daily_guests_float,
                observed_total_stay_nights=tot_room_nights,
                avg_party_size=reconciled_party,
                avg_stay_nights=reconciled_stay,
                avg_lead_time=reconciled_lt,
                avg_adr=reconciled_adr,
                peak_day_date=peak_date_str,
                peak_day_guests=peak_guests_val,
            ),
            daily_rows=daily_items,
            capacity_summary=capacity_summary,
        )

    @classmethod
    def get_capacity_summary_report(
        cls,
        conn: psycopg.Connection,
        *,
        week: str | None = None,
        iso_year: int | None = None,
        iso_week: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> CapacitySummaryResponse:
        """Build the DO-R02 Operations Capacity Summary report grouped by Weekday vs Weekend.

        Vai trò (Role):
            Tạo Báo cáo tóm tắt công suất vận hành (DO-R02) bằng cách tái sử dụng kết quả đã đối soát
            từ `get_weekly_demand_report()`, sau đó phân nhóm các ngày theo `Weekday` và `Weekend`
            để tính tổng và trung bình lượt khách đến, đêm phòng, khách lưu trú và ADR cho từng nhóm.

        Input:
            - conn (psycopg.Connection): Kết nối cơ sở dữ liệu PostgreSQL.
            - week (str | None, mặc định=None): Chuỗi tuần ISO (ví dụ: `"2017-W32"`).
            - iso_year (int | None, mặc định=None): Năm ISO.
            - iso_week (int | None, mặc định=None): Số thứ tự tuần ISO (`1..53`).
            - start_date (str | None, mặc định=None): Ngày bắt đầu tùy chỉnh (`YYYY-MM-DD`).
            - end_date (str | None, mặc định=None): Ngày kết thúc tùy chỉnh (`YYYY-MM-DD`).

        Output:
            - CapacitySummaryResponse: Đối tượng Pydantic chứa thông tin tuần, danh sách nhóm
              `Weekday`/`Weekend` (`groups`) và chỉ thị phân ca (`capacity_summary`).
        """
        weekly = cls.get_weekly_demand_report(
            conn,
            week=week,
            iso_year=iso_year,
            iso_week=iso_week,
            start_date=start_date,
            end_date=end_date,
        )
        groups: list[CapacityGroupBreakdown] = []
        for dtype in ("Weekday", "Weekend"):
            sub = [r for r in weekly.daily_rows if r.day_type == dtype]
            if not sub:
                continue
            cnt = len(sub)
            t_arr = sum(r.arrivals for r in sub)
            t_rn = sum(r.room_nights for r in sub)
            t_g = sum(r.active_guests for r in sub)
            avg_adr = round(sum(r.adr for r in sub) / cnt, 2)
            groups.append(
                CapacityGroupBreakdown(
                    day_type=dtype,
                    days_count=cnt,
                    total_arrivals=t_arr,
                    avg_daily_arrivals=round(t_arr / cnt, 1),
                    total_room_nights=t_rn,
                    avg_daily_room_nights=round(t_rn / cnt, 1),
                    total_active_guests=t_g,
                    avg_daily_active_guests=round(t_g / cnt, 1),
                    avg_adr=avg_adr,
                    avg_party_size=weekly.summary.avg_party_size,
                    avg_stay_nights=weekly.summary.avg_stay_nights,
                )
            )

        return CapacitySummaryResponse(
            data_version=weekly.data_version,
            iso_year=weekly.period.iso_year,
            iso_week=weekly.period.iso_week,
            week_key=weekly.period.week_key,
            groups=groups,
            capacity_summary=weekly.capacity_summary,
        )

    @classmethod
    def generate_weekly_csv(
        cls,
        conn: psycopg.Connection,
        *,
        week: str | None = None,
        iso_year: int | None = None,
        iso_week: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> tuple[str, str]:
        """Return (filename, csv_content_with_utf8_bom).

        Vai trò (Role):
            Kết xuất dữ liệu nhật ký hàng ngày của Báo cáo nhu cầu hàng tuần (DO-R01) sang chuỗi định dạng CSV
            có đính kèm ký tự BOM UTF-8 (`\ufeff`) ở đầu để tương thích hiển thị tiếng Việt trên Excel,
            đồng thời tạo tên tệp chuẩn theo mã tuần.

        Input:
            - conn (psycopg.Connection): Kết nối cơ sở dữ liệu PostgreSQL.
            - week (str | None, mặc định=None): Chuỗi tuần ISO (ví dụ: `"2017-W32"`).
            - iso_year (int | None, mặc định=None): Năm ISO.
            - iso_week (int | None, mặc định=None): Số thứ tự tuần ISO (`1..53`).
            - start_date (str | None, mặc định=None): Ngày bắt đầu tùy chỉnh (`YYYY-MM-DD`).
            - end_date (str | None, mặc định=None): Ngày kết thúc tùy chỉnh (`YYYY-MM-DD`).

        Output:
            - tuple[str, str]: Bộ 2 phần tử gồm:
                1. `filename` (str): Tên tệp CSV (ví dụ: `"DO-R01_City_Hotel_2017-W32.csv"`).
                2. `csv_content` (str): Nội dung tệp CSV đã có UTF-8 BOM.
        """
        report = cls.get_weekly_demand_report(
            conn,
            week=week,
            iso_year=iso_year,
            iso_week=iso_week,
            start_date=start_date,
            end_date=end_date,
        )
        output = io.StringIO()
        output.write("\ufeff")
        writer = csv.writer(output)
        writer.writerow([
            "Stay Date",
            "Day of Week",
            "Day Type",
            "Total Bookings",
            "Arrivals (Non-Canceled)",
            "Cancellations",
            "Room Nights",
            "Active Guests",
            "ADR (EUR)",
            "PT Holiday",
            "Weather Mean Temp (C)",
            "Weather Status",
        ])
        for row in report.daily_rows:
            writer.writerow([
                row.stay_date,
                row.day_of_week,
                row.day_type,
                row.total_bookings,
                row.arrivals,
                row.total_cancellations,
                row.room_nights,
                row.active_guests,
                f"{row.adr:.2f}",
                row.holiday_local_name or ("Holiday" if row.is_pt_holiday else "Normal"),
                row.weather_temp_mean,
                row.weather_status,
            ])

        filename = f"DO-R01_City_Hotel_{report.period.week_key}.csv"
        return filename, output.getvalue()
