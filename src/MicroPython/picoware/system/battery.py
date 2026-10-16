"""Battery - PicoCalc battery level from the keyboard southbridge."""


class Battery:
    """Battery information reported by the PicoCalc southbridge."""

    @property
    def percentage(self) -> int:
        """Returns the current battery level as a percentage (0-100)."""
        from picoware_southbridge import get_battery_percentage

        return get_battery_percentage()
