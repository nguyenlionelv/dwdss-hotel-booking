# Tổng hợp notebook thực nghiệm

Dùng các bản `_report.ipynb` cho báo cáo. Bốn notebook gốc được giữ nguyên;
các notebook ngoài bộ đã chọn nằm trong [extra](extra/).

## Dữ liệu và tiền xử lý chung

- Phạm vi: City Hotel, 07/2015–08/2017, **793 ngày và 79.250 booking** được chấp nhận trong snapshot.
- Biến đích: tổng khách của booking cuối cùng không hủy theo ngày đến; không phải occupancy hoặc số khách check-in thực tế.
- Bù phần khách thiếu đủ điều kiện theo mean khách/booking của `reserved_room_type`. Nhóm có **ít nhất 30 booking hợp lệ** dùng mean riêng; nhóm ít mẫu, chưa gặp hoặc không biết loại phòng dùng mean chung train. Bù từng booking rồi cộng lên ngày/tháng, giữ subtotal quan sát.
- Mean, median và scaler được fit theo train/cutoff của từng lượt. Feature số thiếu trong các pipeline ML daily dùng median; nhãn đã bù vẫn là giá trị ước tính.

## Ba notebook dự báo

### 1. [Imputed 3fold](experiments/history_demand_imputed_3fold_report.ipynb)

- **Mục tiêu:** dự báo tổng khách ngày cho 7 horizon, so sánh lịch sử chưa bù (`canonical_history`) và lịch sử đã bù (`imputed_history`). Nhánh chưa bù giữ target thiếu là `NaN`, không dùng làm nhãn train.
- **Chia dữ liệu:** `TimeSeriesSplit(n_splits=3)` trên 701 ngày development đến 31/05/2017; train lần lượt 176/351/526 ngày, validation đều 175 ngày. Test riêng 06–08/2017, 92 ngày; giả định nhãn có ngay cuối ngày (delay = 0).
- **Mô hình:** B0 mean train, B1 seasonal lag cùng thứ, B2 MA7, B3 MA14, B4 MA14 hiệu chỉnh theo horizon và thứ; Linear Regression, Ridge, Random Forest, Extra Trees, HistGradientBoosting. Baseline có quy tắc fallback khi thiếu history.
- **Feature và train:** 30 feature lag, rolling, lịch và trend; mỗi họ ML fit 7 model trực tiếp theo horizon. Model giữ cố định trong mỗi kỳ đánh giá, history cập nhật cuốn chiếu.
- **Kết quả:** cả hai nhánh chọn **B4_weekday**. Bù lịch sử chưa tạo cải thiện rõ: validation gần bằng nhau, test của nhánh đã bù hơi kém hơn.

### 2. [Causal methods](experiments/history_demand_causal_methods_report.ipynb)

- **Mục tiêu:** dự báo 7 horizon khi nhãn trễ **1 ngày**; “causal” chỉ thứ tự thông tin theo thời gian, không phải suy luận tác động nhân quả.
- **Chia dữ liệu:** cùng ba fold và test như notebook 1, nhưng cutoff nhãn lùi một ngày. History được bù bằng mean theo phòng tích lũy **trước từng ngày**; target benchmark dùng mean train tại cutoff.
- **Mô hình:** B4_matched, Holt–Winters mùa vụ tuần, residual HistGradientBoosting và residual Extra Trees. Hai model residual dùng 53 feature, gộp các horizon để học sai lệch so với anchor từ lịch sử.
- **Train và chọn cấu hình:** inner validation 56 ngày cuối train; model residual có trọng số ưu tiên dữ liệu gần, half-life 180 ngày. Refit trên development trước test.
- **Kết quả:** chọn **B4_matched**; các phương pháp mới chưa vượt baseline rõ rệt. Không xếp hạng trực tiếp với notebook 1 vì khác giả định delay.

### 3. [Monthly forecast](experiments/monthly_demand_forecast_report.ipynb)

- **Mục tiêu:** dự báo tổng khách **tháng tiếp theo**, với 26 mẫu tháng.
- **Chia dữ liệu:** 12 tháng train ban đầu; 11 tháng validation từ 07/2016–05/2017; test 06–08/2017. Rolling một tháng tới, refit và tính lại mean theo phòng trước mỗi origin.
- **Mô hình:** rate khách/ngày tháng trước, seasonal naive cùng tháng năm trước, OLS theo trend, Ridge theo trend và sin/cos năm, blend 50/50 hai rate lịch sử. OLS có 1 feature, Ridge có 3 feature.
- **Kết quả:** validation chọn **M0_last_month_rate**. OLS có test MAE thấp hơn (205,73 khách/tháng), nhưng không dùng test để thay model đã chọn. Test chỉ có 3 tháng nên kết luận còn hạn chế.

### Kết quả của model được chọn

Daily chọn theo trung bình đều MAE ba fold; monthly chọn theo MAE 11 tháng validation.
Trong phạm vi 1% so với điểm tốt nhất, ưu tiên model đơn giản theo thứ tự đã khai báo.
Các số dưới đây chấm trên nhãn gồm cả phần được bù (`ALL_ESTIMATED` ở daily).

| Notebook / nhánh | Model chọn từ validation | MAE validation | MAE test | RMSE test | Đơn vị |
|---|---|---:|---:|---:|---|
| Imputed 3fold / chưa bù | B4_weekday | 30,75 | 24,55 | 32,63 | Khách/dự báo ngày |
| Imputed 3fold / đã bù | B4_weekday | 30,73 | 24,90 | 32,92 | Khách/dự báo ngày |
| Causal methods | B4_matched | 30,92 | 24,96 | 32,98 | Khách/dự báo ngày |
| Monthly forecast | M0_last_month_rate | 438,07 | 288,16 | 325,45 | Khách/tháng |

Daily còn báo riêng `COMPLETE_ONLY` và `IMPUTED_ONLY`. Không so trực tiếp metric ngày với tháng.
Holdout đã được xem ở nghiên cứu trước, nên kết quả là thực nghiệm hồi cứu; nhãn ước tính không phải ground truth đã xác minh.

Số liệu lấy từ các lần chạy đã lưu: [Imputed 3fold](../artifacts/forecasting/history_demand_imputed_3fold_report/20261110T051148_553f2ff2/comparison.csv),
[Causal methods](../artifacts/forecasting/history_demand_causal_methods_report/20261110T051148_90f6fbc3/comparison.csv),
[Monthly forecast](../artifacts/forecasting/monthly_demand_forecast_report/20261110T051147_8eba5ce2/comparison.csv).

## [Notebook EDA](exploration/01_city_hotel_demand_eda_report.ipynb)

Khảo sát chất lượng và độ đầy đủ nhãn, phân bố tổng khách, xu hướng, mùa vụ theo thứ/tháng,
lag, holiday/weather, lead time và cancellation. EDA không train model hoặc bù nhãn thiếu.
Phân tích pattern chỉ dùng development; holdout chỉ xem độ đầy đủ dữ liệu.

Development có **701 ngày**, gồm **626 ngày có nhãn đầy đủ** và **75 ngày thiếu nhãn đầy đủ**.
Tương quan Pearson với lag 7 là **0,543** trên 551 cặp hợp lệ, là căn cứ khảo sát
feature tuần và baseline cùng thứ; tương quan không chứng minh quan hệ nhân quả.

## Chạy lại

Chọn kernel Python của `.venv` với dependency trong [ml/requirements.txt](../ml/requirements.txt),
sau đó **Restart Kernel → Run All**. Notebook in danh sách feature và lưu bảng, biểu đồ,
tham số bù cùng manifest vào `artifacts/forecasting/<tên notebook>/<run_id>`.

Đầu vào là [snapshot cố định](../artifacts/forecasting/history_demand_causal_methods/20261109T110426_146bf398),
không cần PostgreSQL đang chạy. Các notebook kiểm tra checksum; ba bản dự báo đọc thêm
Booking raw để ghép loại phòng, EDA đọc thêm raw và mapping để bổ sung thuộc tính.
Kiểm chứng gần nhất: [verification.json](../artifacts/notebook_execution/report_rewrite_20261110T051514_9ededd04/verification.json).
