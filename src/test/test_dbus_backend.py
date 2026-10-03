# -*- coding: utf-8 -*-
"""End-to-end D-Bus test for the samba-conf-tool backend over a private bus.

Spins up Gio.TestDBus (a real dbus-daemon), exports the privileged backend on
it with polkit disabled, and drives it through the production BackendClient
proxy. This proves the introspection XML, GVariant signatures, dispatch and
core file effects all line up — without touching the real system bus or root.

Run:  python3 -m unittest src.test.test_dbus_backend  (or discover -s src/test)
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import unittest

import gi
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scsamba.dbus.service import BackendService, _own_name  # noqa: E402
from scsamba.dbus.proxy import BackendClient  # noqa: E402
from scsamba.core import SambaBackend  # noqa: E402

SAMPLE = """\
[global]
\tworkgroup = TESTGRP
\tsecurity = user

[oldshare]
\tpath = /srv/old
\tread only = yes
"""


@unittest.skipUnless(hasattr(Gio, "TestDBus"), "Gio.TestDBus unavailable")
class DbusBackendE2E(unittest.TestCase):
    def setUp(self):
        fd, self.conf = tempfile.mkstemp(suffix=".smb.conf")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(SAMPLE)
        self.users = self.conf + ".users"

        os.environ["SAMBA_CONF_TOOL_DISABLE_POLKIT"] = "1"
        os.environ["SAMBA_CONF_TOOL_SKIP_VALIDATE"] = "1"
        os.environ["SAMBA_CONF_TOOL_SKIP_SERVICE"] = "1"

        self.test_bus = Gio.TestDBus.new(Gio.TestDBusFlags.NONE)
        self.test_bus.up()
        addr = self.test_bus.get_bus_address()

        FLAGS = (Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
                 | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION)

        # Run the privileged backend in its own thread with its own main
        # context + loop, mirroring the separate root process it is in
        # production. A same-thread call_sync would not pump the server's
        # dispatch and would deadlock.
        backend = SambaBackend(smb_conf_path=self.conf, smbusers_path=self.users)
        self.server_ctx = GLib.MainContext.new()
        self.server_loop = GLib.MainLoop(self.server_ctx)
        self._ready = threading.Event()
        self._server_err = []

        def _serve():
            try:
                self.server_ctx.push_thread_default()
                self.server_conn = Gio.DBusConnection.new_for_address_sync(
                    addr, FLAGS, None, None)
                BackendService(self.server_conn, backend, require_polkit=False)
                _own_name(self.server_conn)
                self._ready.set()
                self.server_loop.run()
            except Exception as e:  # pragma: no cover
                self._server_err.append(e)
                self._ready.set()

        self._thread = threading.Thread(target=_serve, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=10)
        if self._server_err:
            raise self._server_err[0]

        self.client_conn = Gio.DBusConnection.new_for_address_sync(addr, FLAGS, None, None)
        self.client = BackendClient(bus=self.client_conn)

    def tearDown(self):
        self.server_loop.quit()
        self._thread.join(timeout=5)
        self.test_bus.down()
        for f in (self.conf, self.users):
            try:
                os.unlink(f)
            except OSError:
                pass

    def test_read_config_over_dbus(self):
        text = self.client.read_config()
        self.assertIn("[global]", text)
        self.assertIn("workgroup = TESTGRP", text)

    def test_write_config_roundtrip(self):
        text = self.client.read_config()
        new = text.replace("workgroup = TESTGRP", "workgroup = NEWGRP")
        self.client.write_config(new)

        with open(self.conf, "r", encoding="utf-8") as fh:
            on_disk = fh.read()
        self.assertIn("workgroup = NEWGRP", on_disk)

    def test_list_users_returns_list(self):
        # non-root pdbedit yields an empty passdb; must still be a valid list
        users = self.client.list_samba_users()
        self.assertIsInstance(users, list)

    def test_is_service_active_returns_bool(self):
        self.assertIsInstance(self.client.is_service_active(), bool)

    def test_changed_signal_fires(self):
        fired = {"n": 0}
        self.client.subscribe_changed(lambda: fired.__setitem__("n", fired["n"] + 1))
        self.client.write_config(SAMPLE + "\n[newshare]\n\tpath = /srv/new\n")

        ctx = GLib.MainContext.default()
        # iteration(True) blocks on poll so incoming socket data (the Changed
        # signal) is actually delivered; a repeating heartbeat source guarantees
        # we wake up periodically to enforce the deadline.
        heartbeat = GLib.timeout_add(20, lambda: True)
        deadline = GLib.get_monotonic_time() + 3_000_000
        while fired["n"] == 0 and GLib.get_monotonic_time() < deadline:
            ctx.iteration(True)
        GLib.source_remove(heartbeat)
        self.assertGreater(fired["n"], 0, "Changed signal should reach subscribers")


if __name__ == "__main__":
    unittest.main(verbosity=2)
