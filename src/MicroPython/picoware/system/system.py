"""System - Basic system operations."""

class System:
    """Handle basic system operations."""

    @property
    def board_id(self) -> int:
        """Return the board ID."""
        from picoware.system.boards import BOARD_ID

        return BOARD_ID

    @property
    def board_name(self):
        """Return the board name."""
        from picoware.system.boards import DEVICE_NAME

        return DEVICE_NAME

    @property
    def device_name(self):
        """Return the device name."""
        from picoware.system.boards import BOARD_NAME

        return BOARD_NAME

    @property
    def free_psram(self):
        """Return the amount of free PSRAM memory."""
        from picoware.system.psram import PSRAM

        psram = PSRAM()
        return psram.free_heap_size

    @property
    def free_heap(self) -> int:
        """Return the amount of free heap memory."""
        from gc import mem_free

        return mem_free()

    @property
    def freq(self):
        """Return MCU frequency."""
        import machine

        try:
            freq = machine.freq() / 1000000
        except Exception:
            # unpack tuple
            freq = machine.freq()[0] / 1000000
        return int(freq)

    @property
    def free_flash(self):
        """Return the free flash memory size."""
        from os import statvfs

        stat = statvfs("/")
        free = stat[0] * stat[3]

        return free

    @property
    def total_flash(self):
        """Return the total flash memory size."""
        from os import statvfs

        stat = statvfs("/")
        size = stat[1] * stat[2]

        return size

    @property
    def used_flash(self):
        """Return the used flash memory size."""
        from os import statvfs

        stat = statvfs("/")
        size = stat[1] * stat[2]
        free = stat[0] * stat[3]
        used = size - free

        return used

    @property
    def total_heap(self):
        """Return the total heap memory size."""
        from gc import mem_free, mem_alloc

        return mem_free() + mem_alloc()

    @property
    def total_psram(self):
        """Return the total PSRAM memory size."""
        from picoware.system.psram import PSRAM

        psram = PSRAM()
        return psram.total_heap_size

    @property
    def used_heap(self):
        """Return the total heap memory used."""
        from gc import mem_alloc

        return mem_alloc()

    @property
    def used_psram(self):
        """Return the total PSRAM memory used."""
        from picoware.system.psram import PSRAM

        psram = PSRAM()
        return psram.used_heap_size

    @property
    def version(self) -> str:
        """Return the selected firmware version."""
        from picoware.system.features import FIRMWARE_VERSION
        return FIRMWARE_VERSION

    def bootloader_mode(self):
        """Enter the bootloader mode."""
        from machine import bootloader

        bootloader()

    def hard_reset(self):
        """Reboot the system."""
        from machine import reset

        reset()

    def shutdown_device(self, view_manager=None):
        """Shut down the device.

        Args:
            view_manager (ViewManager): Optional manager to show a shutdown alert. Defaults to None.
        """
        from picoware_southbridge import is_power_off_supported, write_power_off_delay

        if is_power_off_supported():
            if view_manager:
                view_manager.alert(
                    "Click 'BACK', the device will turn off in 5 seconds"
                )
                write_power_off_delay(0)

    def soft_reset(self):
        """Reboot the system without resetting the hardware."""
        from machine import soft_reset

        soft_reset()
