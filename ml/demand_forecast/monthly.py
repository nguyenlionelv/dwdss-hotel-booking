"""Notebook-equivalent experiment logic; extracted definitions, with instance-scoped input data.

Source: notebooks/experiments/monthly_demand_forecast_report.ipynb. No notebook executes at serving time.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from .preprocessing import ExperimentData
DAY = pd.Timedelta(days=1)
TRAIN_START = pd.Timestamp('2015-07-01')
SEED = 42

SEED = 42
MODELS = ('M0_last_month_rate', 'M1_seasonal_naive12', 'M2_OLS_trend', 'M3_seasonal_Ridge', 'M4_seasonal_blend')
MIN_ROOM_BOOKINGS = 30
IMPUTATION_POLICY = {'method': 'room_type_mean', 'group_column': 'reserved_room_type', 'min_room_bookings': MIN_ROOM_BOOKINGS, 'fallback': 'train_global_mean'}

class Experiment(ExperimentData):

    def fit_room_imputer(self, cutoff):
        train = self.valid[self.valid.full_date.between(TRAIN_START, pd.Timestamp(cutoff))]
        mu = float(train.total_guests.mean())
        rooms = train.groupby('reserved_room_type').total_guests.agg(['count', 'sum', 'mean'])
        rooms['use_room_mean'] = rooms['count'].ge(MIN_ROOM_BOOKINGS)
        rooms['fill_mean'] = rooms['mean'].where(rooms.use_room_mean, mu)
        return {**IMPUTATION_POLICY, 'mu_train': mu, 'fit_start': str(TRAIN_START.date()), 'fit_end': str(pd.Timestamp(cutoff).date()), 'fit_label_cutoff': str(pd.Timestamp(cutoff).date()), 'known_guest_sum': int(train.total_guests.sum()), 'known_booking_count': len(train), 'rooms': rooms.to_dict(orient='index')}

    def room_mean_table(self, imputer):
        return pd.DataFrame.from_dict(imputer['rooms'], orient='index').rename_axis('reserved_room_type').reset_index()

    def room_estimates(self, imputer, end):
        mask = self.bookings.is_canceled.eq(0) & ~self.bookings.guest_eligible & self.bookings.full_date.le(pd.Timestamp(end))
        missing = self.bookings.loc[mask].copy()
        means = {room: stats['fill_mean'] for room, stats in imputer['rooms'].items()}
        used = {room: stats['use_room_mean'] for room, stats in imputer['rooms'].items()}
        missing['estimated_guests'] = missing.reserved_room_type.map(means).astype(float).fillna(imputer['mu_train'])
        missing['imputation_source'] = np.where(missing.reserved_room_type.map(used).eq(True), 'ROOM_MEAN', 'GLOBAL_MEAN')
        return missing

    def save_room_imputation(self, prefix, imputer, end):
        self.save_json(prefix + '_imputer.json', imputer)
        self.save_csv(prefix + '_room_means.csv', self.room_mean_table(imputer))
        self.save_csv(prefix + '_imputed_bookings.csv', self.room_estimates(imputer, end))

    def eligible_imputation(self, frame):
        return frame.guest_data_status.eq('PARTIAL') & frame.booking_data_status.eq('COMPLETE') & frame.rejected_booking_count.eq(frame.excluded_booking_count) & frame.missing_guest_bookings_count.gt(0) & frame.guest_ineligible_booking_count.eq(frame.missing_guest_bookings_count) & frame.non_canceled_bookings.eq(frame.guest_valid_booking_count + frame.missing_guest_bookings_count)

    def room_labels(self, cutoff, end):
        frame = self.daily[self.daily.full_date.le(pd.Timestamp(end))].copy()
        imputer = self.fit_room_imputer(cutoff)
        additions = self.room_estimates(imputer, end).groupby('full_date').estimated_guests.sum()
        frame['target_true'] = frame.target_guests.astype(float)
        frame['estimated_missing_guests'] = frame.full_date.map(additions).fillna(0.0)
        mask = self.eligible_imputation(frame)
        frame.loc[~mask, 'estimated_missing_guests'] = 0.0
        frame['target_estimated'] = frame.target_true.copy()
        frame.loc[mask, 'target_estimated'] = frame.loc[mask, 'observed_total_guests'].astype(float) + frame.loc[mask, 'estimated_missing_guests']
        frame['target_is_imputed'] = mask.to_numpy(dtype=bool)
        frame['partition'] = np.where(frame.full_date.le(pd.Timestamp(cutoff)), 'train', 'evaluation')
        return (frame, imputer)

    def monthly_labels(self, cutoff, end):
        frame, imputer = self.room_labels(cutoff, end)
        assert frame.target_estimated.notna().all(), 'Unresolved day: do not silently sum a partial month'
        frame['month'] = frame.full_date.dt.to_period('M')
        monthly = frame.groupby('month', sort=True).agg(target=('target_estimated', 'sum'), observed=('observed_total_guests', 'sum'), estimated_addition=('estimated_missing_guests', 'sum'), calendar_days=('full_date', 'size'), imputed_days=('target_is_imputed', 'sum'), missing_bookings=('missing_guest_bookings_count', 'sum'))
        monthly['rate'] = monthly.target / monthly.calendar_days
        monthly['target_is_estimated'] = monthly.imputed_days.gt(0)
        return (monthly, imputer)

    def calendar_features(self, months, seasonal=False):
        months = pd.PeriodIndex(months, freq='M')
        result = pd.DataFrame({'month_index': [p.ordinal - pd.Period('2015-07', freq='M').ordinal for p in months]})
        if seasonal:
            phase = 2 * np.pi * (months.month - 1) / 12
            result['year_sin'], result['year_cos'] = (np.sin(phase), np.cos(phase))
        return result

    def predict_month(self, name, train, target):
        assert target == train.index[-1] + 1 and len(train) >= 12
        if name == 'M0_last_month_rate':
            return float(train.rate.iloc[-1] * target.days_in_month)
        if name == 'M1_seasonal_naive12':
            return float(train.at[target - 12, 'target'])
        if name == 'M4_seasonal_blend':
            return float(0.5 * (train.rate.iloc[-1] + train.at[target - 12, 'rate']) * target.days_in_month)
        if name == 'M2_OLS_trend':
            model = LinearRegression().fit(self.calendar_features(train.index), train.target)
            return float(model.predict(self.calendar_features([target]))[0])
        model = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
        model.fit(self.calendar_features(train.index, seasonal=True), train.rate)
        return float(model.predict(self.calendar_features([target], seasonal=True))[0] * target.days_in_month)

    def run_origin(self, target, stage):
        cutoff = (target - 1).end_time.normalize()
        labels, imputer = self.monthly_labels(cutoff, target.end_time.normalize())
        train = labels[labels.index < target]
        raw = pd.DataFrame([{'stage': stage, 'model': name, 'target_month': str(target), 'train_end': str(train.index[-1]), 'train_months': len(train), 'mu_train': imputer['mu_train'], 'y_pred': self.predict_month(name, train, target)} for name in MODELS])
        prefix = f'{stage}_{target}'
        self.save_room_imputation(prefix, imputer, target.end_time.normalize())
        self.save_csv(prefix + '_unscored.csv', raw)
        truth = labels.loc[target]
        return raw.assign(actual=float(truth.target), observed=float(truth.observed), estimated_addition=float(truth.estimated_addition), target_is_estimated=bool(truth.target_is_estimated))

    def metrics(self, predictions):
        rows = []
        for name, group in predictions.groupby('model', sort=False):
            e = group.y_pred - group.actual
            complete = group[~group.target_is_estimated]
            rows.append({'model': name, 'n_months': len(group), 'MAE': float(e.abs().mean()), 'RMSE': float(np.sqrt((e ** 2).mean())), 'WAPE': float(e.abs().sum() / group.actual.sum()), 'signed_bias': float(e.mean()), 'complete_months': len(complete), 'COMPLETE_ONLY_MAE': float((complete.y_pred - complete.actual).abs().mean()) if len(complete) else np.nan})
        return pd.DataFrame(rows)
