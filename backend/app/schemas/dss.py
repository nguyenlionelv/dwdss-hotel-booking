"""DSS daily and monthly contracts with explicit unknowns and protocol metadata."""
from datetime import date, datetime
from typing import Literal, Any
from pydantic import BaseModel, ConfigDict, Field

Level = Literal['HIGH', 'NORMAL', 'LOW', 'INSUFFICIENT_HISTORY']

class Contract(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

class ThresholdRule(Contract):
    lookback_days_required: int = 56
    complete_days_available: int
    sufficient_history: bool
    latest_label_date: date
    mean_guests_8w: float | None
    std_guests_8w: float | None
    high_threshold: float | None
    low_threshold: float | None

class Peak(Contract):
    forecast_date: date
    predicted_guest_count: float
    demand_level: Level

class Summary(Contract):
    total_predicted_guests_7d: float
    total_predicted_guests_7d_rounded: int
    peak_forecast_days: list[Peak]
    demand_level_counts: dict[str, int]

class ForecastRow(Peak):
    as_of_date: date
    day_of_week: int
    is_weekend: bool
    is_holiday: bool | None = None
    predicted_guest_count_display: int
    actual_guest_count: float | None = None
    predicted_room_nights: float | None = None
    recommended_action: str
    model_version: str
    generated_at: datetime
    is_peak: bool = False

class HistoryRow(Contract):
    full_date: date
    observed_total_guests: float | None
    target_guests: float | None
    guest_data_status: str

class Comparison(Contract):
    model_name: str
    model_label: str
    is_baseline: bool
    is_selected: bool
    available_for_inference: bool = False
    overall_mae: float
    overall_rmse: float
    horizon_mae: dict[str, float]
    metric_protocol: str
    population: str

class DailyForecastResponse(Contract):
    hotel_name: str = 'City Hotel'
    as_of_date: date
    horizon: int
    model_id: str
    model_version: str
    data_version: str
    generated_at: datetime
    model_metadata: dict[str, Any]
    dss_threshold_rule: ThresholdRule
    summary: Summary
    forecasts: list[ForecastRow]
    recent_history: list[HistoryRow]
    model_comparison: list[Comparison]
    decision_support: 'DecisionSupport'
    resource_allocation: 'ResourceAllocation'

class AllocationDay(Contract):
    date: date
    predicted_guests: float
    allocation_share: float = Field(ge=0, le=1)
    allocation_pct: float = Field(ge=0, le=100)
    allocation_units: float = Field(ge=0)
    comparison_with_uniform_pct_points: float
    review_action: str | None

class AllocationEvaluation(Contract):
    metric: Literal['MRR']
    validation_results: dict[str, Any] | None
    selected_policy_reason: str
    availability: Literal['available', 'unavailable']

class ResourceAllocation(Contract):
    status: Literal['ready', 'unavailable']
    policy_version: str | None = None
    selected_policy: Literal['uniform', 'historical_weekday', 'forecast_proportional', 'blended'] | None = None
    budget_units: float | None = None
    lambda_: float | None = Field(default=None, alias='lambda')
    daily_allocation: list[AllocationDay]
    policy_evaluation: AllocationEvaluation | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None

class DecisionInsight(Contract):
    forecast_date: date
    signal: Literal['ABOVE_TYPICAL_DEMAND', 'BELOW_TYPICAL_DEMAND', 'DEMAND_SURGE', 'DEMAND_DROP']
    title: str
    priority: Literal['REVIEW', 'INSIGHT']
    category: Literal['DEMAND_INSIGHT', 'OPERATIONAL_ADVISORY'] = 'OPERATIONAL_ADVISORY'
    predicted_guests: float
    historical_reference: float
    deviation_guests: float
    absolute_deviation: float
    deviation_pct: float | None
    evidence: str
    recommended_action: str | None
    analysis: Literal['weekday', 'transition']
    horizon: int
    variability: float
    sample_count: int
    reference_window_days: int
    standardized_deviation: float
    calibrated_standardized_threshold: float
    model_error_scale: float | None
    error_population: Literal['COMPLETE_ONLY'] | None
    strength: float
    previous_forecast_date: date | None = None
    forecast_change: float | None = None
    forecast_change_pct: float | None = None

class DecisionSupport(Contract):
    policy_version: Literal['dss-v2']
    state: Literal['ACTIONABLE', 'INSIGHTS', 'NEUTRAL']
    insights: list[DecisionInsight] = Field(max_length=3)
    metadata: dict[str, Any]

class MonthlyForecastResponse(Contract):
    hotel_name: str = 'City Hotel'
    kind: Literal['monthly'] = 'monthly'
    as_of_date: date
    forecast_month: str
    horizon_months: Literal[1] = 1
    units: Literal['guests/month'] = 'guests/month'
    predicted_guests: float
    model_id: str
    model_version: str
    data_version: str
    generated_at: datetime
    model_metadata: dict[str, Any]
