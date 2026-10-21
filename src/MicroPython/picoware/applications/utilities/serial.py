from micropython import const

HELP = (
    "Serial terminal:",
    "UART0 at 115200 baud: TX on GP0, RX on GP1.",
    "Messages are typed on the on-screen keyboard.",
    "ENTER\ttype the next message",
    "ESC\treturn",
)

# states
STATE_VIEWING = const(0)
STATE_TYPING = const(1)
STATE_SENDING = const(2)

# global objects
_textbox = None
_uart = None
_loading = None
state = STATE_TYPING
message = ""
_received = False
_prev_callback = None
_log = []

def __uart_callback(uart_instance):
    """Callback for UART events"""
    global _received, message
    message = f"Friend: {uart_instance.read()}\n"
    _received = True


def __box_start(view_manager) -> None:
    """Show the conversation, newest lines at the bottom."""
    from picoware.gui.style import Page

    global _textbox

    if _textbox is None:
        _textbox = Page(view_manager, "Utils / Serial", ())
        _textbox.message = f"Listening on GPIO{_uart.rx_pin}"
    __log(message)


def __log(text: str) -> None:
    """Add received or sent text to the conversation and redraw it."""
    _log.extend(line for line in text.split("\n") if line)
    del _log[:-60]
    _textbox.set_lines(_log)
    _textbox.first = len(_textbox.lines)
    _textbox.draw()


def __callback(result: str) -> None:
    """Callback for keyboard input"""
    global state, message
    _log.append("You: " + result)
    state = STATE_SENDING
    _uart.println(result)
    message = ""


def __loading_run(view_manager, text: str = "Sending...") -> None:
    """Start loading animation"""
    from picoware.gui.loading import Loading

    global _loading

    if not _loading:
        _loading = Loading(view_manager.draw)
        _loading.set_text(text)
    else:
        _loading.animate()


def __set_kb(view_manager, title: str) -> None:
    """Set up the keyboard"""
    kb = view_manager.keyboard
    kb.reset()
    kb.response = ""
    kb.callback = __callback
    kb.title = title
    kb.run(force=True)


def start(view_manager) -> bool:
    """Start the app"""
    global _textbox, _uart, state, _loading, _received, _prev_callback

    _textbox = None
    del _log[:]
    if _loading is not None:
        del _loading
        _loading = None

    state = STATE_TYPING
    _received = False

    view_manager.freq(True)  # set to lower frequency
    _uart = view_manager.uart
    _prev_callback = _uart.callback
    _uart.set_callback(__uart_callback)

    # first show the connection settings
    if not view_manager.alert(
        "Connect with these settings:\nBaud rate\t115200\nTX pin\tUART0_TX (GP0)\nRX pin\tUART0_RX (GP1)",
        False,
        "Serial",
    ):
        view_manager.back()
        return False

    __set_kb(view_manager, "Start the conversation")

    return True


def run(view_manager) -> None:
    """Run the app"""
    from picoware.system.buttons import BUTTON_ESCAPE, BUTTON_CENTER

    inp = view_manager.input_manager
    button = inp.button

    global state, _loading

    if button == BUTTON_ESCAPE:
        inp.reset()
        view_manager.back()
        return
    if button == BUTTON_CENTER and state == STATE_VIEWING:
        inp.reset()
        __set_kb(view_manager, "Send a message")
        state = STATE_TYPING

    if state == STATE_TYPING:
        kb = view_manager.keyboard
        if not kb.run():
            view_manager.back()
            return
    elif state == STATE_SENDING:
        if not _uart.is_sending:
            state = STATE_VIEWING
            kb = view_manager.keyboard
            kb.reset()
            del _loading
            _loading = None
            __box_start(view_manager)
        else:
            __loading_run(view_manager)
    elif state == STATE_VIEWING:
        global _received, message
        if _received:
            __log(message)
            _received = False
            message = ""


def stop(view_manager) -> None:
    """Stop the app"""
    from gc import collect

    global _textbox, _uart, _loading, state, message, _received, _prev_callback

    _textbox = None
    del _log[:]
    if _loading is not None:
        del _loading
        _loading = None
    if _uart is not None:
        _uart.set_callback(_prev_callback)
        _prev_callback = None
    _uart = None # close our reference
    state = STATE_TYPING
    message = ""
    _received = False

    view_manager.keyboard.reset()

    view_manager.freq()  # set back to higher frequency

    # cleanup
    collect()
