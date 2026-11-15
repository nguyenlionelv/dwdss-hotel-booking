"""Optional tree worker count; statistical settings and random seeds stay unchanged."""
import os
from .causal import Experiment

class CausalExperiment(Experiment):
    def make_model(self, name, config):
        model = super().make_model(name, config)
        if name == 'A3_residual_extra_trees':
            model.steps[-1][1].set_params(n_jobs=int(os.getenv('DWDSS_TREE_JOBS', '1')))
        return model
