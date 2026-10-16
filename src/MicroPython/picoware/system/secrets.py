"""Secrets - credentials kept in the Pico's internal flash instead of on the SD card.

Removing or copying the SD card does not expose these values. They stay with
the device, so moving the card to another PicoCalc means entering them again.
Anyone with the device and a USB cable can still read them through the REPL.
"""

import json

SECRETS_FILE = "secrets.json"


def path() -> str:
    """Return the location of the secrets file in internal flash."""
    from sys import platform

    if platform == "rp2":
        return "/" + SECRETS_FILE
    # The desktop simulator keeps its "internal flash" next to the simulated SD.
    import sim_runtime

    return sim_runtime.flash_path(SECRETS_FILE)


def load() -> dict:
    """Return all stored secrets, or an empty dict if none are readable."""
    try:
        with open(path(), "r") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get(key: str, default: str = "") -> str:
    """Return one stored secret.

    Args:
        key (str): The secret name, e.g. "wifi_password".
        default (str): Value returned when the secret is missing. Defaults to "".
    """
    return load().get(key, default)


def update(values: dict) -> bool:
    """Store secrets atomically; a value of None removes that secret.

    Args:
        values (dict): Secret names and their new values.

    Returns:
        bool: True if the flash write was verified.
    """
    import os

    data = load()
    for key, value in values.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    target = path()
    temporary = target + ".tmp"
    try:
        with open(temporary, "w") as handle:
            json.dump(data, handle)
        with open(temporary, "r") as handle:
            if json.load(handle) != data:
                raise OSError("secrets verification failed")
        os.rename(temporary, target)
        return True
    except (OSError, ValueError):
        try:
            os.remove(temporary)
        except OSError:
            pass
        return False
