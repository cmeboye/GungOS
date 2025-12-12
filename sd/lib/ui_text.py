"""
ui_text.py – Shared ASCII art and UI text helpers for GungOS.
"""

# Simple splash to show during boot
BOOT_LOGO = [
    r"                                                     ",
    r"                                                     ",
    r"   .88888.                      .88888.  .d88888b    ",
    r"  d8'   `88                    d8'   `8b 88.    ``   ",
    r"  88             dP8888b..d888888     88 `Y88888b.   ",
    r"  88   YP888    888'  `888'  `888     88       `8b   ",
    r"  Y8.   .888.  .888    888.  .888.   .8P d8'   .8P   ",
    r"   `88888'`888888P'     `P`888P888888P'   Y88888P    ",
    r"                              .88oooooooooooooooooo  ",
    r"                        d888888P ooooooooooooooooo   ",
    r"                                                     ",
    r"   GungOS – PicoCalc terminal                        ",
]


def print_boot_logo():
    """Print the ASCII boot logo."""
    for line in BOOT_LOGO:
        print(line)

