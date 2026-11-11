"""Notebook-equivalent experiment logic; extracted definitions, with instance-scoped input data.

Source: notebooks/experiments/history_demand_causal_methods_report.ipynb. No notebook executes at serving time.
"""
import numpy as np
import json
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
HORIZONS = tuple(range(1, 8))
DELAY = 1
DEV_END = pd.Timestamp('2017-05-31')
MIN_ROOM_BOOKINGS = 30
IMPUTATION_POLICY = {'method': 'room_type_mean', 'group_column': 'reserved_room_type', 'min_room_bookings': MIN_ROOM_BOOKINGS, 'fallback': 'train_global_mean'}
METHODS = ('A1_holt_winters', 'A2_residual_histgb', 'A3_residual_extra_trees')
ORDER = ('B4_matched',) + METHODS
INNER_DAYS, RECENCY_HALF_LIFE = (56, 180)
GRIDS = {'A1_holt_winters': [dict(alpha=a, beta=b, gamma=g, phi=0.9) for a in (0.2, 0.5) for b in (0.0, 0.05) for g in (0.1, 0.3)], 'A2_residual_histgb': [dict(max_leaf_nodes=n) for n in (7, 15)], 'A3_residual_extra_trees': [dict(min_samples_leaf=n) for n in (14, 28)]}

class Experiment(ExperimentData):

    def schedule(self, start, end):
        start, end = (pd.Timestamp(start), pd.Timestamp(end))
        origins = pd.date_range(start - DAY, end - 7 * DAY)
        return pd.DataFrame([(t, h, t + h * DAY) for t in origins for h in HORIZONS], columns=['origin', 'horizon', 'target_date'])

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

    def causal_room_estimates(self, frame, booking_frame=None):
        source = self.bookings if booking_frame is None else booking_frame
        known = source[source.is_canceled.eq(0) & source.guest_eligible]
        mask = source.is_canceled.eq(0) & ~source.guest_eligible & source.full_date.isin(frame.full_date)
        missing = source.loc[mask].copy()
        counts = frame.guest_valid_booking_count.astype(float).cumsum().shift(1)
        mu = frame.observed_total_guests.astype(float).cumsum().shift(1) / counts.where(counts.gt(0))
        mu.index = pd.DatetimeIndex(frame.full_date)
        missing['past_global_mean'] = missing.full_date.map(mu)
        missing['estimated_guests'] = missing.past_global_mean
        missing['room_known_count'] = 0
        missing['imputation_source'] = 'GLOBAL_MEAN'
        for room, group in missing.groupby('reserved_room_type', dropna=False):
            room_known = known[known.reserved_room_type.eq(room).fillna(False)]
            prior = room_known.groupby('full_date').total_guests.agg(['sum', 'count'])
            prior = prior.reindex(pd.DatetimeIndex(frame.full_date), fill_value=0).cumsum().shift(1, fill_value=0)
            n = prior['count'].reindex(group.full_date).to_numpy()
            mean = (prior['sum'] / prior['count'].where(prior['count'].ge(MIN_ROOM_BOOKINGS))).reindex(group.full_date).to_numpy(dtype=float)
            use_room = np.isfinite(mean)
            missing.loc[group.index, 'estimated_guests'] = np.where(use_room, mean, group.past_global_mean)
            missing.loc[group.index, 'room_known_count'] = n
            missing.loc[group.index, 'imputation_source'] = np.where(use_room, 'ROOM_MEAN', 'GLOBAL_MEAN')
        return missing

    def causal_history(self, frame, booking_frame=None):
        missing = self.causal_room_estimates(frame, booking_frame)
        additions = missing.groupby('full_date').estimated_guests.sum(min_count=1)
        added = frame.full_date.map(additions)
        series = frame.target_guests.astype(float).copy()
        mask = self.eligible_imputation(frame) & added.notna()
        series.loc[mask] = frame.loc[mask, 'observed_total_guests'].astype(float) + added.loc[mask]
        series.index = pd.DatetimeIndex(frame.full_date)
        return series

    def benchmark_labels(self, cutoff, end):
        return self.room_labels(cutoff, end)

    def past_features(self, series, asof):
        values = {}
        for lag in (0, 1, 2, 6, 7, 13, 14, 20, 27, 55, 83):
            values[f'past_lag_{lag}'] = series.reindex(asof - lag * DAY).to_numpy()
        for window in (7, 14, 28, 56, 84):
            roll = series.rolling(window, min_periods=3)
            statistics = {'mean': roll.mean(), 'median': roll.median(), 'std': roll.std(ddof=0), 'count': roll.count()}
            for name, stat in statistics.items():
                values[f'{name}_{window}'] = stat.reindex(asof).to_numpy()
        return values

    def weekday_offset(self, series, asof, target):
        residual = series - series.shift(1).rolling(14, min_periods=7).mean()
        offset = np.zeros(len(target))
        for weekday in range(7):
            r = residual.where(series.index.day_of_week == weekday)
            n = r.rolling(56, min_periods=1).count().reindex(asof).to_numpy()
            mean = r.rolling(56, min_periods=1).mean().reindex(asof).fillna(0).to_numpy()
            mask = target.day_of_week == weekday
            offset[mask] = (mean * n / (n + 4))[mask]
        return offset

    def seasonal_features(self, series, asof, target):
        values = {}
        for weeks in (4, 8, 12):
            past = []
            for k in range(1, weeks + 1):
                date = target - 7 * k * DAY
                values_at_date = series.reindex(date).to_numpy(copy=True)
                values_at_date[date > asof] = np.nan
                past.append(values_at_date)
            seasonal = pd.DataFrame(np.array(past).T)
            values[f'same_weekday_mean_{weeks}w'] = seasonal.mean(axis=1).to_numpy()
            values[f'same_weekday_median_{weeks}w'] = seasonal.median(axis=1).to_numpy()
        return values

    def features(self, series, pairs):
        asof = pd.DatetimeIndex(pairs.origin - DELAY * DAY)
        target = pd.DatetimeIndex(pairs.target_date)
        values = self.past_features(series, asof)
        offset = self.weekday_offset(series, asof, target)
        values['anchor'] = values['mean_14'] + offset
        values['weekday_offset'] = offset
        values.update(self.seasonal_features(series, asof, target))
        values['recent_level_change'] = values['mean_7'] - values['mean_28']
        values['horizon'] = pairs.horizon.to_numpy()
        for weekday in range(1, 7):
            values[f'target_weekday_{weekday}'] = (target.day_of_week == weekday).astype(float)
        values['target_month_sin'] = np.sin(2 * np.pi * (target.month - 1) / 12)
        values['target_month_cos'] = np.cos(2 * np.pi * (target.month - 1) / 12)
        values['target_year_sin'] = np.sin(2 * np.pi * (target.day_of_year - 1) / 365.25)
        values['target_year_cos'] = np.cos(2 * np.pi * (target.day_of_year - 1) / 365.25)
        values['target_month_start'] = target.is_month_start.astype(float)
        values['target_month_end'] = target.is_month_end.astype(float)
        return pd.DataFrame(values, index=pairs.index, dtype=float)

    def holt_prediction(self, series, pairs, config):
        series = series.loc[:pairs.origin.max() - DELAY * DAY]
        seed = series.iloc[:28].dropna()
        level, trend = (float(seed.mean()), 0.0)
        season = np.array([float(seed[seed.index.day_of_week == w].mean() - level) for w in range(7)])
        alpha, beta, gamma, phi = (config[k] for k in ('alpha', 'beta', 'gamma', 'phi'))
        states = {series.index[27]: (level, trend, season.copy())}
        for date, actual in series.iloc[28:].items():
            w, previous = (date.day_of_week, level)
            if pd.notna(actual):
                level = alpha * (actual - season[w]) + (1 - alpha) * (level + phi * trend)
                trend = beta * (level - previous) + (1 - beta) * phi * trend
                season[w] = gamma * (actual - level) + (1 - gamma) * season[w]
            else:
                level, trend = (level + phi * trend, phi * trend)
            states[date] = (level, trend, season.copy())
        result = []
        for row in pairs.itertuples(index=False):
            level, trend, seasonal = states[row.origin - DELAY * DAY]
            steps = row.horizon + DELAY
            damped = phi * (1 - phi ** steps) / (1 - phi)
            result.append(max(0.0, level + damped * trend + seasonal[row.target_date.day_of_week]))
        return np.array(result)

    def make_model(self, name, config):
        if name == 'A2_residual_histgb':
            estimator = HistGradientBoostingRegressor(loss='absolute_error', max_iter=200, learning_rate=0.05, min_samples_leaf=28, l2_regularization=5.0, early_stopping=False, random_state=42, **config)
        else:
            estimator = ExtraTreesRegressor(n_estimators=100, criterion='absolute_error', max_depth=8, max_features=0.8, random_state=42, n_jobs=1, **config)
        return make_pipeline(SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True), estimator)

    def training_data(self, cutoff):
        labels, imputer = self.benchmark_labels(cutoff, cutoff)
        pairs = self.schedule(TRAIN_START + 29 * DAY, pd.Timestamp(cutoff))
        x = self.features(self.HISTORY, pairs)
        y = labels.set_index('full_date').target_estimated.reindex(pd.DatetimeIndex(pairs.target_date)).to_numpy()
        mask = np.isfinite(y) & np.isfinite(x.anchor.to_numpy())
        return (pairs.loc[mask].reset_index(drop=True), x.loc[mask].reset_index(drop=True), y[mask], imputer)

    def fit_ml(self, name, config, cutoff, data):
        pairs, x, y, _ = data
        weight = np.exp2(-(pd.Timestamp(cutoff) - pairs.target_date).dt.days.to_numpy() / RECENCY_HALF_LIFE)
        model = self.make_model(name, config)
        with threadpool_limits(limits=1):
            model.fit(x, y - x.anchor.to_numpy(), **{model.steps[-1][0] + '__sample_weight': weight})
        return model

    def predict_ml(self, model, x):
        with threadpool_limits(limits=1):
            return np.maximum(0.0, x.anchor.to_numpy() + model.predict(x))

    def inner_search(self, cutoff):
        inner_start = cutoff - (INNER_DAYS - 1) * DAY
        inner_cutoff = inner_start - (1 + DELAY) * DAY
        pairs = self.schedule(inner_start, cutoff)
        labels, _ = self.benchmark_labels(inner_cutoff, cutoff)
        actual = labels.set_index('full_date').target_estimated.reindex(pd.DatetimeIndex(pairs.target_date)).to_numpy()
        x, train = (self.features(self.HISTORY, pairs), self.training_data(inner_cutoff))
        rows, chosen = ([], {})
        for name in METHODS:
            best = np.inf
            for config in GRIDS[name]:
                if name == 'A1_holt_winters':
                    predicted = self.holt_prediction(self.HISTORY, pairs, config)
                else:
                    predicted = self.predict_ml(self.fit_ml(name, config, inner_cutoff, train), x)
                mask = np.isfinite(actual)
                mae = float(np.abs(predicted[mask] - actual[mask]).mean())
                rows.append({'model': name, 'config': json.dumps(config), 'inner_MAE': mae, 'train_cutoff': inner_cutoff, 'eval_start': inner_start, 'eval_end': cutoff})
                if mae < best:
                    best, chosen[name] = (mae, config)
        return (chosen, pd.DataFrame(rows))

    def train_bundle(self, fold):
        first_origin = pd.Timestamp(fold['eval_start']) - DAY
        cutoff = first_origin - DELAY * DAY
        selected, search = self.inner_search(cutoff)
        data = self.training_data(cutoff)
        pairs, x, y, imputer = data
        models = {name: self.fit_ml(name, selected[name], cutoff, data) for name in METHODS[1:]}
        residual = y - x.mean_14.to_numpy()
        correction = np.zeros((7, 7))
        for h in HORIZONS:
            for weekday in range(7):
                mask = pairs.horizon.eq(h) & pairs.target_date.dt.day_of_week.eq(weekday)
                correction[h - 1, weekday] = residual[mask].sum() / (int(mask.sum()) + 10)
        assert pairs.target_date.add(DELAY * DAY).le(first_origin).all()
        labels, _ = self.benchmark_labels(cutoff, fold['eval_end'])
        self.save_csv(fold['fold'] + '_inner_search.csv', search)
        self.save_csv(fold['fold'] + '_training.csv', pd.concat([pairs, x, pd.Series(y, name='training_target')], axis=1))
        self.save_json(fold['fold'] + '_configuration.json', {'selected': selected, 'imputer': imputer})
        self.save_room_imputation(fold['fold'], imputer, fold['eval_end'])
        self.save_csv(fold['fold'] + '_labels.csv', labels)
        print(f"{fold['fold']}: train đến {cutoff.date()}, inner choices {selected}")
        return {'fold': fold, 'cutoff': cutoff, 'selected': selected, 'models': models, 'labels': labels, 'correction': correction}

    def score_groups(self, predictions, by_horizon=False):
        rows = []
        keys = ['fold', 'variant', 'model'] + (['horizon'] if by_horizon else [])
        for group_key, frame in predictions.groupby(keys):
            populations = {'ALL_ESTIMATED': frame.target_estimated.notna(), 'COMPLETE_ONLY': frame.target_true.notna(), 'IMPUTED_ONLY': frame.target_is_imputed}
            for population, mask in populations.items():
                q = frame.loc[mask]
                actual = q.target_true if population == 'COMPLETE_ONLY' else q.target_estimated
                errors = q.y_pred - actual
                n = len(q)
                total = float(actual.sum())
                rows.append({**dict(zip(keys, group_key)), 'population': population, 'scheduled_n': len(frame), 'scorable_n': n, 'unique_dates': q.target_date.nunique(), 'coverage': float(q.y_pred.notna().mean()) if n else np.nan, 'MAE': float(errors.abs().mean()) if n else np.nan, 'RMSE': float(np.sqrt((errors ** 2).mean())) if n else np.nan, 'WAPE': float(errors.abs().sum() / total) if total > 0 else np.nan, 'signed_bias': float(errors.mean()) if n else np.nan})
        return pd.DataFrame(rows)

    def attach_truth(self, raw, labels):
        columns = ['full_date', 'target_true', 'target_estimated', 'target_is_imputed']
        result = raw.merge(labels[columns], left_on='target_date', right_on='full_date', how='left', validate='many_to_one')
        return result

    def select_model(self, scores, order):
        best = scores.min()
        return next((name for name in order if scores.loc[name] <= best * 1.01 + 1e-12))

    def forecast_bundle(self, bundle, history=None, pairs=None):
        if history is None:
            history = self.HISTORY
        fold = bundle['fold']
        if pairs is None:
            pairs = self.schedule(fold['eval_start'], fold['eval_end'])
        x = self.features(history, pairs)
        predictions = {'A1_holt_winters': self.holt_prediction(history, pairs, bundle['selected']['A1_holt_winters'])}
        for name, model in bundle['models'].items():
            predictions[name] = self.predict_ml(model, x)
        adjustment = np.array([bundle['correction'][row.horizon - 1, row.target_date.day_of_week] for row in pairs.itertuples(index=False)])
        predictions['B4_matched'] = np.maximum(0.0, x.mean_14.to_numpy() + adjustment)
        parts = []
        for name in ORDER:
            part = pairs.copy()
            part['model'], part['y_pred'] = (name, predictions[name])
            part['fold'], part['variant'] = (fold['fold'], 'causal_history')
            part['latest_label_date'] = part.origin - DELAY * DAY
            part['fit_label_cutoff'] = bundle['cutoff']
            parts.append(part)
        out = pd.concat(parts, ignore_index=True)
        return out
