"""Notebook-equivalent experiment logic; extracted definitions, with instance-scoped input data.

Source: notebooks/experiments/history_demand_imputed_3fold_report.ipynb. No notebook executes at serving time.
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
HORIZONS = tuple(range(1, 8))
DELAY = 0
DEV_END = pd.Timestamp('2017-05-31')
MODELS = ('B0_mean', 'B1_seasonal', 'B2_ma7', 'B3_ma14', 'B4_weekday')
ML_MODELS = ('M0_linear', 'M1_ridge', 'M2_random_forest', 'M3_extra_trees', 'M4_hist_gb')
VARIANTS = ('canonical_history', 'imputed_history')
POLICY = {'warmup_days': 28, 'correction_lambda': 10, 'seed': SEED}
MIN_ROOM_BOOKINGS = 30
IMPUTATION_POLICY = {'method': 'room_type_mean', 'group_column': 'reserved_room_type', 'min_room_bookings': MIN_ROOM_BOOKINGS, 'fallback': 'train_global_mean'}
ML_CONFIG = {'M0_linear': {}, 'M1_ridge': {'alpha': 10.0}, 'M2_random_forest': {'n_estimators': 150, 'max_depth': 8, 'min_samples_leaf': 5, 'max_features': 1.0, 'random_state': SEED, 'n_jobs': 1}, 'M3_extra_trees': {'n_estimators': 150, 'max_depth': 10, 'min_samples_leaf': 5, 'max_features': 1.0, 'random_state': SEED, 'n_jobs': 1}, 'M4_hist_gb': {'max_iter': 200, 'learning_rate': 0.05, 'max_leaf_nodes': 15, 'min_samples_leaf': 15, 'l2_regularization': 1.0, 'early_stopping': False, 'random_state': SEED}}

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

    def fold_labels(self, fold):
        return self.room_labels(fold['train_end'], fold['eval_end'])

    def history_stats(self, series):
        result = pd.DataFrame(index=series.index)
        for size in (7, 14, 28):
            result[f'n{size}'] = series.rolling(size, min_periods=1).count()
            result[f'm{size}'] = series.rolling(size, min_periods=1).mean()
        return result

    def reference(self, series, cutoff):
        known = series.loc[:cutoff].dropna()
        by_weekday = known.groupby(known.index.day_of_week).mean()
        return {'global_mean': float(known.mean()), 'weekday_mean': [float(by_weekday.get(w, known.mean())) for w in range(7)]}

    def ml_features(self, series, pairs):
        """Build features using history through origin and known target-date calendar only."""
        origin = pd.DatetimeIndex(pairs.origin)
        target = pd.DatetimeIndex(pairs.target_date)
        values = {}
        for lag in (0, 1, 2, 6, 7, 13, 14, 20, 27):
            values[f'y_origin_minus_{lag}'] = series.reindex(origin - lag * DAY).to_numpy()
        for size in (7, 14, 28):
            window = series.rolling(size, min_periods=1)
            for name, stat in (('mean', window.mean()), ('std', window.std(ddof=0)), ('count', window.count())):
                values[f'{name}_{size}'] = stat.reindex(origin).to_numpy()
        for lag in (7, 14, 28):
            history_date = target - lag * DAY
            values[f'target_lag_{lag}'] = series.reindex(history_date).to_numpy()
        for weekday in range(1, 7):
            values[f'target_weekday_{weekday}'] = (target.day_of_week == weekday).astype(float)
        phase = 2 * np.pi * (target.day_of_year - 1) / 365.25
        values['target_year_sin'] = np.sin(phase)
        values['target_year_cos'] = np.cos(phase)
        values['target_trend_days'] = (target - TRAIN_START).days.astype(float)
        return pd.DataFrame(values, index=pairs.index, dtype=float)

    def make_ml_model(self, name):
        estimators = {'M0_linear': LinearRegression, 'M1_ridge': Ridge, 'M2_random_forest': RandomForestRegressor, 'M3_extra_trees': ExtraTreesRegressor, 'M4_hist_gb': HistGradientBoostingRegressor}
        steps = [SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True)]
        if name in ('M0_linear', 'M1_ridge'):
            steps.append(StandardScaler())
        return make_pipeline(*steps, estimators[name](**ML_CONFIG[name]))

    def moving_average(self, series, stats, origin, model, weekday, ref):
        windows = [(7, 4), (14, 7), (28, 10)] if model == 'B2_ma7' else [(14, 7), (28, 10)]
        for size, minimum in windows:
            if stats.at[origin, f'n{size}'] >= minimum:
                return (float(stats.at[origin, f'm{size}']), f'MA{size}')
        return (ref['weekday_mean'][weekday], 'TRAIN_WEEKDAY_MEAN')

    def baseline(self, model, series, stats, origin, horizon, ref, correction=None):
        target = origin + horizon * DAY
        weekday = target.day_of_week
        if model == 'B0_mean':
            return (ref['global_mean'], 'TRAIN_MEAN')
        if model == 'B1_seasonal':
            for lag in (7, 14, 21, 28):
                value = series.get(target - lag * DAY, np.nan)
                if pd.notna(value):
                    return (float(value), f'LAG{lag}')
            return (ref['weekday_mean'][weekday], 'TRAIN_WEEKDAY_MEAN')
        value, rule = self.moving_average(series, stats, origin, model, weekday, ref)
        if model == 'B4_weekday':
            value += correction[horizon - 1][weekday]
            rule += '+CORRECTION'
        return (max(0.0, float(value)), rule)

    def fit_baseline(self, series, stats, cutoff):
        cutoff = pd.Timestamp(cutoff)
        ref = self.reference(series, cutoff)
        rows = []
        for origin in pd.date_range(TRAIN_START + POLICY['warmup_days'] * DAY, cutoff - 7 * DAY):
            causal_ref = self.reference(series, origin)
            for h in HORIZONS:
                target = origin + h * DAY
                actual = series.at[target]
                if pd.isna(actual):
                    continue
                base, _ = self.baseline('B3_ma14', series, stats, origin, h, causal_ref)
                rows.append({'origin': origin, 'horizon': h, 'target_date': target, 'weekday': target.day_of_week, 'residual': float(actual) - base})
        residuals = pd.DataFrame(rows)
        correction = np.zeros((7, 7))
        for h in HORIZONS:
            for w in range(7):
                r = residuals.loc[(residuals.horizon == h) & (residuals.weekday == w), 'residual']
                correction[h - 1, w] = float(r.sum() / (len(r) + POLICY['correction_lambda']))
        return ({'reference': ref, 'correction': correction.tolist(), 'fit_end': str(cutoff.date())}, residuals)

    def fit_direct_models(self, series, pairs):
        x = self.ml_features(series, pairs)
        y = series.reindex(pd.DatetimeIndex(pairs.target_date)).to_numpy()
        fitted = {name: {} for name in ML_MODELS}
        with threadpool_limits(limits=1):
            for horizon in HORIZONS:
                mask = pairs.horizon.eq(horizon).to_numpy() & np.isfinite(y)
                for name in ML_MODELS:
                    model = self.make_ml_model(name)
                    model.fit(x.loc[mask], y[mask])
                    fitted[name][horizon] = model
        return (fitted, x)

    def train_fold(self, fold):
        cutoff = pd.Timestamp(fold['train_end'])
        labels, imputer = self.fold_labels(fold)
        indexed = labels.set_index('full_date')
        pairs = self.schedule(TRAIN_START + 29 * DAY, cutoff)
        assert pairs.target_date.le(cutoff).all()
        states = {}
        for variant, column in zip(VARIANTS, ('target_true', 'target_estimated')):
            series = indexed[column]
            stats = self.history_stats(series)
            params, _ = self.fit_baseline(series, stats, cutoff)
            fitted, x = self.fit_direct_models(series, pairs)
            states[variant] = {'series': series, 'stats': stats, 'params': params, 'models': fitted}
            self.save_csv(f"{fold['fold']}_{variant}_train.csv", pd.concat([pairs, x], axis=1))
        self.save_room_imputation(fold['fold'], imputer, fold['eval_end'])
        self.save_csv(f"{fold['fold']}_labels.csv", labels)
        print(f"{fold['fold']}: train đến {cutoff.date()}, bù theo phòng, mean fallback {imputer['mu_train']:.6f}")
        return {'fold': fold, 'labels': labels, 'states': states, 'imputer': imputer}

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

    def forecast_fold(self, state):
        pairs = self.schedule(state['fold']['eval_start'], state['fold']['eval_end'])
        rows = []
        for variant, data in state['states'].items():
            for pair in pairs.itertuples(index=False):
                for name in MODELS:
                    value, _ = self.baseline(name, data['series'], data['stats'], pair.origin, pair.horizon, data['params']['reference'], data['params']['correction'])
                    rows.append({**pair._asdict(), 'variant': variant, 'model': name, 'y_pred': value})
            x = self.ml_features(data['series'], pairs)
            with threadpool_limits(limits=1):
                for name in ML_MODELS:
                    for h in HORIZONS:
                        mask = pairs.horizon.eq(h)
                        values = data['models'][name][h].predict(x.loc[mask])
                        for pair, value in zip(pairs.loc[mask].itertuples(index=False), values):
                            rows.append({**pair._asdict(), 'variant': variant, 'model': name, 'y_pred': max(0.0, value)})
        raw = pd.DataFrame(rows).assign(fold=state['fold']['fold'])
        return raw
