"""Circuit Lab engineering model placeholder. No numerical results yet.
"""

TOOL = {'id': 'circuits', 'title': 'Circuit Lab', 'description': 'RC, RL and RLC models, impedances and filters.', 'status': 'planned', 'inputs': (), 'planned_outputs': ('Voltage/current curves', 'Frequency response', 'Named values with units')}


def validate(parameters):
    """Check model inputs and assumptions."""
    raise NotImplementedError("Circuit Lab is not implemented yet")


def solve(parameters, job=None):
    """Calculate model results independently of the display."""
    raise NotImplementedError("Circuit Lab is not implemented yet")


def build_plots(result):
    """Convert a valid calculation result into plot specifications."""
    raise NotImplementedError("Circuit Lab is not implemented yet")
