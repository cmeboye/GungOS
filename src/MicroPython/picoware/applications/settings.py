"""Settings - Configure device settings."""

from micropython import const

HELP = (
    "Settings:",
    "UP/DOWN\tchoose a setting",
    "ENTER\topen the chosen setting",
    "ESC\treturn; in a setting, cancel it",
    "Appearance:",
    "UP/DOWN\tchoose a colour role",
    "ENTER\tpick its colour",
    "F1\tsave all colours",
    "F2\treset to the default colours",
    "Colour picker:",
    "Arrows\tchoose a preset colour",
    "F2\ttype a custom #RRGGBB value",
    "LEFT/RIGHT\tmove the cursor in the value",
    "BACK / DEL\terase before the cursor",
    "ENTER\tuse the colour",
    "Date & Time:",
    "LEFT/RIGHT\tchoose a field",
    "UP/DOWN\tchange its value",
    "ENTER\tsave the date and time",
    "GMT offset:",
    "Type the hours from UTC; ENTER saves",
)

# Brightness is the only choice mode; drawing/keyboard preferences remain
# supported by Settings and ViewManager without exposing their old toggles.
STATE_SCREEN_BRIGHTNESS = const(0)

# modes
_MODE_APPEARANCE = const(19)
_MODE_MENU = const(0)
_MODE_CHOICE = const(2)
_MODE_TIME_MENU = const(3)
_MODE_DATE_PICKER = const(4)
_MODE_GMT_KEYBOARD = const(5)


_settings = None
_menu = None
_choice = None
_appearance = None
_time_menu = None
_date_picker = None
_view_manager = None
_mode = _MODE_MENU
_current_setting = 0
_gmt_save_requested = False
_resume_menu_label = None


def __config() -> tuple:
    """Get the configuration tuple for the current setting.

    Returns:
        tuple: The (menu label, json key, default value) tuples.
    """
    # (menu label, json key, default value)
    return (
        ("Screen Brightness", "screen_brightness", 100),
        ("Appearance", "appearance", None),
        ("Time", "time", None),
    )


def __open_appearance() -> None:
    """Edit an unsaved appearance draft; commit all roles together."""
    global _appearance, _mode
    from picoware.gui.appearance_editor import AppearanceEditor
    from picoware.gui.appearance import values
    _appearance = AppearanceEditor(_view_manager, values(_settings.settings))
    _appearance.draw()
    _mode = _MODE_APPEARANCE


def __open_choice_brightness() -> None:
    """Open a Choice sub-view for the screen brightness setting."""
    global _choice, _mode, _current_setting
    from picoware.gui.choice import Choice
    from picoware.system.vector import Vector

    _current_setting = STATE_SCREEN_BRIGHTNESS
    _brightness_options = [str(i) for i in range(10, 101, 10)]
    current_brightness = _settings.screen_brightness
    try:
        initial_index = _brightness_options.index(str(current_brightness))
    except ValueError:
        initial_index = len(_brightness_options) - 1

    draw = _view_manager.draw
    draw.erase()
    if _choice is not None:
        del _choice
        _choice = None

    _choice = Choice(
        draw,
        Vector(0, 0),
        draw.size,
        "Screen Brightness",
        _brightness_options,
        initial_index,
        _view_manager.foreground_color,
        _view_manager.background_color,
    )
    _choice.draw()
    _mode = _MODE_CHOICE


def __open_time_menu() -> None:
    """Open the Time sub-menu (Date & Time / GMT Offset)."""
    global _time_menu, _mode
    from picoware.gui.menu import Menu

    draw = _view_manager.draw
    draw.erase()
    if _time_menu is not None:
        del _time_menu
        _time_menu = None

    _time_menu = Menu(
        draw,
        "Time",
        0,
        draw.size.y,
        _view_manager.foreground_color,
        _view_manager.background_color,
        _view_manager.selected_color,
        _view_manager.foreground_color,
        2,
    )
    _time_menu.add_item("Date & Time")
    _time_menu.add_item("GMT Offset")
    _time_menu.draw()
    _mode = _MODE_TIME_MENU


def __open_date_picker() -> None:
    """Open the DatePicker pre-loaded with the current RTC time."""
    global _date_picker, _mode
    from picoware.gui.date_picker import DatePicker
    from picoware.system.vector import Vector

    draw = _view_manager.draw
    draw.erase()
    if _date_picker is not None:
        del _date_picker
        _date_picker = None

    current_time = _view_manager.time.rtc.datetime()
    _date_picker = DatePicker(
        _view_manager,
        Vector(0, 0),
        draw.size,
        current_time,
    )
    _date_picker.run()
    _mode = _MODE_DATE_PICKER


def __open_gmt_keyboard() -> None:
    """Open the keyboard for entering the GMT offset."""
    global _mode, _gmt_save_requested

    keyboard = _view_manager.keyboard
    keyboard.reset()
    keyboard.title = "GMT Offset"
    keyboard.response = str(_settings.gmt_offset)
    keyboard.set_save_callback(__gmt_save_callback)
    keyboard.input_manager.reset()
    keyboard.run(force=True)
    _gmt_save_requested = False
    _mode = _MODE_GMT_KEYBOARD


def __gmt_save_callback(result: str) -> None:
    """Callback triggered when the GMT offset keyboard is saved.

    Args:
        result (str): The saved keyboard value.
    """
    global _gmt_save_requested
    _gmt_save_requested = True


def __back_to_menu() -> None:
    """Clean up any sub-view and return to the main menu."""
    global _choice, _appearance, _time_menu, _date_picker, _mode

    if _choice is not None:
        del _choice
        _choice = None
    if _time_menu is not None:
        del _time_menu
        _time_menu = None
    if _date_picker is not None:
        del _date_picker
        _date_picker = None

    _appearance = None
    _mode = _MODE_MENU
    _menu.selected_color = _view_manager.selected_color
    _menu.background_color = _view_manager.background_color
    _menu.text_color = _view_manager.foreground_color
    _menu.draw()


def __back_to_time_menu() -> None:
    """Return to the Time sub-menu from a date picker or keyboard."""
    global _date_picker, _gmt_save_requested

    if _date_picker is not None:
        del _date_picker
        _date_picker = None

    keyboard = _view_manager.keyboard
    keyboard.reset()
    _gmt_save_requested = False

    __open_time_menu()


def start(view_manager) -> bool:
    """Start the app and build the settings menu.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        bool: True if the app started, False if no SD card is present.
    """
    if not view_manager.has_sd_card:
        print("Settings app requires an SD card")
        return False

    from picoware.gui.menu import Menu
    from picoware.system.settings import Settings

    global _appearance, _settings, _menu, _view_manager, _mode, _time_menu, _date_picker, _gmt_save_requested
    global _resume_menu_label
    _view_manager = view_manager
    _mode = _MODE_MENU
    _gmt_save_requested = False

    _appearance = None
    if _settings is not None:
        del _settings
        _settings = None
    if _menu is not None:
        del _menu
        _menu = None
    if _time_menu is not None:
        del _time_menu
        _time_menu = None
    if _date_picker is not None:
        del _date_picker
        _date_picker = None

    view_manager.storage.mkdir("picoware/settings")

    _settings = Settings(view_manager.storage)

    _menu = Menu(
        view_manager.draw,
        "Settings",
        0,
        view_manager.draw.size.y,
        view_manager.foreground_color,
        view_manager.background_color,
        view_manager.selected_color,
        view_manager.foreground_color,
        2,
    )

    for cfg in __config():
        _menu.add_item(cfg[0])

    _menu.add_item('Screensaver')

    if _resume_menu_label is not None:
        for index in range(_menu.item_count):
            if _menu.get_item(index)==_resume_menu_label:
                _menu.set_selected(index)
                break
        _resume_menu_label=None

    _menu.draw()
    return True


def run(view_manager) -> None:
    """Run the app and handle setting input.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from picoware.system.buttons import (
        BUTTON_ESCAPE,
        BUTTON_UP,
        BUTTON_DOWN,
        BUTTON_LEFT,
        BUTTON_RIGHT,
        BUTTON_CENTER,
    )

    button = view_manager.button

    if _mode == _MODE_MENU:
        if button == BUTTON_ESCAPE:
            view_manager.back()
        elif button in (BUTTON_UP, BUTTON_LEFT):
            _menu.scroll_up()
        elif button in (BUTTON_DOWN, BUTTON_RIGHT):
            _menu.scroll_down()
        elif button == BUTTON_CENTER:
            selected = _menu.current_item
            if selected == 'Screensaver':
                global _resume_menu_label
                _resume_menu_label='Screensaver'
                from picoware.system.view import View
                from picoware.applications.system import screensaver_setting
                name='screensaver_setting'
                if view_manager.get_view(name) is None:
                    view_manager.add(View(name,screensaver_setting.run,screensaver_setting.start,screensaver_setting.stop, getattr(screensaver_setting, "HELP", None)))
                view_manager.switch_to(name)
            elif selected == "Appearance":
                __open_appearance()
            elif selected == "Time":
                __open_time_menu()
            elif selected == "Screen Brightness":
                __open_choice_brightness()

    elif _mode == _MODE_APPEARANCE:
        result = _appearance.handle(button)
        if result == 'cancel':
            __back_to_menu()
        elif result == 'save':
            if not _settings.update(_appearance.values):
                _appearance.error = 'Save failed. Check SD; F1 retries.'
                _appearance.draw()
                return
            view_manager.apply_appearance(_appearance.values)
            __back_to_menu()

    elif _mode == _MODE_TIME_MENU:
        if button == BUTTON_ESCAPE:
            __back_to_menu()
        elif button in (BUTTON_UP, BUTTON_LEFT):
            _time_menu.scroll_up()
        elif button in (BUTTON_DOWN, BUTTON_RIGHT):
            _time_menu.scroll_down()
        elif button == BUTTON_CENTER:
            selected = _time_menu.selected_index
            if selected == 0:  # Date & Time
                __open_date_picker()
            else:  # GMT Offset
                __open_gmt_keyboard()

    elif _mode == _MODE_DATE_PICKER:
        pending = view_manager.button
        if not _date_picker.run():
            if pending == BUTTON_CENTER:
                _saved_time = _date_picker.time
                view_manager.time.set(
                    _saved_time[0],  # year
                    _saved_time[1],  # month
                    _saved_time[2],  # day
                    _saved_time[4],  # hour
                    _saved_time[5],  # minute
                    _saved_time[6],  # second
                )
            __back_to_time_menu()

    elif _mode == _MODE_GMT_KEYBOARD:
        global _gmt_save_requested
        if _gmt_save_requested:
            _gmt_save_requested = False
            try:
                offset = int(view_manager.keyboard.response)
            except (ValueError, TypeError):
                offset = 0
            if not _settings.update({"gmt_offset": offset}):
                view_manager.alert("Could not save time offset.\nCheck the SD card.")
                view_manager.keyboard.run(force=True)
                return
            view_manager.gmt_offset = offset
            view_manager.keyboard.reset()
            __back_to_time_menu()
        elif not view_manager.keyboard.run():
            # ESC pressed — discard without saving
            view_manager.keyboard.reset()
            __back_to_time_menu()

    elif _mode == _MODE_CHOICE:
        if button == BUTTON_ESCAPE:
            __back_to_menu()
        elif button in (BUTTON_UP, BUTTON_LEFT):
            _choice.scroll_up()
        elif button in (BUTTON_DOWN, BUTTON_RIGHT):
            _choice.scroll_down()
        elif button == BUTTON_CENTER:
            if _current_setting == STATE_SCREEN_BRIGHTNESS:
                selected_value = int(_choice.options[_choice.state])
                if not _settings.update({"screen_brightness": selected_value}):
                    view_manager.alert("Could not save brightness.\nCheck the SD card.")
                    _choice.draw()
                    return
                _view_manager.draw.set_brightness(selected_value)
            __back_to_menu()


def stop(view_manager) -> None:
    """Stop the app and clean up.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from gc import collect

    global _settings, _menu, _choice, _appearance, _time_menu, _date_picker

    _appearance = None
    if _settings is not None:
        del _settings
        _settings = None
    if _choice is not None:
        del _choice
        _choice = None
    if _date_picker is not None:
        del _date_picker
        _date_picker = None
    if _time_menu is not None:
        del _time_menu
        _time_menu = None
    if _menu is not None:
        del _menu
        _menu = None

    view_manager.keyboard.reset()
    collect()
