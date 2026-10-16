"""Desktop - Static desktop home screen."""

class PicowareAnimation:
    """Class to draw "Picoware" animation"""

    def __init__(self, draw):
        """Initialize the Picoware animation.

        Args:
            draw (Draw): The drawing context.
        """
        from picoware.system.boards import BOARD_FLIPPER_ZERO, BOARD_ID, BOARD_POOM
        self.display = draw
        self.letter_states = []
        self.animation_complete = False
        self.circle_radius = 0
        self.circle_max_radius = 80
        self.circle_opacity = 100
        self.size = self.display.size
        self.center_x = self.size.x // 2
        self.center_y = self.size.y // 2
        self.frame_counter = 0

        self._color = 0xFFFF if BOARD_ID in (BOARD_FLIPPER_ZERO, BOARD_POOM) else 0x4208

        self._initialize_letter_animation()

    def __del__(self):
        """Clean up the letter animation state."""
        del self.letter_states
        self.letter_states = None

    def _initialize_letter_animation(self) -> None:
        """Initialize the animation state for each letter in 'Picoware'."""
        from picoware.system.boards import BOARD_FLIPPER_ZERO, BOARD_ID, BOARD_POOM
        from picoware.system.colors import (
            TFT_RED,
            TFT_GREEN,
            TFT_BLUE,
            TFT_YELLOW,
            TFT_VIOLET,
            TFT_CYAN,
            TFT_ORANGE,
            TFT_PINK,
            TFT_SKYBLUE,
        )

        self.letter_states = []

        text = "Picoware"
        self.letter_states = []
        self.circle_opacity = 100

        # Calculate target position (center of screen)
        char_width = self.display.font_size.x
        total_width = len(text) * char_width
        target_y = self.center_y
        start_x = (self.size.x - total_width) // 2

        # Color palette (RGB565 format)
        colors = [
            TFT_RED,
            TFT_GREEN,
            TFT_BLUE,
            TFT_YELLOW,
            TFT_VIOLET,
            TFT_CYAN,
            TFT_ORANGE,
            TFT_PINK,
            TFT_SKYBLUE,
        ]

        # Different starting Y positions and delays for each letter
        from random import randint, choice

        for i, char in enumerate(text):
            letter_state = {
                "char": char,
                "target_x": start_x + (i * char_width),
                "target_y": target_y,
                "current_y": target_y + randint(-80, -40),  # Start above target
                "delay": i * 3,  # Staggered start times
                "frame": 0,
                "opacity": 0,  # Start invisible (0-100 scale)
                "color": 0xFFFF if BOARD_ID in (BOARD_FLIPPER_ZERO, BOARD_POOM) else choice(colors),  # Random color for each letter (white for Flipper Zero/Poom)
            }
            self.letter_states.append(letter_state)

    def draw(self) -> None:
        """Draw the animated 'Picoware' text."""

        # Draw background animations
        if self.circle_radius < self.circle_max_radius:
            self.circle_radius += 2
        else:
            # Reset for continuous animation
            self.circle_radius = 0
            self.circle_opacity = 100

        # Fade out as it expands
        if self.circle_radius > self.circle_max_radius // 2:
            self.circle_opacity = max(0, self.circle_opacity - 3)

        # Draw circle with fade effect
        if self.circle_opacity > 20:  # Only draw if visible enough

            # Draw if opacity threshold is met
            if (
                self.frame_counter % max(1, (100 - self.circle_opacity) // 20 + 1)
            ) == 0:
                self.display._circle(
                    self.center_x, self.center_y, self.circle_radius, self._color
                )

        all_settled = True

        for letter in self.letter_states:
            # Handle delay before letter starts moving
            if letter["frame"] < letter["delay"]:
                letter["frame"] += 1
                all_settled = False
                continue

            # Animate Y position (ease-out effect)
            if letter["current_y"] > letter["target_y"]:
                diff = letter["current_y"] - letter["target_y"]
                letter["current_y"] -= max(1, diff // 4)  # Ease-out
                all_settled = False
            else:
                letter["current_y"] = letter["target_y"]

            # Fade in opacity (0-100 scale)
            if letter["opacity"] < 100:
                letter["opacity"] = min(100, letter["opacity"] + 5)
                all_settled = False

            # Draw the letter with fade effect
            if letter["opacity"] > 0:
                # Higher opacity = more solid appearance
                opacity_threshold = 100 - letter["opacity"]

                # Use modulo to create a fade pattern
                # At low opacity, only draw occasionally; at high opacity, always draw
                if (self.frame_counter % max(1, opacity_threshold // 10 + 1)) == 0:
                    self.display._text(
                        letter["target_x"],
                        int(letter["current_y"]),
                        letter["char"],
                        letter["color"],
                    )

            letter["frame"] += 1

        self.animation_complete = all_settled
        self.frame_counter += 1


_desktop = None
_desktop_status = None
_desktop_visual = None
_has_wifi = True
_dashboard = None
_dashboard_state = None


def start(view_manager):
    """Open the custom home screen and reconnect to saved Wi-Fi."""
    from picoware.gui.desktop import Desktop
    from picoware.gui.home_visual import HomeVisual
    global _desktop, _desktop_status, _desktop_visual, _has_wifi, _dashboard
    _desktop = Desktop(view_manager.draw, view_manager.foreground_color,
                       view_manager.background_color)
    _desktop_status = None
    _desktop_visual = HomeVisual()
    if (view_manager.draw.size.x,view_manager.draw.size.y)==(320,320):
        from picoware.gui.dashboard import Dashboard
        _dashboard=Dashboard(view_manager,_dashboard_state)
        _desktop_visual=None
    _has_wifi = view_manager.has_wifi
    if _has_wifi:
        from picoware.applications.wifi.utils import connect_to_saved_wifi
        connect_to_saved_wifi(view_manager)
    return True


def run(view_manager):
    """Update home status and time; handle navigation."""
    from picoware.system.buttons import BUTTON_LEFT, BUTTON_CENTER, BUTTON_UP
    from picoware.system.view import View
    global _desktop_status
    if _dashboard is not None:
        _dashboard.update()
        if view_manager.has_wifi:
            wifi=view_manager.wifi
            if not wifi.is_connected() and wifi.state in (0,4):
                from picoware.applications.wifi.utils import connect_to_saved_wifi
                connect_to_saved_wifi(view_manager)
            elif wifi.is_connected() and not view_manager.time.is_set and not view_manager.time.is_fetching:
                view_manager.time.fetch(view_manager.gmt_offset)
        if not _dashboard or not _dashboard.dirty:
            from time import sleep_ms
            sleep_ms(10)
        return
    button = view_manager.button
    if button == BUTTON_LEFT:
        from picoware.applications.system import system_info
        view_manager.add(View("system_info", system_info.run, system_info.start, system_info.stop))
        view_manager.switch_to("system_info")
        return
    if button == BUTTON_CENTER:
        from picoware.applications import library
        view_manager.add(View("library", library.run, library.start, library.stop))
        view_manager.switch_to("library")
        return
    if button == BUTTON_UP:
        from picoware.applications import notifications
        view_manager.add(View("notifications", notifications.run, notifications.start, notifications.stop))
        view_manager.switch_to("notifications")
        return

    battery_level: int = view_manager.battery.percentage
    is_connected = _has_wifi and view_manager.wifi.is_connected()
    current = view_manager.time.rtc.datetime() if view_manager.time.is_set else None
    clock_state = current[:6] if current is not None else None
    if current is not None:
        _desktop.set_time("%02d:%02d" % (current[4], current[5]))
    else:
        _desktop.set_time("")
    status = (battery_level, is_connected, clock_state,
              view_manager.foreground_color, view_manager.background_color)
    if status != _desktop_status:
        _desktop.set_battery(battery_level)
        draw = view_manager.draw
        draw.erase()
        _desktop.text_color = view_manager.foreground_color
        _desktop.background_color = view_manager.background_color
        _desktop.is_dark_mode = view_manager.foreground_color == 0xFFFF and view_manager.background_color == 0
        _desktop.draw_header(is_connected)
        _desktop_visual.draw(draw, current, view_manager.foreground_color, view_manager.background_color)
        draw.swap()
        _desktop_status = status
    else:
        from time import sleep_ms

        sleep_ms(10)

    if not _has_wifi:
        return
    wifi = view_manager.wifi
    if not wifi.is_connected():
        if wifi.state in (0, 4):
            from picoware.applications.wifi.utils import connect_to_saved_wifi
            connect_to_saved_wifi(view_manager)
    elif not view_manager.time.is_set and not view_manager.time.is_fetching:
        view_manager.time.fetch(view_manager.gmt_offset)


def stop(view_manager):
    """Release home drawing data when entering a menu."""
    from gc import collect
    global _desktop, _desktop_status, _desktop_visual, _has_wifi, _dashboard, _dashboard_state
    if _dashboard is not None:
        _dashboard_state=(_dashboard.category,_dashboard.indices[:])
        _dashboard.stop()
        _dashboard=None
    _desktop = None
    _desktop_status = None
    _desktop_visual = None
    _has_wifi = True
    collect()
