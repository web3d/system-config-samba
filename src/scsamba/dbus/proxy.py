# -*- coding: utf-8 -*-
"""Front-end D-Bus proxy for samba-conf-tool.

The UI runs as an unprivileged user and talks to the root backend over the
system bus. Reads (ReadConfig / ListSambaUsers / IsServiceActive) are cheap;
writes trigger a polkit authorisation inside the backend.

SAMBA_CONF_TOOL_BUS=address://... lets tests point the client at a private
bus instead of the real system bus.
"""

from __future__ import annotations

import os

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from scsamba import BACKEND_BUS_NAME, BACKEND_OBJECT_PATH, BACKEND_INTERFACE


class BackendError(Exception):
    pass


class BackendNotInstalled(BackendError):
    """The privileged org.SambaConfTool backend is not installed/activatable."""
    pass


class NotAuthorized(BackendError):
    pass


class BackendClient:
    def __init__(self, bus=None):
        self.bus = bus or self._default_bus()

    @staticmethod
    def _default_bus():
        address = os.environ.get("SAMBA_CONF_TOOL_BUS")
        if address:
            return Gio.DBusConnection.new_for_address_sync(
                address,
                Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
                | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
                None, None)
        return Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

    def _call(self, method, params, out_type):
        try:
            return self.bus.call_sync(
                BACKEND_BUS_NAME, BACKEND_OBJECT_PATH, BACKEND_INTERFACE,
                method, params, GLib.VariantType(out_type) if out_type else None,
                Gio.DBusCallFlags.NONE, -1, None)
        except GLib.Error as e:
            if e.domain == "g-dbus-error" and \
                    e.message.startswith("GDBus.Error:org.SambaConfTool.NotAuthorized"):
                raise NotAuthorized(e.message) from e
            if "ServiceUnknown" in e.message or "not activatable" in e.message:
                raise BackendNotInstalled(
                    "The privileged backend is not installed, so changes "
                    "cannot be saved. Run `sudo make install` to install "
                    "the samba-conf-tool backend service, then restart the "
                    "application.") from e
            raise BackendError(e.message) from e

    # ------------------------------------------------------------------ reads
    def read_config(self) -> str:
        return self._call("ReadConfig", None, "(s)").get_child_value(0).get_string()

    def list_samba_users(self):
        reply = self._call("ListSambaUsers", None, "(as)")
        return list(reply.get_child_value(0).unpack())

    def get_user_alias_map(self):
        reply = self._call("GetUserAliasMap", None, "(a{ss})")
        return dict(reply.get_child_value(0).unpack())

    def is_service_active(self) -> bool:
        return self._call("IsServiceActive", None, "(b)").get_child_value(0).get_boolean()

    # ---------------------------------------------------------------- writes
    def write_config(self, text: str):
        self._call("WriteConfig", GLib.Variant("(s)", (text,)), None)

    def add_samba_user(self, unix_name, windows_name, password):
        self._call("AddSambaUser",
                   GLib.Variant("(sss)", (unix_name, windows_name, password)), None)

    def change_user_password(self, unix_name, password):
        self._call("ChangeUserPassword", GLib.Variant("(ss)", (unix_name, password)), None)

    def set_user_alias(self, unix_name, windows_name):
        self._call("SetUserAlias", GLib.Variant("(ss)", (unix_name, windows_name)), None)

    def delete_samba_user(self, unix_name):
        self._call("DeleteSambaUser", GLib.Variant("(s)", (unix_name,)), None)

    def start_service(self):
        self._call("StartService", None, None)

    def restart_service(self):
        self._call("RestartService", None, None)

    # ---------------------------------------------------------------- signals
    def subscribe_changed(self, callback):
        def on_signal(conn, sender, path, interface, signal, params, user_data):
            if interface == BACKEND_INTERFACE and signal == "Changed":
                callback()
        return self.bus.signal_subscribe(
            None, BACKEND_INTERFACE, "Changed", BACKEND_OBJECT_PATH, None,
            Gio.DBusSignalFlags.NONE, on_signal, None)
