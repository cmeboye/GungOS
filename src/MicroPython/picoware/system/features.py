"""Release identity and the SD application set shipped with GungOS."""

FIRMWARE_NAME = 'GungOS'
FIRMWARE_VERSION = '1.34'
RELEASE_APPS = ('PicoDESK', 'PicoLAB', 'Graph', 'Graph3D')
RELEASE_GAMES = ('Tetris',)
RELEASE_SCREENSAVERS = ('Lorenz', 'Lenia')
# New layout first; existing SD widgets remain discoverable during migration.
SCREENSAVER_DIRECTORIES = ('misc/screensavers','screensavers')
