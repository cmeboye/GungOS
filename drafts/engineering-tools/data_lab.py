"""Data Lab engineering model placeholder. No numerical results yet.
"""

TOOL = {'id': 'data_lab', 'title': 'Data Lab', 'description': 'CSV measurements, statistics and curve fitting.', 'status': 'planned', 'inputs': (), 'planned_outputs': ('Measured points', 'Fitted curves and residuals', 'Statistics and CSV export')}


def validate(parameters):
    """Check model inputs and assumptions."""
    raise NotImplementedError("Data Lab is not implemented yet")


def solve(parameters, job=None):
    """Calculate model results independently of the display."""
    raise NotImplementedError("Data Lab is not implemented yet")


def build_plots(result):
    """Convert a valid calculation result into plot specifications."""
    raise NotImplementedError("Data Lab is not implemented yet")
