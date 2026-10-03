#!/usr/bin/python3
"""GUI application entry point for system-config-samba.

Builds the libadwaita application and shows the main share window. The window
talks to the privileged D-Bus backend through BackendClient; if the backend is
not reachable, reads still work via a direct file preview (writes require it).
"""

from __future__ import annotations

import os
import sys

# Run as a top-level script: make the sibling UI modules and the scsamba
# package importable no matter the working directory (mirrors upstream,
# where system-config-samba.py was executed directly from src/).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib  # noqa: E402

from scsamba import APP_ID  # noqa: E402
from scsamba.dbus.proxy import BackendClient  # noqa: E402
from mainWindow import SambaMainWindow  # noqa: E402


def _make_client():
    """Connect to the backend, but never fail startup if it is absent."""
    try:
        return BackendClient()
    except Exception as exc:  # no system bus / backend not installed yet
        print("backend not connected (%s); read-only preview" % exc,
              file=sys.stderr)
        return None


class SystemConfigSambaApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self._window = None
        self._client = _make_client()
        self._selfcheck_failed = False

    def do_activate(self):
        if self._window is None:
            self._window = SambaMainWindow(self, client=self._client)
        self._window.present()

        if os.environ.get("SYSTEM_CONFIG_SAMBA_SELFCHECK") == "1":
            # Exercise dialog construction headlessly. PyGObject swallows
            # exceptions raised in do_activate yet still returns 0 from run(),
            # so we must catch them here and propagate an explicit exit code
            # or a broken dialog would look like a passing smoke test.
            import traceback

            failed = False
            try:
                self._window.selfcheck_open_dialogs()
            except BaseException:
                traceback.print_exc()
                failed = True

            def _finish():
                self._window.destroy()
                # Adw/Gtk/Gio.Application has no exit(); record the result on
                # the app and let main() translate it into the process exit
                # code after run() returns, otherwise failures stay masked.
                self._selfcheck_failed = failed
                self.quit()
                return False
            GLib.idle_add(_finish)

    def do_startup(self):
        Adw.Application.do_startup(self)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    app = SystemConfigSambaApp()
    rc = app.run(argv)
    if getattr(app, "_selfcheck_failed", False):
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
