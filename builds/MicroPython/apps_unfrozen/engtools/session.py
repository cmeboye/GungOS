"""State PicoLAB tools keep while their code is unloaded.

PicoLAB unloads a tool's modules when you return to its menu, so a tool
stores what should survive (for example Beam view's model) here. This
module is tiny and lives as long as PicoLAB.
"""
kept = {}
