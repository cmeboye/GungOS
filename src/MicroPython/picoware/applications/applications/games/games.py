"""Games - Collection of built-in games."""
from picoware.system.decorator import storage_required

_games = None
_games_index = 0
_app_loader = None

@storage_required
def start(view_manager) -> bool:
    """Start the games app.

    Args:
        view_manager (ViewManager): The view manager context.

    Returns:
        bool: True on success.
    """
    from picoware.system.app_loader import AppLoader
    AppLoader.release(view_manager)  # unload closed SD apps
    from picoware.gui.menu import Menu

    # create games folder if it doesn't exist
    view_manager.storage.mkdir("picoware/apps/games")

    global _games
    global _app_loader

    if _games:
        del _games
        _games = None

    _games = Menu(
        view_manager.draw,
        "Games",
        0,
        view_manager.draw.size.y,
        view_manager.foreground_color,
        view_manager.background_color,
        view_manager.selected_color,
        view_manager.foreground_color,
        2,
    )
    _app_loader = view_manager.app_loader

    from picoware.system.features import RELEASE_GAMES
    for game in sorted(set(_app_loader.list_available_apps("games"))):
        if game in RELEASE_GAMES: _games.add_item(game)

    _games.set_selected(_games_index)

    _games.draw()
    return True


def run(view_manager) -> None:
    """Run the games app.

    Args:
        view_manager (ViewManager): The view manager context.
    """
    from picoware.system.view import View
    from picoware.system.buttons import (
        BUTTON_ESCAPE,
        BUTTON_UP,
        BUTTON_DOWN,
        BUTTON_LEFT,
        BUTTON_CENTER,
        BUTTON_RIGHT,
    )

    global _games_index

    if not _games:
        return

    button: int = view_manager.button

    if button in (BUTTON_UP, BUTTON_LEFT):
        _games.scroll_up()
    elif button in (BUTTON_DOWN, BUTTON_RIGHT):
        _games.scroll_down()
    elif button == BUTTON_ESCAPE:
        _games_index = 0
        view_manager.back()
    elif button == BUTTON_CENTER:
        _games_index = _games.selected_index

        # Get the selected game name
        selected_game = _games.current_item

        if selected_game and _app_loader:
            # Try to load the game
            game_module = _app_loader.load_app(selected_game, "games")
            if game_module is None:
                view_manager.alert(f'Failed to load: {_app_loader.error}') 
                return
            # Create a view for the game and switch to it
            game_view_name = f"game_{selected_game}"
            from utime import ticks_ms

            start_time = ticks_ms()

            # Check if view already exists
            if view_manager.get_view(game_view_name) is None:
                game_view = View(
                    game_view_name,
                    game_module.run,
                    game_module.start,
                    game_module.stop,
                )
                view_manager.log(
                    f"[Games]: Created view for app {selected_game} after {ticks_ms() - start_time} ms",
                )
                view_manager.add(game_view)

            view_manager.switch_to(game_view_name)
            view_manager.log(
                f'[Games]: Switched to view for app "{selected_game}" after {ticks_ms() - start_time} ms',
            )


def stop(view_manager) -> None:
    """Stop the games app.

    Args:
        view_manager (ViewManager): The view manager context.
    """
    from gc import collect

    global _games
    if _games is not None:
        del _games
        _games = None
    if _app_loader is not None:
        _app_loader.cleanup_modules()
    collect()
