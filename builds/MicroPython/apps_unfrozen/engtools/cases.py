"""Versioned JSON case storage and streamed CSV export.

Scaffold only: public operations raise NotImplementedError until implemented.
"""

CASE_VERSION = 1
CASE_DIRECTORY = "picoware/engineering/cases"
EXPORT_DIRECTORY = "picoware/engineering/exports"


def save_case(storage, case_id, case):
    """Save reproducible inputs, units and settings; verify the write."""
    raise NotImplementedError("cases is a placeholder")


def load_case(storage, case_id):
    """Load and validate a versioned saved case."""
    raise NotImplementedError("cases is a placeholder")


def export_csv(storage, path, columns, rows):
    """Stream tabular results to a CSV file."""
    raise NotImplementedError("cases is a placeholder")
