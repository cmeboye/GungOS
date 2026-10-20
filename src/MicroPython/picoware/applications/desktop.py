"""Desktop - Dashboard home screen."""

_dashboard = None
_dashboard_state = None

# Saved Wi-Fi and the network clock are retried at most this often, not every
# frame: a try reads the saved network from SD and flash, or starts a network
# task. It matches the Wi-Fi connect timeout, so a timed-out try repeats at once.
RETRY_MS = 10000
_wifi_retry = None
_clock_retry = None


def _due(deadline, now):
    from time import ticks_diff
    return deadline is None or ticks_diff(now, deadline) >= 0


def start(view_manager):
    """Open the dashboard home screen and reconnect to saved Wi-Fi."""
    from picoware.gui.dashboard import Dashboard
    from picoware.applications.wifi.utils import connect_to_saved_wifi
    from time import ticks_ms, ticks_add
    global _dashboard, _wifi_retry
    # Closed SD apps give their code back before the widget loads.
    from picoware.system.app_loader import AppLoader
    AppLoader.release(view_manager)
    _dashboard = Dashboard(view_manager, _dashboard_state)
    if view_manager.has_wifi:
        _wifi_retry = ticks_add(ticks_ms(), RETRY_MS)
        connect_to_saved_wifi(view_manager)
    return True


def run(view_manager):
    """Update the dashboard; keep Wi-Fi and the clock in sync."""
    global _wifi_retry, _clock_retry
    _dashboard.update()
    if view_manager.has_wifi:
        from time import ticks_ms, ticks_add
        now = ticks_ms()
        wifi = view_manager.wifi
        if not wifi.is_connected():
            if wifi.state in (0, 4) and _due(_wifi_retry, now):
                _wifi_retry = ticks_add(now, RETRY_MS)
                from picoware.applications.wifi.utils import connect_to_saved_wifi
                connect_to_saved_wifi(view_manager)
        elif not view_manager.time.is_set and not view_manager.time.is_fetching and _due(_clock_retry, now):
            _clock_retry = ticks_add(now, RETRY_MS)
            view_manager.time.fetch(view_manager.gmt_offset)
    # update() may have opened another view, which releases the dashboard.
    if _dashboard is None or not _dashboard.dirty:
        from time import sleep_ms
        sleep_ms(10)


def stop(view_manager):
    """Release home drawing data when entering a menu."""
    from gc import collect
    global _dashboard, _dashboard_state
    if _dashboard is not None:
        _dashboard_state = (_dashboard.category, _dashboard.indices[:])
        _dashboard.stop()
        _dashboard = None
    collect()
