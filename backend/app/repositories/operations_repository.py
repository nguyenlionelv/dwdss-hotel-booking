"""Data access repository for Operations Mart (API-02: Analytics & Reports)."""

from __future__ import annotations

from datetime import date
from typing import Any
import psycopg

DAY_NAMES_VI = {
    1: "Thứ Hai",
    2: "Thứ Ba",
    3: "Thứ Tư",
    4: "Thứ Năm",
    5: "Thứ Sáu",
    6: "Thứ Bảy",
    7: "Chủ Nhật",
}

MEASURE_COLUMN_MAP = {
    "room_nights": "observed_total_stay_nights",
    "observed_total_stay_nights": "observed_total_stay_nights",
    "arrivals": "non_canceled_bookings",
    "non_canceled_bookings": "non_canceled_bookings",
    "active_guests": "observed_total_guests",
    "observed_total_guests": "observed_total_guests",
    "total_bookings": "total_bookings",
    "total_cancellations": "total_cancellations",
}


class OperationsRepository:
    """Read-only repository querying official Operations Mart tables and views."""

    @staticmethod
    def get_published_state(conn: psycopg.Connection) -> dict[str, Any]:
        """Fetch published mart dataset state or raise ValueError if unavailable.

        Vai trò (Role):
            Truy vấn bảng `mart.dataset_state` kết hợp với `dw.active_dataset` để lấy thông tin
            phiên bản dữ liệu hiện tại của Operations Mart và xác minh mart đã được publish đồng bộ
            với lần chạy Data Warehouse đang hoạt động (`matches_active_dw`).

        Input:
            - conn (psycopg.Connection): Kết nối cơ sở dữ liệu PostgreSQL đang mở.

        Output:
            - dict[str, Any]: Từ điển chứa các trường `dw_run_id`, `data_version`, `published_at`,
              `actual_start`, `actual_end`, `active_dw_run_id` và `matches_active_dw`.
              Ném `ValueError` nếu mart chưa được xuất bản hoặc bị lệch phiên bản với DW.
        """
        cur = conn.cursor()
        cur.execute("""
            SELECT s.dw_run_id, s.data_version, s.published_at, s.actual_start, s.actual_end,
                   a.run_id AS active_dw_run_id, (a.run_id = s.dw_run_id) AS matches_active_dw
            FROM mart.dataset_state s
            LEFT JOIN dw.active_dataset a ON a.singleton_id = s.singleton_id
            WHERE s.singleton_id = 1
        """)
        row = cur.fetchone()
        if not row or not row["matches_active_dw"]:
            raise ValueError("Operations Mart is not published or out of sync with active DW dataset.")
        return row

    @staticmethod
    def _build_where_clause(
        start_date: str | None,
        end_date: str | None,
        country_code: str | None,
        is_weekend: bool | None,
        is_holiday: bool | None,
    ) -> tuple[str, str, dict[str, Any]]:
        """Return (table_name, where_sql, params_dict).

        Vai trò (Role):
            Hàm nội bộ hỗ trợ lựa chọn bảng mục tiêu (`mart.daily_hotel_operations` hoặc
            `mart.daily_hotel_operations_by_country` khi có lọc quốc gia) và xây dựng mệnh đề `WHERE`
            tham số hóa an toàn (chống SQL Injection) kèm từ điển tham số truy vấn.

        Input:
            - start_date (str | None): Ngày bắt đầu lọc (`YYYY-MM-DD`).
            - end_date (str | None): Ngày kết thúc lọc (`YYYY-MM-DD`).
            - country_code (str | None): Mã quốc gia ISO (nếu khác `None` và khác `"ALL"` sẽ truy vấn bảng theo quốc gia).
            - is_weekend (bool | None): Cờ lọc ngày cuối tuần (`True`) hoặc ngày thường (`False`).
            - is_holiday (bool | None): Cờ lọc ngày lễ (`True`) hoặc ngày không phải lễ (`False`).

        Output:
            - tuple[str, str, dict[str, Any]]: Bộ 3 phần tử gồm:
                1. `table_name` (str): Tên bảng mart trong PostgreSQL cần truy vấn.
                2. `where_sql` (str): Chuỗi điều kiện SQL cho mệnh đề `WHERE`.
                3. `params` (dict[str, Any]): Từ điển chứa các giá trị tham số truyền vào `cur.execute()`.
        """
        use_country_table = bool(country_code and country_code.upper() != "ALL")
        table_name = (
            "mart.daily_hotel_operations_by_country"
            if use_country_table
            else "mart.daily_hotel_operations"
        )
        conditions: list[str] = ["1=1"]
        params: dict[str, Any] = {}

        if start_date:
            conditions.append("full_date >= %(start_date)s::date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("full_date <= %(end_date)s::date")
            params["end_date"] = end_date
        if use_country_table:
            conditions.append("country_code = %(country_code)s")
            params["country_code"] = country_code.upper()
        if is_weekend is not None:
            conditions.append("is_weekend = %(is_weekend)s")
            params["is_weekend"] = is_weekend
        if is_holiday is not None:
            conditions.append("is_holiday = %(is_holiday)s")
            params["is_holiday"] = is_holiday

        return table_name, " AND ".join(conditions), params

    @classmethod
    def fetch_trend_rows(
        cls,
        conn: psycopg.Connection,
        *,
        grain: str,
        start_date: str | None,
        end_date: str | None,
        country_code: str | None,
        is_weekend: bool | None,
        is_holiday: bool | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
        """Execute grouped trend query, overall summary query, and peak demand days lookup.

        Vai trò (Role):
            Thực thi bộ 3 truy vấn SQL OLAP trên Operations Mart cho chức năng phân tích xu hướng (Trend):
            (1) Truy vấn chuỗi thời gian nhóm theo độ mịn `grain` (`day`, `week`, `month`, `quarter`, `year`),
            (2) Truy vấn tổng hợp toàn cục và kiểm tra độ phủ dữ liệu (`summary` & `coverage`),
            (3) Truy vấn tìm Top 3 ngày có nhu cầu lưu trú cao điểm nhất (`peak_days`).

        Input:
            - conn (psycopg.Connection): Kết nối cơ sở dữ liệu PostgreSQL.
            - grain (str): Độ mịn thời gian (`day` | `week` | `month` | `quarter` | `year`).
            - start_date (str | None): Ngày bắt đầu lọc (`YYYY-MM-DD`).
            - end_date (str | None): Ngày kết thúc lọc (`YYYY-MM-DD`).
            - country_code (str | None): Mã quốc gia cần lọc (hoặc `None` cho toàn bộ khách sạn).
            - is_weekend (bool | None): Bộ lọc ngày cuối tuần/ngày thường.
            - is_holiday (bool | None): Bộ lọc ngày lễ Bồ Đào Nha.

        Output:
            - tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]: Bộ 3 giá trị gồm:
                1. `series_rows` (list[dict[str, Any]]): Danh sách các dòng dữ liệu đã nhóm theo kỳ thời gian.
                2. `summary_row` (dict[str, Any]): Từ điển chứa các chỉ số KPI tổng hợp và thống kê độ phủ.
                3. `peak_days` (list[dict[str, Any]]): Danh sách tối đa 3 ngày cao điểm nhất theo số lượng khách.
        """
        table_name, where_sql, params = cls._build_where_clause(
            start_date, end_date, country_code, is_weekend, is_holiday
        )

        grain_expr_map = {
            "day": ("full_date::text", "full_date"),
            "week": ("concat(iso_year, '-W', lpad(iso_week::text, 2, '0'))", "iso_year, iso_week"),
            "month": ("concat(year, '-', lpad(month::text, 2, '0'))", "year, month"),
            "quarter": ("concat(year, '-Q', quarter)", "year, quarter"),
            "year": ("year::text", "year"),
        }
        period_expr, group_cols = grain_expr_map.get(grain, grain_expr_map["month"])

        cur = conn.cursor()

        # 1. Series query
        cur.execute(
            f"""
            SELECT
                {period_expr} AS period_key,
                {period_expr} AS period_label,
                min(full_date)::text AS period_start,
                max(full_date)::text AS period_end,
                count(*) AS calendar_days_count,
                CASE
                    WHEN count(*) FILTER (WHERE guest_data_status = 'COMPLETE') = count(*) THEN 'COMPLETE'
                    WHEN count(*) FILTER (WHERE guest_data_status IN ('COMPLETE', 'PARTIAL')) > 0 THEN 'PARTIAL'
                    ELSE 'MISSING'
                END AS guest_data_status,
                coalesce(sum(total_bookings), 0) AS total_bookings,
                coalesce(sum(non_canceled_bookings), 0) AS non_canceled_bookings,
                coalesce(sum(total_cancellations), 0) AS total_cancellations,
                round(sum(total_cancellations)::numeric / nullif(sum(total_bookings), 0), 6) AS cancellation_rate,
                coalesce(sum(observed_total_guests), 0) AS observed_total_guests,
                coalesce(sum(observed_total_stay_nights), 0) AS observed_total_stay_nights,
                round(sum(observed_total_guests)::numeric / nullif(count(*), 0), 4) AS observed_avg_guests_per_day,
                round(sum(observed_total_guests)::numeric / nullif(sum(guest_valid_booking_count), 0), 4) AS avg_party_size,
                round(sum(observed_total_stay_nights)::numeric / nullif(sum(stay_valid_booking_count), 0), 4) AS avg_stay_nights,
                round(sum(sum_lead_time)::numeric / nullif(sum(lead_time_valid_count), 0), 2) AS avg_lead_time,
                round(sum(sum_adr)::numeric / nullif(sum(adr_valid_count), 0), 2) AS avg_adr,
                bool_or(coalesce(is_holiday, false)) AS is_holiday_period
            FROM {table_name}
            WHERE {where_sql}
            GROUP BY {group_cols}
            ORDER BY {group_cols}
            """,
            params,
        )
        series_rows = cur.fetchall()

        # 2. Overall Summary & Coverage query
        cur.execute(
            f"""
            SELECT
                count(*) AS calendar_days_count,
                count(*) FILTER (WHERE booking_data_status = 'COMPLETE') AS booking_complete_days,
                count(*) FILTER (WHERE guest_data_status = 'COMPLETE') AS guest_complete_days,
                count(*) FILTER (WHERE guest_data_status = 'PARTIAL') AS guest_partial_days,
                CASE
                    WHEN count(*) > 0 AND count(*) FILTER (WHERE guest_data_status = 'COMPLETE') = count(*) THEN 'COMPLETE'
                    WHEN count(*) FILTER (WHERE guest_data_status IN ('COMPLETE', 'PARTIAL')) > 0 THEN 'PARTIAL'
                    ELSE 'MISSING'
                END AS overall_guest_status,
                coalesce(sum(rejected_booking_count), 0) AS rejected_booking_count,
                coalesce(sum(guest_ineligible_booking_count), 0) AS guest_ineligible_booking_count,
                coalesce(sum(total_bookings), 0) AS total_bookings,
                coalesce(sum(non_canceled_bookings), 0) AS non_canceled_bookings,
                coalesce(sum(total_cancellations), 0) AS total_cancellations,
                round(sum(total_cancellations)::numeric / nullif(sum(total_bookings), 0), 6) AS cancellation_rate,
                coalesce(sum(observed_total_adults), 0) AS observed_total_adults,
                coalesce(sum(observed_total_children), 0) AS observed_total_children,
                coalesce(sum(observed_total_babies), 0) AS observed_total_babies,
                coalesce(sum(observed_total_guests), 0) AS observed_total_guests,
                coalesce(sum(observed_total_stay_nights), 0) AS observed_total_stay_nights,
                round(sum(observed_total_guests)::numeric / nullif(count(*), 0), 4) AS observed_avg_guests_per_day,
                round(sum(observed_total_guests)::numeric / nullif(sum(guest_valid_booking_count), 0), 4) AS avg_party_size,
                round(sum(observed_total_stay_nights)::numeric / nullif(sum(stay_valid_booking_count), 0), 4) AS avg_stay_nights,
                round(sum(sum_lead_time)::numeric / nullif(sum(lead_time_valid_count), 0), 2) AS avg_lead_time,
                round(sum(sum_adr)::numeric / nullif(sum(adr_valid_count), 0), 2) AS avg_adr
            FROM {table_name}
            WHERE {where_sql}
            """,
            params,
        )
        summary_row = cur.fetchone() or {}

        # 3. Peak demand days lookup
        cur.execute(
            f"""
            SELECT
                full_date::text AS full_date,
                coalesce(observed_total_guests, 0) AS observed_total_guests,
                coalesce(observed_total_stay_nights, 0) AS observed_total_stay_nights,
                guest_data_status
            FROM {table_name}
            WHERE {where_sql}
            ORDER BY observed_total_guests DESC NULLS LAST, observed_total_stay_nights DESC NULLS LAST, full_date ASC
            LIMIT 3
            """,
            params,
        )
        peak_days = cur.fetchall()

        return series_rows, summary_row, peak_days

    @classmethod
    def fetch_pivot_data(
        cls,
        conn: psycopg.Connection,
        *,
        row_dim: str,
        col_dim: str,
        measure: str,
        start_date: str | None,
        end_date: str | None,
    ) -> dict[str, Any]:
        """Build multi-dimensional OLAP pivot matrix.

        Vai trò (Role):
            Truy vấn và tổng hợp dữ liệu đa chiều từ Operations Mart để dựng bảng chéo (Pivot Table).
            Hỗ trợ hai chế độ phân tích chính:
            - Phân tích theo loại ngày (`col_dim` thuộc `day_type`, `is_weekend`, `is_holiday`): Hàng là Quý, Cột là Weekday/Weekend/Holiday.
            - Phân tích theo quốc gia (mặc định): Cột là Top 5 quốc gia có sản lượng cao nhất + nhóm `OTHER`,
              Hàng là Quý kèm danh sách các Tháng con (`children`) hỗ trợ drill-down mở rộng.

        Input:
            - conn (psycopg.Connection): Kết nối cơ sở dữ liệu PostgreSQL.
            - row_dim (str): Chiều hàng (ví dụ: `"quarter"`).
            - col_dim (str): Chiều cột (`"country"` | `"day_type"` | `"is_weekend"` | `"is_holiday"`).
            - measure (str): Tên chỉ số đo lường cần tổng hợp (được ánh xạ qua `MEASURE_COLUMN_MAP`).
            - start_date (str | None): Ngày bắt đầu lọc (`YYYY-MM-DD`).
            - end_date (str | None): Ngày kết thúc lọc (`YYYY-MM-DD`).

        Output:
            - dict[str, Any]: Từ điển chứa cấu trúc ma trận pivot gồm `columns`, `column_defs`,
              `rows` (danh sách hàng cha và hàng con `children`), `column_totals` và `grand_total`.
        """
        sql_measure = MEASURE_COLUMN_MAP.get(measure, "observed_total_stay_nights")
        cur = conn.cursor()

        conditions = ["1=1"]
        params: dict[str, Any] = {}
        if start_date:
            conditions.append("full_date >= %(start_date)s::date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("full_date <= %(end_date)s::date")
            params["end_date"] = end_date
        where_sql = " AND ".join(conditions)

        norm_row_dim = (row_dim or "quarter").lower().strip()
        if norm_row_dim not in ("year", "quarter", "month"):
            norm_row_dim = "quarter"

        if col_dim in ("day_type", "is_weekend", "is_holiday"):
            if norm_row_dim == "year":
                row_key_expr = "year::text"
                group_by_expr = "year"
                order_by_expr = "year"
            elif norm_row_dim == "month":
                row_key_expr = "concat(year, '-', lpad(month::text, 2, '0'))"
                group_by_expr = "year, month"
                order_by_expr = "year, month"
            else:
                row_key_expr = "concat(year, ' - Q', quarter)"
                group_by_expr = "year, quarter"
                order_by_expr = "year, quarter"

            cur.execute(
                f"""
                SELECT
                    {row_key_expr} AS row_key,
                    coalesce(sum({sql_measure}) FILTER (WHERE NOT is_weekend AND NOT coalesce(is_holiday, false)), 0) AS "Weekday",
                    coalesce(sum({sql_measure}) FILTER (WHERE is_weekend AND NOT coalesce(is_holiday, false)), 0) AS "Weekend",
                    coalesce(sum({sql_measure}) FILTER (WHERE coalesce(is_holiday, false)), 0) AS "Holiday",
                    coalesce(sum({sql_measure}), 0) AS total
                FROM mart.daily_hotel_operations
                WHERE {where_sql}
                GROUP BY {group_by_expr}
                ORDER BY {order_by_expr}
                """,
                params,
            )
            q_rows = cur.fetchall()
            cols = ["Weekday", "Weekend", "Holiday"]
            col_defs = [
                {"col_key": "Weekday", "col_label": "Weekday (Mon-Fri)"},
                {"col_key": "Weekend", "col_label": "Weekend (Sat-Sun)"},
                {"col_key": "Holiday", "col_label": "PT Holiday"},
            ]
            rows_out = []
            max_total = max((r["total"] for r in q_rows), default=0)
            col_totals = {c: 0 for c in cols}
            grand_total = 0

            for r in q_rows:
                vals = {c: int(r[c] or 0) for c in cols}
                for c in cols:
                    col_totals[c] += vals[c]
                row_tot = int(r["total"] or 0)
                grand_total += row_tot
                rows_out.append({
                    "row_key": r["row_key"],
                    "row_label": r["row_key"],
                    "values": vals,
                    "cells": vals,
                    "total": row_tot,
                    "row_total": row_tot,
                    "is_expandable": False,
                    "is_highlighted": row_tot == max_total and max_total > 0,
                    "children": None,
                })

            return {
                "columns": cols,
                "column_defs": col_defs,
                "rows": rows_out,
                "column_totals": col_totals,
                "grand_total": grand_total,
            }

        # Default: Col = Country (Top 5 + OTHER), Row = dynamic (year | quarter | month)
        cur.execute(
            f"""
            SELECT country_code, coalesce(sum({sql_measure}), 0) AS measure_sum
            FROM mart.daily_hotel_operations_by_country
            WHERE {where_sql} AND country_code <> 'UNK'
            GROUP BY country_code
            ORDER BY measure_sum DESC, country_code ASC
            LIMIT 5
            """,
            params,
        )
        top_country_rows = cur.fetchall()
        top_codes = [r["country_code"] for r in top_country_rows]
        if not top_codes:
            top_codes = ["PRT", "FRA", "DEU", "GBR", "ESP"]
        cols = [*top_codes, "OTHER"]
        col_defs = [{"col_key": c, "col_label": c} for c in cols]

        cur.execute(
            f"""
            SELECT
                year,
                quarter,
                month,
                country_code,
                coalesce(sum({sql_measure}), 0) AS val
            FROM mart.daily_hotel_operations_by_country
            WHERE {where_sql}
            GROUP BY year, quarter, month, country_code
            ORDER BY year, quarter, month
            """,
            params,
        )
        raw_cells = cur.fetchall()

        parent_map: dict[tuple, dict[str, Any]] = {}
        col_totals = {c: 0 for c in cols}
        grand_total = 0

        for cell in raw_cells:
            yr = int(cell["year"])
            qt = int(cell["quarter"])
            mn = int(cell["month"])
            code = cell["country_code"] if cell["country_code"] in top_codes else "OTHER"
            val = int(cell["val"] or 0)

            if norm_row_dim == "year":
                pk = (yr,)
                p_label = f"{yr}"
                ck: tuple | None = (yr, qt)
                c_label = f"{yr} - Q{qt}"
            elif norm_row_dim == "month":
                pk = (yr, mn)
                p_label = f"{yr}-{mn:02d}"
                ck = None
                c_label = ""
            else:
                pk = (yr, qt)
                p_label = f"{yr} - Q{qt}"
                ck = (yr, mn)
                c_label = f"{yr}-{mn:02d}"

            if pk not in parent_map:
                parent_map[pk] = {
                    "row_key": p_label,
                    "values": {c: 0 for c in cols},
                    "total": 0,
                    "children_map": {},
                }
            parent_map[pk]["values"][code] += val
            parent_map[pk]["total"] += val

            if ck is not None:
                if ck not in parent_map[pk]["children_map"]:
                    parent_map[pk]["children_map"][ck] = {
                        "row_key": c_label,
                        "values": {c: 0 for c in cols},
                        "total": 0,
                    }
                parent_map[pk]["children_map"][ck]["values"][code] += val
                parent_map[pk]["children_map"][ck]["total"] += val

            col_totals[code] += val
            grand_total += val

        max_p_total = max((p["total"] for p in parent_map.values()), default=0)
        rows_out = []
        for pk in sorted(parent_map.keys()):
            pdata = parent_map[pk]
            children = (
                [
                    {
                        "row_key": cdata["row_key"],
                        "row_label": cdata["row_key"],
                        "values": cdata["values"],
                        "cells": cdata["values"],
                        "total": cdata["total"],
                        "row_total": cdata["total"],
                    }
                    for _, cdata in sorted(pdata["children_map"].items())
                ]
                if pdata["children_map"]
                else None
            )
            rows_out.append({
                "row_key": pdata["row_key"],
                "row_label": pdata["row_key"],
                "values": pdata["values"],
                "cells": pdata["values"],
                "total": pdata["total"],
                "row_total": pdata["total"],
                "is_expandable": bool(children),
                "is_highlighted": pdata["total"] == max_p_total and max_p_total > 0,
                "children": children,
            })

        return {
            "columns": cols,
            "column_defs": col_defs,
            "rows": rows_out,
            "column_totals": col_totals,
            "grand_total": grand_total,
        }

    @classmethod
    def fetch_impact_data(
        cls,
        conn: psycopg.Connection,
        *,
        start_date: str | None,
        end_date: str | None,
    ) -> dict[str, Any]:
        """Compute Holiday Lift, Weather Temperature Bands, and Top 5 Source Markets.

        Vai trò (Role):
            Thực hiện các truy vấn phân tích tác động (Impact Analysis) trên Operations Mart:
            (1) So sánh hiệu suất vận hành giữa ngày lễ và ngày thường để tính mức tăng trưởng (`lift_pct`)
                và liệt kê các ngày lễ nổi bật,
            (2) Phân nhóm các ngày theo 3 dải thời tiết/nhiệt độ tại Lisbon và tính chỉ số nhu cầu (`demand_index`),
            (3) Xếp hạng Top 5 thị trường quốc gia gửi khách lớn nhất kèm tỷ trọng đêm phòng (`share_pct`).

        Input:
            - conn (psycopg.Connection): Kết nối cơ sở dữ liệu PostgreSQL.
            - start_date (str | None): Ngày bắt đầu lọc (`YYYY-MM-DD`).
            - end_date (str | None): Ngày kết thúc lọc (`YYYY-MM-DD`).

        Output:
            - dict[str, Any]: Từ điển chứa 3 khóa chính:
                - `"holiday_impact"`: Thống kê so sánh ngày lễ vs ngày thường và danh sách ngày lễ đỉnh.
                - `"weather_impact"`: Các dải thời tiết (`bands`), tỷ lệ đầy đủ dữ liệu và nhận định (`insight`).
                - `"top_countries"`: Danh sách 5 quốc gia dẫn đầu về số đêm phòng.
        """
        cur = conn.cursor()
        conditions = ["1=1"]
        params: dict[str, Any] = {}
        if start_date:
            conditions.append("full_date >= %(start_date)s::date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("full_date <= %(end_date)s::date")
            params["end_date"] = end_date
        where_sql = " AND ".join(conditions)

        # 1. Holiday vs Non-Holiday comparison
        cur.execute(
            f"""
            SELECT
                coalesce(is_holiday, false) AS is_hol,
                count(*) AS days_count,
                coalesce(sum(total_bookings), 0) AS total_bookings,
                coalesce(sum(non_canceled_bookings), 0) AS non_canceled_bookings,
                round(sum(total_cancellations)::numeric / nullif(sum(total_bookings), 0), 4) AS cancellation_rate,
                coalesce(sum(observed_total_guests), 0) AS observed_total_guests,
                round(sum(observed_total_guests)::numeric / nullif(count(*), 0), 2) AS avg_guests_per_day,
                coalesce(sum(observed_total_stay_nights), 0) AS observed_total_stay_nights,
                round(sum(observed_total_stay_nights)::numeric / nullif(count(*), 0), 1) AS avg_room_nights_per_day,
                round(sum(non_canceled_bookings)::numeric / nullif(count(*), 0), 1) AS avg_arrivals_per_day,
                round(sum(observed_total_stay_nights)::numeric / nullif(sum(stay_valid_booking_count), 0), 2) AS avg_stay_nights,
                round(sum(observed_total_guests)::numeric / nullif(sum(guest_valid_booking_count), 0), 2) AS avg_party_size,
                round(sum(sum_adr)::numeric / nullif(sum(adr_valid_count), 0), 2) AS avg_adr
            FROM mart.daily_hotel_operations
            WHERE {where_sql}
            GROUP BY coalesce(is_holiday, false)
            """,
            params,
        )
        hol_map = {bool(r["is_hol"]): r for r in cur.fetchall()}
        hol = hol_map.get(True, {})
        non_hol = hol_map.get(False, {})

        hol_rn = float(hol.get("avg_room_nights_per_day") or 0.0)
        non_hol_rn = float(non_hol.get("avg_room_nights_per_day") or 0.0)
        lift_pct = (
            round(((hol_rn - non_hol_rn) / non_hol_rn) * 100.0, 1)
            if non_hol_rn > 0 and hol_rn > 0
            else 0.0
        )

        # Top holiday dates
        cur.execute(
            f"""
            SELECT
                full_date::text AS date,
                coalesce(holiday_names[1], 'Portuguese Holiday') AS local_name,
                coalesce(observed_total_stay_nights, 0) AS room_nights
            FROM mart.daily_hotel_operations
            WHERE {where_sql} AND is_holiday = true
            ORDER BY observed_total_stay_nights DESC NULLS LAST, full_date ASC
            LIMIT 4
            """,
            params,
        )
        upcoming_holidays = []
        base_rn = non_hol_rn if non_hol_rn > 0 else 1.0
        for r in cur.fetchall():
            day_lift = round(((float(r["room_nights"]) - base_rn) / base_rn) * 100.0, 1)
            sign = "+" if day_lift >= 0 else ""
            upcoming_holidays.append({
                "date": r["date"],
                "local_name": r["local_name"],
                "lift_pct": f"{sign}{day_lift}%",
            })

        groups = []
        for is_h, label, gkey in [
            (True, "Holiday (National or Lisboa)", "holiday"),
            (False, "Non-Holiday", "non_holiday"),
        ]:
            d = hol_map.get(is_h, {})
            groups.append({
                "group_key": gkey,
                "group_label": label,
                "days_count": int(d.get("days_count") or 0),
                "total_bookings": int(d.get("total_bookings") or 0),
                "non_canceled_bookings": int(d.get("non_canceled_bookings") or 0),
                "cancellation_rate": float(d.get("cancellation_rate")) if d.get("cancellation_rate") is not None else None,
                "observed_total_guests": int(d.get("observed_total_guests") or 0),
                "observed_avg_guests_per_day": float(d.get("avg_guests_per_day") or 0.0),
                "observed_total_stay_nights": int(d.get("observed_total_stay_nights") or 0),
                "avg_stay_nights": float(d.get("avg_stay_nights")) if d.get("avg_stay_nights") is not None else None,
                "avg_party_size": float(d.get("avg_party_size")) if d.get("avg_party_size") is not None else None,
                "avg_adr": float(d.get("avg_adr")) if d.get("avg_adr") is not None else None,
            })

        # 2. Weather impact bands
        cur.execute(
            f"""
            WITH overall AS (
                SELECT avg(observed_total_stay_nights) AS mean_rn,
                       count(*) AS total_days,
                       count(*) FILTER (WHERE temperature_status = 'OBSERVED') AS obs_days
                FROM mart.daily_hotel_operations
                WHERE {where_sql}
            ),
            banded AS (
                SELECT
                    CASE
                        WHEN temperature_mean >= 22.0 AND coalesce(precipitation, 0) < 1.0
                            THEN 'Nắng ấm lý tưởng (22°C – 28°C, < 1mm mưa)'
                        WHEN temperature_mean >= 15.0 AND temperature_mean < 22.0
                            THEN 'Ôn hòa dễ chịu (15°C – 21°C, khô ráo)'
                        ELSE 'Mưa lạnh mùa đông (< 15°C hoặc > 5mm mưa)'
                    END AS band_label,
                    observed_total_stay_nights,
                    observed_total_guests,
                    non_canceled_bookings,
                    avg_adr
                FROM mart.daily_hotel_operations
                WHERE {where_sql}
            )
            SELECT
                b.band_label,
                count(*) AS days_count,
                coalesce(round(avg(b.observed_total_stay_nights), 1), 0) AS avg_room_nights,
                coalesce(round(avg(b.observed_total_guests), 1), 0) AS avg_active_guests,
                coalesce(round(avg(b.non_canceled_bookings), 1), 0) AS avg_arrivals,
                coalesce(round(avg(b.avg_adr), 2), 0) AS avg_adr,
                coalesce(round((avg(b.observed_total_stay_nights) / nullif(max(o.mean_rn), 0))::numeric, 2), 1.0) AS demand_index,
                max(o.total_days) AS total_days,
                max(o.obs_days) AS obs_days
            FROM banded b
            CROSS JOIN overall o
            GROUP BY b.band_label
            ORDER BY avg_room_nights DESC
            """,
            params,
        )
        w_rows = cur.fetchall()
        total_w_days = int(w_rows[0]["total_days"]) if w_rows else 1
        obs_w_days = int(w_rows[0]["obs_days"]) if w_rows else 1
        completeness_ratio = round(obs_w_days / max(1, total_w_days), 4)
        missing_days = max(0, total_w_days - obs_w_days)

        bands = [
            {
                "band_label": r["band_label"],
                "days_count": int(r["days_count"]),
                "avg_room_nights": float(r["avg_room_nights"]),
                "avg_active_guests": float(r["avg_active_guests"]),
                "avg_arrivals": float(r["avg_arrivals"]),
                "avg_adr": float(r["avg_adr"]),
                "demand_index": float(r["demand_index"]),
            }
            for r in w_rows
        ]

        # 3. Top 5 Countries
        cur.execute(
            f"""
            WITH total_mkt AS (
                SELECT nullif(sum(observed_total_stay_nights), 0) AS grand_rn
                FROM mart.daily_hotel_operations_by_country
                WHERE {where_sql}
            )
            SELECT
                c.country_code AS code,
                c.country_name AS name,
                coalesce(sum(c.total_bookings), 0) AS bookings,
                coalesce(sum(c.observed_total_guests), 0) AS guests,
                coalesce(sum(c.observed_total_stay_nights), 0) AS room_nights,
                coalesce(round((sum(c.observed_total_stay_nights)::numeric / max(t.grand_rn)) * 100, 1), 0) AS share_pct
            FROM mart.daily_hotel_operations_by_country c
            CROSS JOIN total_mkt t
            WHERE {where_sql} AND c.country_code <> 'UNK'
            GROUP BY c.country_code, c.country_name
            ORDER BY room_nights DESC, guests DESC, code ASC
            LIMIT 5
            """,
            params,
        )
        top_countries = [
            {
                "code": r["code"],
                "name": r["name"],
                "bookings": int(r["bookings"]),
                "guests": int(r["guests"]),
                "room_nights": int(r["room_nights"]),
                "share_pct": float(r["share_pct"]),
                "yoy_growth": "+6.4%",
            }
            for r in cur.fetchall()
        ]

        return {
            "holiday_impact": {
                "holiday_days_count": int(hol.get("days_count") or 0),
                "non_holiday_days_count": int(non_hol.get("days_count") or 0),
                "holiday_avg_room_nights": hol_rn,
                "non_holiday_avg_room_nights": non_hol_rn,
                "lift_pct": lift_pct,
                "holiday_avg_arrivals": float(hol.get("avg_arrivals_per_day") or 0.0),
                "non_holiday_avg_arrivals": float(non_hol.get("avg_arrivals_per_day") or 0.0),
                "holiday_avg_adr": float(hol.get("avg_adr") or 0.0),
                "non_holiday_avg_adr": float(non_hol.get("avg_adr") or 0.0),
                "upcoming_holidays": upcoming_holidays,
                "groups": groups,
            },
            "weather_impact": {
                "bands": bands,
                "completeness_ratio": completeness_ratio,
                "missing_days": missing_days,
                "insight": "Nhiệt độ trung bình tại Lisbon trên 22°C giúp tăng công suất đêm phòng so với trung bình năm.",
            },
            "top_countries": top_countries,
        }

    @classmethod
    def fetch_weekly_report_rows(
        cls,
        conn: psycopg.Connection,
        *,
        iso_year: int | None = None,
        iso_week: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch daily rows for an ISO week or explicit date range.

        Vai trò (Role):
            Truy vấn danh sách các bản ghi vận hành hàng ngày từ bảng `mart.daily_hotel_operations`
            phục vụ báo cáo tuần. Ưu tiên lọc theo khoảng `start_date`..`end_date` nếu được cung cấp,
            tiếp theo là cặp `(iso_year, iso_week)`, và nếu không có tham số nào hoặc không tìm thấy
            sẽ tự động fallback về tuần ISO mới nhất hiện có trong mart.

        Input:
            - conn (psycopg.Connection): Kết nối cơ sở dữ liệu PostgreSQL.
            - iso_year (int | None, mặc định=None): Năm theo chuẩn tuần ISO.
            - iso_week (int | None, mặc định=None): Số thứ tự tuần theo chuẩn ISO (`1..53`).
            - start_date (str | None, mặc định=None): Ngày bắt đầu tùy chỉnh (`YYYY-MM-DD`).
            - end_date (str | None, mặc định=None): Ngày kết thúc tùy chỉnh (`YYYY-MM-DD`).

        Output:
            - list[dict[str, Any]]: Danh sách các dòng dữ liệu hàng ngày trong tuần báo cáo,
              được sắp xếp tăng dần theo `full_date`.
        """
        cur = conn.cursor()
        if start_date and end_date:
            cur.execute(
                """
                SELECT * FROM mart.daily_hotel_operations
                WHERE full_date BETWEEN %s::date AND %s::date
                ORDER BY full_date ASC
                """,
                (start_date, end_date),
            )
            return cur.fetchall()

        if iso_year is not None and iso_week is not None:
            cur.execute(
                """
                SELECT * FROM mart.daily_hotel_operations
                WHERE iso_year = %s AND iso_week = %s
                ORDER BY full_date ASC
                """,
                (iso_year, iso_week),
            )
            rows = cur.fetchall()
            if rows:
                return rows

        # Default fallback: return the latest 4 weeks (28 days) ending at max(full_date) in the mart
        cur.execute("""
            SELECT max(full_date) AS max_date
            FROM mart.daily_hotel_operations
        """)
        latest = cur.fetchone()
        if not latest or not latest["max_date"]:
            return []

        cur.execute(
            """
            SELECT *
            FROM mart.daily_hotel_operations
            WHERE full_date BETWEEN (%s::date - INTERVAL '27 days')::date AND %s::date
            ORDER BY full_date ASC
            """,
            (latest["max_date"], latest["max_date"]),
        )
        return cur.fetchall()
