"""Selected features for the custom Python/engineering firmware."""

LVGL_ENABLED = False
EXTRA_LANGUAGES_ENABLED = False
GAME_BACKENDS_ENABLED = False
MEDIA_ENABLED = False
AI_ENABLED = False
FIRMWARE_NAME = 'GungOS'
FIRMWARE_VERSION = '2.2'
RELEASE_APPS = ('PicoDESK', 'PicoLAB', 'Graph', 'Graph3D')
RELEASE_GAMES = ('Tetris',)
RELEASE_SCREENSAVERS = ('Lorenz',)
# New layout first; existing SD widgets remain discoverable during migration.
SCREENSAVER_DIRECTORIES = ('misc/screensavers','screensavers')

# Shared by the frozen manifest and simulator import guard. Native backends
# are omitted by the PicoCalc CMake file and desktop make fragments as well.
DISABLED_MODULES = (
    "picoware.applications.applications.FlipSocial",
    "picoware.applications.notifications",
    "picoware.applications.applications.agent",
    "picoware.applications.ai_setup",
    "picoware.system.agent",
    "picoware.system.ai",
    "picoware.applications.utilities.email",
    "picoware.applications.utilities.espflasher",
    "picoware.applications.applications.app_store",
    "picoware.applications.system.update",
    "picoware.applications.applications.c",
    "picoware.applications.applications.javascript",
    "picoware.applications.applications.mmbasic",
    "picoware.applications.applications.games.gameboy",
    "picoware.applications.applications.games.ghouls",
    "picoware.engine",
    "picoware.system.c",
    "picoware.system.js",
    "picoware.system.mmbasic",
    "picoware.system.audio",
    "picoware.system.video",
    "c", "mjs", "mmbasic", "engine", "gameboy", "ghouls",
    "audio", "video", "usb_video_mp", "picoware_lvgl",
    "http", "websocket", "jsmn",
)


def module_disabled(name):
    """Whether a module was excluded from this firmware build."""
    return any(name == item or name.startswith(item + ".") for item in DISABLED_MODULES)
