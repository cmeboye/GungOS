"""Beam Lab engineering model placeholder. No numerical results yet.
"""

TOOL = {'id': 'beams', 'title': 'Beam Lab', 'description': 'Simple beam supports, loads and material properties.', 'status': 'planned', 'inputs': (), 'planned_outputs': ('Support reactions', 'Shear and moment diagrams', 'Deflection curves')}


def validate(parameters):
    """Check model inputs and assumptions."""
    raise NotImplementedError("Beam Lab is not implemented yet")


def solve(parameters, job=None):
    """Calculate model results independently of the display."""
    raise NotImplementedError("Beam Lab is not implemented yet")


def build_plots(result):
    """Convert a valid calculation result into plot specifications."""
    raise NotImplementedError("Beam Lab is not implemented yet")
