"""Training-only preprocessing and deterministic, modest demand candidates."""
from datetime import date
import json
from pathlib import Path
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .artifacts import make_bundle
from .contracts import CALENDAR_FEATURES, FEATURE_SPECS, DemandError, feature_spec

DEFAULT_CONFIG = Path(__file__).with_name("config.json")

def load_config(path=DEFAULT_CONFIG):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_config(config)
    return config

def validate_config(config):
    if config.get("contract_version") != "demand-contract-v1" or config.get("feature_version") not in FEATURE_SPECS:
        raise DemandError("INVALID_CONFIG", "Unsupported contract/feature version")
    if set(config.get("models",{})) != {"linear_regression","random_forest","xgboost"}:
        raise DemandError("INVALID_CONFIG", "All three required regression candidates must be configured")
    if set(config.get("splits",{})) != {"train","validation","test"}:
        raise DemandError("INVALID_CONFIG", "Train, validation and test partitions required")
    prior = None
    for name in ("train","validation","test"):
        split = config["splits"][name]
        start, end = date.fromisoformat(split["start"]), date.fromisoformat(split["end"])
        if start > end or (prior is not None and start <= prior):
            raise DemandError("INVALID_CONFIG", "Partitions must be ordered and non-overlapping")
        prior = end
    for key in ("min_train_rows","min_validation_origins","min_test_origins"):
        if type(config.get(key)) is not int or config[key] < 1:
            raise DemandError("INVALID_CONFIG", f"{key} must be a positive integer")
    improvement = config.get("min_relative_mae_improvement")
    if not isinstance(improvement,(float,int)) or not 0 <= improvement < 1:
        raise DemandError("INVALID_CONFIG", "Improvement threshold must be in [0,1)")
    if type(config.get("seed")) is not int:
        raise DemandError("INVALID_CONFIG", "An integer seed is required")

def candidate_pipeline(name, config):
    params = config["models"][name].copy()
    if name == "linear_regression":
        estimator = LinearRegression(**params)
    elif name == "random_forest":
        estimator = RandomForestRegressor(random_state=config["seed"], n_jobs=1, **params)
    elif name == "xgboost":
        from xgboost import XGBRegressor
        estimator = XGBRegressor(objective="reg:squarederror", tree_method="hist",
                                 random_state=config["seed"], n_jobs=1, **params)
    else:
        raise DemandError("UNKNOWN_MODEL", name)
    spec = feature_spec(config["feature_version"])
    continuous = [name for name in spec.names if name not in CALENDAR_FEATURES]
    categorical = list(CALENDAR_FEATURES)
    preprocessing = ColumnTransformer([
        ("history", StandardScaler(), continuous),
        ("calendar", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical),
    ])
    return Pipeline([("preprocessing",preprocessing),("regression",estimator)])

def training_rows(features, start, end):
    return features.loc[features["train_ready"] & features.full_date.between(start,end)].copy()

def fit_candidate(name, snapshot, features, start, end, config, model_version, *, eligible_dates=None):
    spec = feature_spec(config["feature_version"])
    if (features.attrs.get("data_version") != snapshot.data_version
            or features.attrs.get("feature_version") != spec.version
            or features.attrs.get("snapshot_hash") != snapshot.snapshot_hash):
        raise DemandError("STALE_FEATURES", "Feature table does not match the pinned snapshot/specification")
    rows = training_rows(features,start,end)
    if eligible_dates is not None:
        requested = set(eligible_dates)
        if not requested <= set(rows.full_date):
            raise DemandError("INVALID_TRAINING_SUBSET", "Controlled subset must contain only eligible training dates")
        rows = rows.loc[rows.full_date.isin(requested)].copy()
    if len(rows) < config["min_train_rows"]:
        raise DemandError("INSUFFICIENT_TRAINING_DATA", f"Only {len(rows)} eligible training rows")
    estimator = candidate_pipeline(name,config)
    estimator.fit(rows.loc[:,list(spec.names)].astype(float),rows.target_guests.to_numpy(dtype=float))
    return make_bundle(snapshot,name,end,model_version,estimator=estimator,
                       feature_version=spec.version,
                       parameters={"seed":config["seed"],**config["models"][name]},
                       metadata={"train_rows":len(rows),"training_start":str(start)})
