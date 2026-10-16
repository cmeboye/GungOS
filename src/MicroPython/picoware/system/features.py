"""Release identity and the SD application set shipped with GungOS."""

FIRMWARE_NAME = 'GungOS'
FIRMWARE_VERSION = '2.2'
RELEASE_APPS = ('PicoDESK', 'PicoLAB', 'Graph', 'Graph3D')
RELEASE_GAMES = ('Tetris',)
RELEASE_SCREENSAVERS = ('Lorenz',)
# New layout first; existing SD widgets remain discoverable during migration.
SCREENSAVER_DIRECTORIES = ('misc/screensavers','screensavers')
