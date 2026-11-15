# Machine Learning

Dự báo lượng khách của booking không hủy theo ngày đến, gồm dự báo ngày và tháng.

- `demand_forecast/data.py`: export và kiểm tra snapshot DW/Mart có phiên bản.
- `demand_forecast/imputed.py`, `causal.py`, `monthly.py`: ba giao thức thực nghiệm.
- `demand_forecast/train.py`, `training.py`, `execution.py`: CLI và huấn luyện ngoại tuyến.
- `demand_forecast/predict.py`, `registry.py`, `artifacts.py`: suy luận và kiểm tra model artifacts.
- Các module còn lại hỗ trợ feature, tiền xử lý, baseline, đóng gói và đánh giá.
- `requirements.txt`: dependency ML được pin phiên bản.

`cancellation/` và `guest_mix/` giữ các file TODO cho Phase 2; hiện chưa huấn luyện hoặc phục vụ hai bài toán này.

Snapshot/model sinh ra ở `artifacts/ml_serving/`. Xem [thực nghiệm notebook](../notebooks/README.md) và [ML serving handoff](../docs/ml/ml_serving_handoff.md).
