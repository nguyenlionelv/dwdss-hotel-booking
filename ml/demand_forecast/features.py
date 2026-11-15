"""Feature construction for each distinct notebook availability protocol."""
def build_features(experiment, series, pairs):
    builder = getattr(experiment, 'features', None) or experiment.ml_features
    return builder(series, pairs)
