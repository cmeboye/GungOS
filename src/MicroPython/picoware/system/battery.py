"""Battery - PicoCalc battery level from the keyboard southbridge."""


class Battery:
    """Battery information reported by the PicoCalc southbridge."""

    @property
    def percentage(self) -> int:
        """Returns the current battery level as a percentage (0-100)."""
        from picoware_southbridge import get_battery_percentage

        return get_battery_percentage()


    @property
    def is_charging(self) -> bool:
        """Read the PicoCalc southbridge charging flag when available."""
        try:
            from picoware_southbridge import is_battery_charging
            return bool(is_battery_charging())
        except (ImportError, OSError):
            return False
