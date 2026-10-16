"""Control Systems engineering model placeholder. No numerical results yet.
"""

TOOL = {'id': 'controls', 'title': 'Control Systems', 'description': 'Transfer functions and dynamic responses.', 'status': 'planned', 'inputs': (), 'planned_outputs': ('Step response', 'Poles and zeros', 'Frequency response')}


def validate(parameters):
    """Check model inputs and assumptions."""
    raise NotImplementedError("Control Systems is not implemented yet")


def solve(parameters, job=None):
    """Calculate model results independently of the display."""
    raise NotImplementedError("Control Systems is not implemented yet")


def build_plots(result):
    """Convert a valid calculation result into plot specifications."""
    raise NotImplementedError("Control Systems is not implemented yet")
