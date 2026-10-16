"""View - Base class for managed views."""

CRASH_LOG_PATH = "picoware/last_crash.txt"

class View:
    """A view managed by the ViewManager.

    Attributes:
        name (str): The name of the view.
        run (callable): Function called every frame.
        start (callable): Function called when the view is created.
        stop (callable): Function called when the view is destroyed.
        active (bool): Whether the view is currently active.
    """

    __slots__ = ("name", "_run", "_start", "_stop", "active")

    def __init__(self, name: str, run: callable, start: callable, stop: callable):
        """Initialize the view with its name and callbacks.

        Args:
            name (str): The name of the view.
            run (callable): Function called every frame.
            start (callable): Function called when the view is created.
            stop (callable): Function called when the view is destroyed.
        """
        self.name = name
        self._run = run
        self._start = start
        self._stop = stop
        self.active = False

    def __alert(self, phase, exception, view_manager) -> None:
        """Report a view failure: log the traceback, keep it on SD and show a summary.

        Args:
            phase (str): What the view was doing ("starting", "running", "stopping").
            exception (Exception): The exception raised by the view.
            view_manager (ViewManager): The manager to show the alert on.
        """
        import sys
        import io

        buf = io.StringIO()
        sys.print_exception(exception, buf)
        trace = buf.getvalue()
        view_manager.log(f"{self.name} failed while {phase}:\n{trace}", 2)

        saved = False
        try:
            storage = view_manager.storage
            saved = storage is not None and storage.write(
                CRASH_LOG_PATH, f"View: {self.name} ({phase})\n{trace}"
            )
        except Exception:
            saved = False

        lines = [line.strip() for line in trace.split("\n") if line.strip()]
        summary = lines[-1] if lines else repr(exception)
        # The innermost frame is the last "File ..." line of the traceback.
        location = ""
        for line in reversed(lines):
            if line.startswith("File "):
                parts = line.split('"')
                if len(parts) >= 3:
                    location = "/".join(parts[1].split("/")[-2:]) + parts[2].rstrip()
                break
        message = f"{self.name} failed while {phase}.\n{summary}"
        if location:
            message += f"\nAt {location}"
        if saved:
            message += f"\nDetails: {CRASH_LOG_PATH}"
        view_manager.alert(message, False, "App error")

    def start(self, view_manager) -> bool:
        """Start the view and mark it active.

        Args:
            view_manager (ViewManager): The manager that owns this view.

        Returns:
            bool: True if the view started successfully, False otherwise.
        """
        if self._start:
            try:
                if self._start(view_manager):
                    self.active = True
                    return True
            except Exception as e:
                self.__alert("starting", e, view_manager)
                self.active = False
                return False
        return False

    def stop(self, view_manager):
        """Stop the view and mark it inactive.

        Args:
            view_manager (ViewManager): The manager that owns this view.
        """
        if self._stop:
            try:
                self._stop(view_manager)
            except Exception as e:
                self.__alert("stopping", e, view_manager)
        self.active = False

    def run(self, view_manager):
        """Run the view's per-frame callback.

        Args:
            view_manager (ViewManager): The manager that owns this view.
        """
        if self._run and self.active:
            try:
                self._run(view_manager)
            except Exception as e:
                self.__alert("running", e, view_manager)
                self.active = False
                view_manager.back()
