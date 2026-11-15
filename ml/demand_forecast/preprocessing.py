"""Instance-scoped immutable experiment inputs and optional evidence output."""
import json
from pathlib import Path
from functools import cached_property


class ExperimentData:
    def __init__(self, daily, bookings, output=None):
        self.daily = daily.copy()
        self.bookings = bookings.copy()
        self.valid = self.bookings[self.bookings.is_canceled.eq(0) & self.bookings.guest_eligible].copy()
        self.output = Path(output) if output else None
        if self.output:
            self.output.mkdir(parents=True, exist_ok=True)

    @cached_property
    def HISTORY(self):
        # Only the causal experiment defines causal_history. Callers bound inputs
        # to their availability cutoff before constructing the serving instance.
        return self.causal_history(self.daily)

    def save_json(self, name, value):
        if self.output:
            with (self.output / name).open('x', encoding='utf-8') as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2, default=str)

    def save_csv(self, name, frame):
        if self.output:
            frame.to_csv(self.output / name, index=False, float_format='%.12g', lineterminator='\n')
