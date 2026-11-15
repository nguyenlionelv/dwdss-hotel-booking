"""Daily inference and independent DSS classification over canonical COMPLETE history."""
from collections import Counter
from datetime import datetime, timezone
import math
import numpy as np
import pandas as pd
from ml.demand_forecast.registry import entries, resolve
from ml.demand_forecast.predict import inputs, daily_prediction, ForecastInputError
from ml.demand_forecast.evaluation import clean
from .decision_engine.recommendation_service import decision_support
from .decision_engine.allocation_engine import resource_allocation

ACTIONS = {
    'HIGH': 'Rà soát khả năng tiếp nhận, chuẩn bị nhân lực và workload housekeeping/F&B',
    'NORMAL': 'Duy trì kế hoạch vận hành, theo dõi thay đổi',
    'LOW': 'Rà soát phân bổ ca và lượng chuẩn bị theo nhu cầu thấp',
    'INSUFFICIENT_HISTORY': 'Chưa đủ dữ liệu lịch sử để phân mức',
}

def published_version(conn):
    row = conn.execute("""SELECT m.data_version FROM mart.dataset_state m
        JOIN dw.active_dataset a ON a.run_id=m.dw_run_id
        JOIN dw.load_run r ON r.run_id=a.run_id AND r.data_version=m.data_version
        WHERE r.status='published'""").fetchone()
    if not row:
        raise ValueError('No matching published DW/Mart')
    return str(row['data_version'])

def public_metadata(metadata):
    return {k: metadata[k] for k in ['algorithm','training_cutoff','imputation_policy','label_definition',
            'validation_metrics','feature_schema','availability_assumptions','metric_protocol']}

def thresholds(daily, latest):
    window = daily[daily.full_date.between(latest-pd.Timedelta(days=55),latest)]
    known = window[window.guest_data_status.eq('COMPLETE') & window.target_guests.notna()]
    sufficient = len(window)==56 and len(known)==56
    mean = float(known.target_guests.mean()) if sufficient else None
    std = float(known.target_guests.std(ddof=0)) if sufficient else None
    return dict(lookback_days_required=56,complete_days_available=len(known),sufficient_history=sufficient,
        latest_label_date=str(latest.date()),mean_guests_8w=mean,std_guests_8w=std,
        high_threshold=mean+std if sufficient else None, low_threshold=max(0.,mean-std) if sufficient else None)

def classify(value,rule):
    if not rule['sufficient_history']: return 'INSUFFICIENT_HISTORY'
    if value>=rule['high_threshold']: return 'HIGH'
    if value<=rule['low_threshold']: return 'LOW'
    return 'NORMAL'

def comparisons(all_entries, selected):
    if 'benchmark_comparison' in selected:
        return selected['benchmark_comparison']
    rows=[]
    for metadata,_ in all_entries:
        if metadata['notebook']!=selected['notebook']: continue
        metric=metadata['validation_metrics']
        populations=[m for m in metric['populations'] if m['population']=='ALL_ESTIMATED']
        by_horizon={str(h):float(np.mean([m['MAE'] for m in metric['horizon'] if m['population']=='ALL_ESTIMATED' and m['horizon']==h])) for h in range(1,8)}
        rows.append(dict(model_name=metadata['model_id'],model_label=metadata['algorithm']+' / '+metadata['imputation_policy'],
            is_baseline=True,is_selected=metadata['model_id']==selected['model_id'],
            overall_mae=float(np.mean([m['MAE'] for m in populations])),
            overall_rmse=float(np.mean([m['RMSE'] for m in populations])),horizon_mae=by_horizon,
            metric_protocol=metadata['metric_protocol'],population='ALL_ESTIMATED'))
    return rows

def daily_forecast(conn, as_of_date, model_name=None, horizon=7, budget_units=100):
    version=published_version(conn)
    available=entries(version,'daily')
    if model_name is not None and model_name not in [m['model_id'] for m,_ in available]:
        raise ForecastInputError('Unsupported daily model; see /api/dss/models')
    metadata,state=resolve(model_name,version,'daily')
    daily,bookings=inputs(metadata)
    cutoff=pd.Timestamp(as_of_date)
    dates,values,latest=daily_prediction(metadata,state,daily,bookings,cutoff,horizon)
    rule=thresholds(daily,latest)
    now=datetime.now(timezone.utc).isoformat()
    index=daily.set_index('full_date')
    rows=[]
    for day,value in zip(dates,values):
        canonical=index.loc[day] if day in index.index else None
        actual=float(canonical.target_guests) if canonical is not None and pd.notna(canonical.target_guests) else None
        holiday=bool(canonical.is_holiday) if canonical is not None and pd.notna(canonical.is_holiday) else None
        level=classify(value,rule)
        rows.append(dict(as_of_date=str(cutoff.date()),forecast_date=str(day.date()),day_of_week=day.isoweekday(),
            is_weekend=day.day_of_week>=5,is_holiday=holiday,predicted_guest_count=value,
            predicted_guest_count_display=math.floor(value+.5),actual_guest_count=actual,
            predicted_room_nights=None,demand_level=level,recommended_action=ACTIONS[level],
            model_version=metadata['model_version'],generated_at=now,is_peak=value==max(values)))
    history=daily[daily.full_date.between(latest-pd.Timedelta(days=27),latest)]
    history=[dict(full_date=str(r.full_date.date()),observed_total_guests=float(r.observed_total_guests) if pd.notna(r.observed_total_guests) else None,
                  target_guests=float(r.target_guests) if pd.notna(r.target_guests) else None,
                  guest_data_status=r.guest_data_status) for r in history.itertuples()]
    total=float(sum(values))
    return dict(hotel_name='City Hotel',as_of_date=str(cutoff.date()),horizon=horizon,model_id=metadata['model_id'],
        model_version=metadata['model_version'],data_version=version,generated_at=now,model_metadata=public_metadata(metadata),
        dss_threshold_rule=rule,summary=dict(total_predicted_guests_7d=total,total_predicted_guests_7d_rounded=math.floor(total+.5),
            peak_forecast_days=[{k:r[k] for k in ['forecast_date','predicted_guest_count','demand_level']} for r in rows if r['is_peak']],
            demand_level_counts=dict(Counter(r['demand_level'] for r in rows))),forecasts=rows,recent_history=history,
        model_comparison=comparisons(available,metadata),
        decision_support=decision_support(conn,rows,metadata,latest,version),
        resource_allocation=resource_allocation(conn,rows,metadata,latest,version,budget_units,cutoff))

def monthly_forecast(conn,as_of_date,model_name=None):
    version=published_version(conn)
    available=entries(version,'monthly')
    if model_name is not None and model_name not in [m['model_id'] for m,_ in available]:
        raise ForecastInputError('Unsupported monthly model')
    metadata,state=resolve(model_name,version,'monthly')
    origin=state['origins'].get(str(as_of_date))
    if origin is None or pd.Timestamp(as_of_date) < pd.Timestamp('2017-05-31'): raise ForecastInputError('Use a saved month-end cutoff from 2017-05-31 to 2017-08-31')
    # Verifies the saved immutable snapshot even though prediction is precomputed offline.
    inputs(metadata)
    meta=public_metadata(metadata);meta['training_cutoff']=origin['training_cutoff']
    return dict(hotel_name='City Hotel',as_of_date=str(as_of_date),forecast_month=origin['forecast_month'],
        predicted_guests=origin['predicted_guests'],model_id=metadata['model_id'],model_version=metadata['model_version'],
        data_version=version,generated_at=datetime.now(timezone.utc).isoformat(),model_metadata=meta)
