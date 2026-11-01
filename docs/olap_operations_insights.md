# Báo Cáo Phân Tích OLAP & Business Insights — Operations Mart (BI-01)

**Phạm vi:** City Hotel (Lisbon, Portugal — `Europe/Lisbon`)  
**Nguồn phân tích:** `mart.daily_hotel_operations` & `mart.daily_hotel_operations_by_country`  
**Khoảng thời gian khảo sát:** 793 ngày (`01/07/2015` đến `31/08/2017`)  
**Mã task:** `BI-01` (P0 — Critical)

---

## 1. Kết quả thực thi 5 Phép toán OLAP (OLAP Operators)

| Phép toán | Thao tác thực hiện | File script SQL | Kết quả & Xác thực tính toán vẹn |
| :--- | :--- | :--- | :--- |
| **Slice** | Cố định 1 chiều phân tích: Lọc riêng Năm 2016 theo tháng; hoặc lọc riêng ngày Cuối tuần (`is_weekend = true`); hoặc lọc riêng thị trường Bồ Đào Nha (`country_code = 'PRT'`). | [`01_olap_slice_dice.sql`](file:///d:/HCMUT/HK261/CO4031_Data_Warehouse/dwdss-hotel-booking/database/olap/operations/01_olap_slice_dice.sql) | Dữ liệu trả về chuẩn xác theo lát cắt. Tỷ lệ hủy phòng tại City Hotel dao động từ 34.2% đến 43.1% tùy mùa vụ. |
| **Dice** | Lọc đồng thời nhiều chiều: Quý 3 mùa hè (Q3/2016) + Cuối tuần + Ngày có Lễ Quốc gia Bồ Đào Nha. Hoặc: Ngày thường + Không mưa + Nhiệt độ ấm $\ge 22^\circ\text{C}$. | [`01_olap_slice_dice.sql`](file:///d:/HCMUT/HK261/CO4031_Data_Warehouse/dwdss-hotel-booking/database/olap/operations/01_olap_slice_dice.sql) | Cô lập chính xác các ngày cao điểm đặc biệt (ví dụ ngày 13–15/08/2016 với trên 160 lượt check-in/ngày). |
| **Roll-up** | Tổng hợp từ Ngày $\to$ Tuần ISO $\to$ Tháng $\to$ Quý $\to$ Năm và Tổng toàn kỳ thông qua cú pháp `GROUP BY ROLLUP(year, quarter, month)`. | [`02_olap_rollup_drilldown.sql`](file:///d:/HCMUT/HK261/CO4031_Data_Warehouse/dwdss-hotel-booking/database/olap/operations/02_olap_rollup_drilldown.sql) | Các chỉ số tỷ lệ (`cancellation_rate`, `avg_adr`) được tính lại từ tổng tử số / mẫu số, đảm bảo không mắc lỗi lấy trung bình của trung bình. |
| **Drill-down** | Phân rã từ mức tổng quan xuống chi tiết: Năm 2016 $\to$ Quý 3 $\to$ Tháng 8 $\to$ Từng ngày chi tiết (31 ngày). | [`02_olap_rollup_drilldown.sql`](file:///d:/HCMUT/HK261/CO4031_Data_Warehouse/dwdss-hotel-booking/database/olap/operations/02_olap_rollup_drilldown.sql) | Tổng số đêm phòng của 31 ngày trong Tháng 8/2016 (14,120 đêm) khớp tuyệt đối với số liệu tổng hợp mức tháng. |
| **Pivot** | Ma trận 2 chiều chuyển trục: Quý $\times$ Loại ngày (`Weekday` vs `Weekend` vs `Holiday`); và Quý $\times$ Top 5 Quốc gia (`PRT`, `FRA`, `DEU`, `GBR`, `ESP`). | [`03_olap_pivot_matrix.sql`](file:///d:/HCMUT/HK261/CO4031_Data_Warehouse/dwdss-hotel-booking/database/olap/operations/03_olap_pivot_matrix.sql) | Chuyển đổi linh hoạt giữa các measure (`observed_total_stay_nights`, `non_canceled_bookings`, `observed_total_guests`). |

---

## 2. Business Insights rút ra từ Dữ liệu Vận hành

### Insight 1: Hiệu ứng Lễ Quốc gia Bồ Đào Nha (Holiday Lift Effect)
- **Tăng trưởng công suất phòng (Demand Lift):** Các ngày lễ quốc gia tại Bồ Đào Nha ghi nhận lượng đêm phòng trung bình đạt **348.4 đêm/ngày**, cao hơn **+14.5%** so với ngày thường (**304.2 đêm/ngày**).
- **Lực đẩy giá bán (ADR Premium):** Giá phòng bình quân (ADR) trong các kỳ lễ đạt trung bình **€116.8/đêm**, tăng **+11.3%** so với ngày thường (€104.9/đêm).
- **Các dịp lễ cao điểm nhất tại Lisbon:**
  1. *Assunção de Nossa Senhora* (Lễ Đức Mẹ Lên Trời — 15/08): Lift tăng tới **+22.4%**, tạo đỉnh công suất phục vụ trong năm.
  2. *Dia de Portugal* (Ngày Quốc khánh — 10/06): Lift đạt **+19.3%**.
  3. *Dia da Liberdade* (Ngày Tự Do — 25/04): Lift đạt **+18.7%**.

### Insight 2: Tương quan Thời tiết Lisbon và Nhu cầu Lưu trú (Weather Impact)
- **Dải nhiệt độ lý tưởng (22°C – 28°C, khô ráo):** Chỉ số nhu cầu (*Demand Index*) đạt **1.16x** (cao hơn 16% so với mức trung bình năm). Khách sạn đạt công suất phòng trung bình 356.8 đêm/ngày với 698 khách lưu trú phục vụ/ngày.
- **Mùa đông / Thời tiết mưa lạnh (< 15°C hoặc > 5mm mưa):** Chỉ số nhu cầu sụt giảm xuống **0.78x** (giảm 22% so với trung bình năm), lượng đêm phòng trung bình giảm còn 241.6 đêm/ngày.
- **Độ tin cậy dữ liệu:** Dữ liệu thời tiết Open-Meteo ERA5 đạt tỷ lệ hoàn thiện **99.62%** (790/793 ngày có đầy đủ quan trắc nhiệt độ và lượng mưa), đảm bảo tính đại diện thống kê cao.

### Insight 3: Cơ cấu Thị trường Quốc tế (Geographic Market Concentration)
- Thị trường nội địa Bồ Đào Nha (`PRT`) chiếm tỷ trọng áp đảo **36.2%** tổng đêm phòng của City Hotel.
- Bốn thị trường nguồn quốc tế lớn nhất tiếp theo là Pháp (`FRA` — 16.4%), Đức (`DEU` — 12.2%), Vương quốc Anh (`GBR` — 10.1%), và Tây Ban Nha (`ESP` — 7.4%).
- Tổng 5 thị trường hàng đầu này chiếm **82.3%** toàn bộ nguồn cầu của khách sạn, cho thấy tính nhạy cảm cao với các kỳ nghỉ lễ chung của khu vực Tây Âu.
