"""Decorators for feature availability checks on the PicoCalc with a Pico 2 W.

Audio, PSRAM, SD, Bluetooth, the keyboard and Wi-Fi are built in.
Infrared is excluded from this release; its legacy decorators report it as
unavailable for compatibility with SD applications.
"""

import sys


def _available(func: callable) -> callable:
    """Return the function unchanged: its hardware is always present."""
    return func


def _unavailable(func: callable, feature: str) -> callable:
    """Return a stub that raises because the hardware is absent."""
    def unavailable(*args, **kwargs):
        """Raise an error because the feature is not available.

        Raises:
            RuntimeError: Always.
        """
        raise RuntimeError(f"{func.__name__} requires {feature}, which is not available")
    return unavailable


audio_required = _available
psram_required = _available
storage_required = _available
bluetooth_required = _available
keyboard_required = _available


def infrared_tx_required(func: callable) -> callable:
    """Reject legacy IR applications: no infrared driver is shipped."""
    return _unavailable(func, "infrared support (excluded from this release)")


def infrared_rx_required(func: callable) -> callable:
    """Reject legacy IR applications: no infrared driver is shipped."""
    return _unavailable(func, "infrared reception")


def native(func: callable) -> callable:
    """Decorator to wrap a function with micropython.native on the device.

    Args:
        func (callable): The function to decorate.

    Returns:
        callable: The function, wrapped with micropython.native on the RP2350.
    """
    if sys.platform in ("darwin", "linux", "win32"):
        return func
    from picoware.system.native import native_wrapper
    return native_wrapper(func)


def viper(func: callable) -> callable:
    """Decorator to wrap a function with micropython.viper on the device.

    Args:
        func (callable): The function to decorate.

    Returns:
        callable: The function, wrapped with micropython.viper on the RP2350.
    """
    if sys.platform in ("darwin", "linux", "win32"):
        return func
    try:
        from picoware.system.native import viper_wrapper
        return viper_wrapper(func)
    except Exception:
        return func


def wifi_required(func: callable) -> callable:
    """Decorator to require a Wi-Fi connection before calling a view function.

    Args:
        func (callable): The function to decorate; its first argument is the view manager.

    Returns:
        callable: The wrapped function.

    Raises:
        RuntimeError: If the decorated function is called without WiFi connected.
    """
    def wrapper(*args, **kwargs):
        """Connect to saved WiFi and call the wrapped function.

        Args:
            *args: Positional arguments passed to the wrapped function.
            **kwargs: Keyword arguments passed to the wrapped function.

        Returns:
            object: The result of the wrapped function.

        Raises:
            RuntimeError: If WiFi is not connected.
        """
        view_manager = args[0]
        wifi = view_manager.wifi
        if not wifi.is_connected():
            raise RuntimeError(f"{func.__name__} requires WiFi, but it is not connected yet.")
        from picoware.applications.wifi.utils import connect_to_saved_wifi
        connect_to_saved_wifi(args[0])
        return func(*args, **kwargs)
    return wrapper
