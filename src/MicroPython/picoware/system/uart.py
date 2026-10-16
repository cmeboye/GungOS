"""UART - Serial communication interface."""

class UART:
    """Class representing a UART (Universal Asynchronous Receiver-Transmitter) interface."""

    def __init__(
        self,
        uart_id: int = None,
        tx_pin: int = None,
        rx_pin: int = None,
        baud_rate: int = 115200,
        timeout: int = 2000,
    ) -> None:
        """Initialize the UART interface.

        Args:
            uart_id (int or None): UART peripheral ID, or None for UART0. Defaults to None.
            tx_pin (int or None): TX pin number, or None for GP0. Defaults to None.
            rx_pin (int or None): RX pin number, or None for GP1. Defaults to None.
            baud_rate (int): Baud rate for the interface. Defaults to 115200.
            timeout (int): Read timeout in milliseconds. Defaults to 2000.

        Raises:
            Exception: If the UART peripheral could not be initialized.
        """
        from machine import UART as MachineUART
        from machine import Pin

        # PicoCalc exposes UART0 on GP0 (TX) and GP1 (RX).
        if uart_id is None:
            uart_id = 0
        if tx_pin is None:
            tx_pin = 0
        if rx_pin is None:
            rx_pin = 1

        self._uart_id = uart_id
        self._tx_pin = tx_pin
        self._rx_pin = rx_pin
        self._baud_rate = baud_rate
        self._uart = None
        self._callback = None

        self._uart = MachineUART(
            uart_id, baudrate=baud_rate, tx=Pin(tx_pin), rx=Pin(rx_pin)
        )
        self._uart.init()

        self._timeout = timeout  # milliseconds

    def __del__(self) -> None:
        """Deinitialize the UART interface."""
        self._uart.deinit()
        del self._uart
        self._uart = None

    @property
    def baud_rate(self) -> int:
        """Get the baud rate of the UART interface."""
        return self._baud_rate

    @property
    def callback(self):
        """Get the UART callback function."""
        return self._callback

    @property
    def has_data(self) -> bool:
        """Check if there is data available to read from the UART interface."""
        return self._uart.any() > 0

    @property
    def is_sending(self) -> bool:
        """Check if the UART interface is currently sending data."""
        return not self._uart.txdone()

    @property
    def rx_pin(self) -> int:
        """Get the RX pin number."""
        return self._rx_pin

    @property
    def timeout(self) -> int:
        """Get the timeout value in milliseconds."""
        return self._timeout

    @timeout.setter
    def timeout(self, value: int) -> None:
        """Set the timeout value in milliseconds.

        Args:
            value (int): The timeout value in milliseconds.
        """
        self._timeout = value

    @property
    def tx_pin(self) -> int:
        """Get the TX pin number."""
        return self._tx_pin

    @property
    def uart(self):
        """Get the UART context."""
        return self._uart

    def clear(self) -> None:
        """Clear the serial buffer"""
        while self._uart.any() > 0:
            self._uart.read()

    def flush(self) -> None:
        """Flush the UART interface."""
        self._uart.flush()

    def println(self, message: str) -> None:
        """Write a message followed by a newline to the UART interface.

        Args:
            message (str): The message to write.
        """
        self._uart.write(message + "\n")

    def read_into(self, buffer: bytearray) -> int:
        """Read data from the UART interface into a buffer.

        Args:
            buffer (bytearray): The buffer to read data into.

        Returns:
            int: The number of bytes read.
        """
        return self._uart.readinto(buffer)

    def read_line(self) -> str:
        """Read a line from the UART interface with timeout handling.

        Returns:
            str or None: The line read without a trailing newline, or None on timeout.
        """
        from time import ticks_ms

        start_time = ticks_ms()
        message = ""

        while (ticks_ms() - start_time) < self._timeout:
            if self._uart.any() > 0:
                try:
                    raw_data = self._uart.read()
                    if raw_data:
                        # Reset the timeout when data is read
                        start_time = ticks_ms()
                        message += raw_data.decode()

                        if "\n" in message:
                            message = message.strip("\n")
                            return message
                except Exception:
                    continue

        # Timeout reached with no newline received
        return None

    def read_serial_line(self) -> str:
        """Read a line from the UART interface.

        Returns:
            str: The decoded data read, or an empty string if none.
        """
        data = ""
        try:
            raw_data = self._uart.read()
            if raw_data:  # Ensures raw_data isn't empty before decoding
                data = raw_data.decode()
        except Exception:
            pass  # raw_data is empty/None
        return data

    def set_callback(self, callback: callable, trigger: int = None, hard: bool = False) -> None:
        """Set an interrupt handler to be called when a UART event occurs.

        Args:
            callback (callable): The interrupt handler function.
        """
        self._uart.irq(
            handler=callback,
            trigger=trigger if trigger is not None else self._uart.IRQ_RXIDLE,
            hard=hard,
        )
        self._callback = callback

    def write(self, message: bytes) -> None:
        """Write a message to the UART interface.

        Args:
            message (bytes): The bytes to write.
        """
        self._uart.write(message)
