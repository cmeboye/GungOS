"""Settings - Configure device settings."""

from micropython import const

# states
STATE_DARK_MODE = const(1)  # toggle (on/off)
STATE_DEBUG = const(2)  # toggle (enable/disable)
STATE_EXIT_BUTTON = const(4)  # selection to choose which button triggers app exits
STATE_LVGL_MODE = const(15)  # toggle (use LVGL or not)
STATE_ONSCREEN_KEYBOARD = const(9)  # toggle (show/hide)
STATE_SCREEN_BRIGHTNESS = const(11)  # choice (10 - 100)
STATE_THEME_COLOR = const(12)  # choice (select from predefined colors)
STATE_TIME = const(13)  # menu with date (date picker), GMT offset (keyboard)
STATE_USB_STREAM = const(14)  # toggle (enable/disable USB stream)

# modes
_MODE_MENU = const(0)
_MODE_TOGGLE = const(1)
_MODE_CHOICE = const(2)
_MODE_TIME_MENU = const(3)
_MODE_DATE_PICKER = const(4)
_MODE_GMT_KEYBOARD = const(5)
_MODE_MCP_SERVER_ENDPOINT_KEYBOARD = const(16)
_MODE_MCP_API_KEY_KEYBOARD = const(17)
_MODE_MCP_SERVERS_MENU = const(18)


_settings = None
_menu = None
_toggle = None
_choice = None
_time_menu = None
_date_picker = None
_mcp_servers_menu = None
_view_manager = None
_mode = _MODE_MENU
_current_setting = 0
_gmt_save_requested = False
_mcp_server_endpoint_save_requested = False
_mcp_api_key_save_requested = False
_mcp_server_index = 0
_menu_setting_indices = []
_resume_menu_label = None
_mcp_only = False


def __color_values() -> list[int]:
    """Get the list of color values corresponding to the color names.

    Returns:
        list[int]: The color values matching the theme color names.
    """
    from picoware.system.colors import (
        TFT_BLUE,
        TFT_RED,
        TFT_GREEN,
        TFT_YELLOW,
        TFT_VIOLET,
        TFT_CYAN,
        TFT_ORANGE,
        TFT_PINK,
        TFT_SKYBLUE,
        TFT_LIGHTGREY,
        TFT_DARKGREY,
        TFT_DARKCYAN,
        TFT_DARKGREEN,
        TFT_BROWN,
    )

    return [
        TFT_RED,
        TFT_GREEN,
        TFT_BLUE,
        TFT_YELLOW,
        TFT_VIOLET,
        TFT_CYAN,
        TFT_ORANGE,
        TFT_PINK,
        TFT_SKYBLUE,
        TFT_LIGHTGREY,
        TFT_DARKGREY,
        TFT_DARKCYAN,
        TFT_DARKGREEN,
        TFT_BROWN,
    ]


def __config() -> tuple:
    """Get the configuration tuple for the current setting.

    Returns:
        tuple: The (menu label, json key, default value) tuples.
    """
    # (menu label, json key, default value)
    return (
        ("Anthropic API Key", "anthropic_api_key", ""),
        ("Dark Mode", "dark_mode", True),
        ("Debug", "debug", False),
        ("DeepSeek API Key", "deepseek_api_key", ""),
        ("Exit Button", "exit_button", None),
        ("Gemini API Key", "gemini_api_key", ""),
        ("Local API Key", "local_api_key", ""),
        ("Local URL", "local_url", "http://127.0.0.1:8080/v1/chat/completions"),
        ("MCP Servers", "mcp_servers", None),
        (
            "Onscreen Keyboard",
            "onscreen_keyboard",
            True,
        ),
        ("OpenAI API Key", "openai_api_key", ""),
        ("Screen Brightness", "screen_brightness", 100),
        ("Theme Color", "theme_color", None),
        ("Time", "time", None),
        ("USB Stream", "usb_stream", False),
        ("Use LVGL", "lvgl_mode", False),
        ("xAI API Key", "xai_api_key", ""),
    )


def __exit_button_mapping() -> dict[int, str]:
    """Get the mapping of button values to their names for the exit button setting.

    Returns:
        dict[int, str]: The button value to name mapping.
    """
    from picoware.system.buttons import (
        BUTTON_ESCAPE,
    )

    return {
        BUTTON_ESCAPE: "<-Back",
        BUTTON_ESCAPE: "Esc",
    }


def __apply_toggle_setting(index: int, state: bool) -> None:
    """Apply a toggle setting change to the view manager.

    Args:
        index (int): The setting index to apply.
        state (bool): The new toggle state.
    """
    if index == STATE_ONSCREEN_KEYBOARD:
        _view_manager.keyboard.show_keyboard = state
    elif index == STATE_LVGL_MODE:
        _view_manager.draw.use_lvgl = state
    elif index == STATE_USB_STREAM:
        if state:
            _view_manager.start_usb_video_stream()
        else:
            _view_manager.stop_usb_video_stream()


def __open_toggle(setting_index: int) -> None:
    """Open a Toggle sub-view for the given setting index.

    Args:
        setting_index (int): The setting index to toggle.
    """
    global _toggle, _mode, _current_setting
    from picoware.gui.toggle import Toggle
    from picoware.system.vector import Vector

    _current_setting = setting_index
    cfg = __config()[setting_index]
    current_state = _settings._settings[cfg[1]]

    draw = _view_manager.draw
    draw.erase()
    if _toggle is not None:
        del _toggle
        _toggle = None

    _toggle = Toggle(
        draw,
        Vector(10, 10),
        Vector(draw.size.x - 20, int(draw.size.y // 10.67)),
        cfg[0],
        current_state,
        _view_manager.foreground_color,
        _view_manager.background_color,
        _view_manager.selected_color,
        _view_manager.foreground_color,
        2,
    )
    _toggle.draw()
    _mode = _MODE_TOGGLE


def __open_choice() -> None:
    """Open a Choice sub-view for the theme color setting."""
    global _choice, _mode, _current_setting
    from picoware.gui.choice import Choice
    from picoware.system.vector import Vector

    _current_setting = STATE_THEME_COLOR
    current_color = _settings.theme_color
    try:
        initial_index = __color_values().index(current_color)
    except ValueError:
        initial_index = 0

    draw = _view_manager.draw
    draw.erase()
    if _choice is not None:
        del _choice
        _choice = None

    _color_names = [
        "Red",
        "Green",
        "Blue",
        "Yellow",
        "Violet",
        "Cyan",
        "Orange",
        "Pink",
        "Sky Blue",
        "Light Grey",
        "Dark Grey",
        "Dark Cyan",
        "Dark Green",
        "Brown",
    ]

    _choice = Choice(
        draw,
        Vector(0, 0),
        draw.size,
        "Theme Color",
        _color_names,
        initial_index,
        _view_manager.foreground_color,
        _view_manager.background_color,
    )
    _choice.draw()
    _mode = _MODE_CHOICE


def __open_choice_button() -> None:
    """Open a Choice sub-view for the button to exit setting."""
    global _choice, _mode, _current_setting
    from picoware.gui.choice import Choice
    from picoware.system.vector import Vector

    _current_setting = STATE_EXIT_BUTTON
    current_button = _settings.exit_button
    str_buttons = list(__exit_button_mapping().values())
    initial_index = 0
    button_mapping = __exit_button_mapping()
    for i, button_value in enumerate(button_mapping.keys()):
        if button_value == current_button:
            initial_index = i
            break

    draw = _view_manager.draw
    draw.erase()
    if _choice is not None:
        del _choice
        _choice = None

    _choice = Choice(
        draw,
        Vector(0, 0),
        draw.size,
        "Button to Exit",
        str_buttons,
        initial_index,
        _view_manager.foreground_color,
        _view_manager.background_color,
    )
    _choice.draw()
    _mode = _MODE_CHOICE


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


def __open_mcp_server_endpoint_keyboard() -> None:
    """Open the keyboard for adding an MCP server endpoint."""
    global _mode, _mcp_server_endpoint_save_requested

    keyboard = _view_manager.keyboard
    keyboard.reset()
    keyboard.title = "MCP Server Endpoint"
    keyboard.response = ""
    keyboard.set_save_callback(__mcp_server_endpoint_save_callback)
    keyboard.input_manager.reset()
    keyboard.run(force=True)
    _mcp_server_endpoint_save_requested = False
    _mode = _MODE_MCP_SERVER_ENDPOINT_KEYBOARD


def __mcp_server_endpoint_save_callback(result: str) -> None:
    """Callback triggered when an MCP endpoint is saved."""
    global _mcp_server_endpoint_save_requested
    _mcp_server_endpoint_save_requested = True


def __add_mcp_server(endpoint: str) -> bool:
    """Add an MCP server with an empty optional API key."""
    servers = list(_settings.mcp_servers)
    servers.append({"endpoint": endpoint, "api_key": ""})
    return _settings.update({"mcp_servers": servers})


def __open_mcp_servers_menu() -> None:
    """Open the menu containing configured MCP servers."""
    global _mcp_servers_menu, _mode
    from picoware.gui.menu import Menu

    draw = _view_manager.draw
    draw.erase()
    if _mcp_servers_menu is not None:
        del _mcp_servers_menu
        _mcp_servers_menu = None

    _mcp_servers_menu = Menu(
        draw,
        "MCP Servers",
        0,
        draw.size.y,
        _view_manager.foreground_color,
        _view_manager.background_color,
        _view_manager.selected_color,
        _view_manager.foreground_color,
        2,
    )
    _mcp_servers_menu.add_item("[Add Server]")
    for server in _settings.mcp_servers:
        _mcp_servers_menu.add_item(server.get("endpoint", ""))
    _mcp_servers_menu.draw()
    _mode = _MODE_MCP_SERVERS_MENU


def __open_mcp_api_key_keyboard(server_index: int) -> None:
    """Open the keyboard for a per-server MCP API key.

    Args:
        server_index (int): The index of the server in the settings list.
    """
    global _mode, _mcp_api_key_save_requested, _mcp_server_index

    _mcp_server_index = server_index
    keyboard = _view_manager.keyboard
    keyboard.reset()
    keyboard.title = "MCP API Key"
    keyboard.secret = True
    keyboard.response = _settings.mcp_servers[server_index].get("api_key", "")
    keyboard.text_cursor_position = len(keyboard.response)
    keyboard.set_save_callback(__mcp_api_key_save_callback)
    keyboard.input_manager.reset()
    keyboard.run(force=True)
    _mcp_api_key_save_requested = False
    _mode = _MODE_MCP_API_KEY_KEYBOARD


def __mcp_api_key_save_callback(result: str) -> None:
    """Callback triggered when an MCP API key keyboard is saved.

    Args:
        result (str): The saved keyboard value.
    """
    global _mcp_api_key_save_requested
    _mcp_api_key_save_requested = True


def __save_mcp_api_key(value: str) -> bool:
    """Save a per-server MCP API key by its server index."""
    servers = list(_settings.mcp_servers)
    server = dict(servers[_mcp_server_index])
    server["api_key"] = value
    servers[_mcp_server_index] = server
    return _settings.update({"mcp_servers": servers})


def __back_to_mcp_servers_menu() -> None:
    """Return to the MCP Servers sub-menu."""
    global _mcp_server_endpoint_save_requested, _mcp_api_key_save_requested

    keyboard = _view_manager.keyboard
    keyboard.reset()
    _mcp_server_endpoint_save_requested = False
    _mcp_api_key_save_requested = False

    __open_mcp_servers_menu()


def __back_to_menu() -> None:
    """Clean up any sub-view and return to the main menu."""
    global _toggle, _choice, _time_menu, _date_picker, _mcp_servers_menu, _mode

    if _toggle is not None:
        del _toggle
        _toggle = None
    if _choice is not None:
        del _choice
        _choice = None
    if _time_menu is not None:
        del _time_menu
        _time_menu = None
    if _date_picker is not None:
        del _date_picker
        _date_picker = None
    if _mcp_servers_menu is not None:
        del _mcp_servers_menu
        _mcp_servers_menu = None

    _mode = _MODE_MENU
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

    global _settings, _menu, _view_manager, _mode, _time_menu, _date_picker, _mcp_servers_menu, _gmt_save_requested, _mcp_server_endpoint_save_requested, _mcp_api_key_save_requested

    global _menu_setting_indices, _mcp_only
    global _resume_menu_label
    _mcp_only = False
    _view_manager = view_manager
    _mode = _MODE_MENU
    _gmt_save_requested = False
    _mcp_server_endpoint_save_requested = False
    _mcp_api_key_save_requested = False

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
    if _mcp_servers_menu is not None:
        del _mcp_servers_menu
        _mcp_servers_menu = None

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

    _menu_setting_indices = []
    from picoware.system.features import LVGL_ENABLED, MEDIA_ENABLED, AI_ENABLED
    if AI_ENABLED:
        _menu.add_item("AI Setup")
        _menu_setting_indices.append(-1)
    for index, cfg in enumerate(__config()):
        if cfg[1] in ("dark_mode","exit_button"):
            continue
        if cfg[1].endswith("api_key") or cfg[1] in ("local_url", "mcp_servers"):
            continue
        if cfg[1] == "lvgl_mode" and not LVGL_ENABLED:
            continue
        if cfg[1] == "usb_stream" and not MEDIA_ENABLED:
            continue
        _menu.add_item(cfg[0])
        _menu_setting_indices.append(index)

    _menu.add_item('Screensaver')
    _menu_setting_indices.append(-2)

    if _resume_menu_label is not None:
        for index in range(_menu.item_count):
            if _menu.get_item(index)==_resume_menu_label:
                _menu.set_selected(index)
                break
        _resume_menu_label=None

    _menu.draw()
    return True


def start_mcp(view_manager):
    """Open MCP settings from the AI Setup advanced menu."""
    global _mcp_only
    if not start(view_manager):
        return False
    _mcp_only = True
    __open_mcp_servers_menu()
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
            if selected == "AI Setup":
                from picoware.applications.ai_setup import open_setup
                open_setup(view_manager)
            elif selected == 'Screensaver':
                global _resume_menu_label
                _resume_menu_label='Screensaver'
                from picoware.system.view import View
                from picoware.applications.system import screensaver_setting
                name='screensaver_setting'
                if view_manager.get_view(name) is None:
                    view_manager.add(View(name,screensaver_setting.run,screensaver_setting.start,screensaver_setting.stop))
                view_manager.switch_to(name)
            elif selected == "Theme Color":
                __open_choice()
            elif selected == "Time":
                __open_time_menu()
            elif selected == "Exit Button":
                __open_choice_button()
            elif selected == "Screen Brightness":
                __open_choice_brightness()
            else:
                __open_toggle(_menu_setting_indices[_menu.selected_index])

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

    elif _mode == _MODE_MCP_SERVER_ENDPOINT_KEYBOARD:
        global _mcp_server_endpoint_save_requested
        if _mcp_server_endpoint_save_requested:
            _mcp_server_endpoint_save_requested = False
            endpoint = view_manager.keyboard.response or ""
            if endpoint:
                if not __add_mcp_server(endpoint):
                    view_manager.alert("Could not save MCP server.\nCheck the SD card.")
                    return
            __back_to_mcp_servers_menu()
        elif not view_manager.keyboard.run():
            __back_to_mcp_servers_menu()

    elif _mode == _MODE_MCP_SERVERS_MENU:
        if button == BUTTON_ESCAPE:
            if _mcp_only:
                view_manager.back()
            else:
                __back_to_menu()
        elif button in (BUTTON_UP, BUTTON_LEFT):
            _mcp_servers_menu.scroll_up()
        elif button in (BUTTON_DOWN, BUTTON_RIGHT):
            _mcp_servers_menu.scroll_down()
        elif button == BUTTON_CENTER:
            selected = _mcp_servers_menu.selected_index
            if selected == 0:
                __open_mcp_server_endpoint_keyboard()
            else:
                __open_mcp_api_key_keyboard(selected - 1)

    elif _mode == _MODE_MCP_API_KEY_KEYBOARD:
        global _mcp_api_key_save_requested
        if _mcp_api_key_save_requested:
            _mcp_api_key_save_requested = False
            if not __save_mcp_api_key(view_manager.keyboard.response or ""):
                view_manager.alert("Could not save MCP key.\nCheck the SD card.")
                return
            __back_to_mcp_servers_menu()
        elif not view_manager.keyboard.run():
            __back_to_mcp_servers_menu()

    elif _mode == _MODE_TOGGLE:
        if button == BUTTON_ESCAPE:
            __back_to_menu()
        elif button == BUTTON_CENTER:
            new_state = not _toggle.state
            _toggle.state = new_state
            cfg = __config()[_current_setting]
            if not _settings.update({cfg[1]: new_state}):
                _toggle.state = not new_state
                view_manager.alert("Could not save setting.\nCheck the SD card.")
                return
            __apply_toggle_setting(_current_setting, new_state)

    elif _mode == _MODE_CHOICE:
        if button == BUTTON_ESCAPE:
            __back_to_menu()
        elif button in (BUTTON_UP, BUTTON_LEFT):
            _choice.scroll_up()
        elif button in (BUTTON_DOWN, BUTTON_RIGHT):
            _choice.scroll_down()
        elif button == BUTTON_CENTER:
            if _current_setting == STATE_THEME_COLOR:
                selected_color = __color_values()[_choice.state]
                if not _settings.update({"theme_color": selected_color}):
                    view_manager.alert("Could not save theme color.\nCheck the SD card.")
                    _choice.draw()
                    return
                _view_manager.selected_color = selected_color
            elif _current_setting == STATE_EXIT_BUTTON:
                button_mapping = __exit_button_mapping()
                selected_button_value = list(button_mapping.keys())[_choice.state]
                if not _settings.update({"exit_button": selected_button_value}):
                    view_manager.alert("Could not save exit button.\nCheck the SD card.")
                    _choice.draw()
                    return
                from picoware.system.system import System

                s = System()
                s.hard_reset()
            elif _current_setting == STATE_SCREEN_BRIGHTNESS:
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

    global _settings, _menu, _toggle, _choice, _time_menu, _date_picker, _mcp_servers_menu

    if _settings is not None:
        del _settings
        _settings = None
    if _choice is not None:
        del _choice
        _choice = None
    if _toggle is not None:
        del _toggle
        _toggle = None
    if _date_picker is not None:
        del _date_picker
        _date_picker = None
    if _time_menu is not None:
        del _time_menu
        _time_menu = None
    if _mcp_servers_menu is not None:
        del _mcp_servers_menu
        _mcp_servers_menu = None
    if _menu is not None:
        del _menu
        _menu = None

    from picoware.system.features import LVGL_ENABLED
    if LVGL_ENABLED and view_manager.draw.use_lvgl:
        # restart with wifi disconnected...
        if view_manager._wifi is not None:
            from picoware.system.system import System

            sys = System()
            sys.hard_reset()
    elif LVGL_ENABLED:
        if view_manager._wifi is None:
            from picoware.system.system import System

            sys = System()
            if sys.has_wifi:
                # wifi was disabled before so just restart...
                # we probably could just deinit lvgl and continue
                # but maybe thats something we'll try later...
                sys.hard_reset()

    view_manager.keyboard.reset()
    collect()
