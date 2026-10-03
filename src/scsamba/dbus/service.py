# -*- coding: utf-8 -*-
"""Privileged D-Bus backend for samba-conf-tool.

Runs as root (via systemd Type=dbus activation) and exposes
org.SambaConfTool.Backend on the system bus. Every mutating method first
checks the org.SambaConfTool.configure polkit action against the caller's
unix user id (see data/polkit/org.SambaConfTool.policy: allow_active=yes).

Test/development escape hatches (never set in production installs):
  SAMBA_CONF_TOOL_BUS=address://...   use a private/session bus instead of the
                                       system bus so the plumbing can be
                                       exercised without touching the real one.
  SAMBA_CONF_TOOL_DISABLE_POLKIT=1    skip the polkit check.
  SAMBA_CONF_TOOL_SMB_CONF=/path      inject an smb.conf path.
  SAMBA_CONF_TOOL_SMBUSERS=/path      inject an smbusers path.
"""

from __future__ import annotations

import os
import sys

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from scsamba import BACKEND_BUS_NAME, BACKEND_OBJECT_PATH, BACKEND_INTERFACE, POLKIT_ACTION
from scsamba.core import SambaBackend, SambaConfig

# Resolve the D-Bus introspection XML. In a source checkout it lives in the
# top-level config/ dir (three levels up from src/scsamba/dbus); once installed
# the Makefile drops it next to this module. An env override wins.
_HERE = os.path.dirname(os.path.abspath(__file__))
_INTRO_XML = os.environ.get("SAMBA_CONF_TOOL_INTRO_XML") or next(
    (p for p in (
        os.path.join(_HERE, "org.SambaConfTool.Backend.xml"),
        os.path.join(_HERE, "..", "..", "..", "config",
                     "org.SambaConfTool.Backend.xml"),
    ) if os.path.exists(p)),
    os.path.join(_HERE, "org.SambaConfTool.Backend.xml"),
)

# Methods that mutate privileged state and therefore require polkit.
_MUTATING = {
    "WriteConfig", "AddSambaUser", "ChangeUserPassword", "SetUserAlias",
    "DeleteSambaUser", "StartService", "RestartService",
}


class BackendService:
    def __init__(self, bus, backend, require_polkit=True):
        self.backend = backend
        self.require_polkit = require_polkit
        self._owner_id = 0

        info = Gio.DBusNodeInfo.new_for_xml(self._load_introspection())
        self.iface_info = info.interfaces[0]

        self._registration_id = bus.register_object(
            object_path=BACKEND_OBJECT_PATH,
            interface_info=self.iface_info,
            method_call_closure=self.on_method_call,
        )
        self.bus = bus

    @staticmethod
    def _load_introspection() -> str:
        with open(_INTRO_XML, "r", encoding="utf-8") as fh:
            return fh.read()

    # ------------------------------------------------------------------ polkit
    def _polkit_allowed(self, sender: str) -> bool:
        if not self.require_polkit:
            return True
        try:
            # polkit >= 127 dropped the "unix-user" subject kind on the
            # CheckAuthorization path: only "unix-process" (pid + start-time)
            # and "unix-session" are accepted. Resolve the *caller's* process so
            # the check runs against the desktop user's active session, not the
            # root backend's own (session-less) one.
            pid = self.bus.call_sync(
                "org.freedesktop.DBus", "/org/freedesktop/DBus",
                "org.freedesktop.DBus", "GetConnectionUnixProcessID",
                GLib.Variant("(s)", (sender,)), GLib.VariantType("(u)"),
                Gio.DBusCallFlags.NONE, -1, None,
            ).get_child_value(0).get_uint32()
            start_time = self._proc_start_time(pid)

            subject = ("unix-process", {
                "pid": GLib.Variant("u", pid),
                "start-time": GLib.Variant("t", start_time),
            })
            # polkit CheckAuthorization signature (verified against the live
            # Authority interface):
            #   in  (sa{sv}) subject, s action_id, a{ss} details,
            #       u flags, s cancellation_id   ->  "((sa{sv})sa{ss}us)"
            #   out (bba{ss}) (is_authorized, is_challenge, details)
            # The destination is the Authority object (not "Manager"). Build the
            # subject from plain Python: nesting a pre-built GLib.Variant("a{sv}")
            # here makes PyGObject re-iterate it and raise KeyError.
            # Pass reply_type=None: the D-Bus reply is a tuple wrapping the
            # (bba{ss}) struct, so child 0 -> child 0 is is_authorized.
            reply = self.bus.call_sync(
                "org.freedesktop.PolicyKit1",
                "/org/freedesktop/PolicyKit1/Authority",
                "org.freedesktop.PolicyKit1.Authority", "CheckAuthorization",
                GLib.Variant("((sa{sv})sa{ss}us)",
                             (subject, POLKIT_ACTION, {}, 0, "")),
                None, Gio.DBusCallFlags.NONE, -1, None,
            )
            result_struct = reply.get_child_value(0)
            return result_struct.get_child_value(0).get_boolean()
        except Exception as e:
            # Fail closed on ANY error (not just GLib.Error): a raised exception
            # here would escape on_method_call before a reply is sent, hanging
            # the client until its D-Bus timeout.
            print("polkit check failed: %s" % e, file=sys.stderr)
            return False

    @staticmethod
    def _proc_start_time(pid: int) -> int:
        # /proc/<pid>/stat field 22 (starttime, clock ticks since boot). The
        # comm field can contain spaces/parens, so split after the last ')';
        # once comm is skipped, field 22 is index 19 of the remainder.
        with open("/proc/%d/stat" % pid, "r") as fh:
            data = fh.read()
        after = data[data.rindex(")") + 2:].split()
        return int(after[19])

    # ------------------------------------------------------------------ dispatch
    # method_call_closure is invoked with exactly these 7 args (no user_data).
    def on_method_call(self, conn, sender, object_path, interface_name,
                       method_name, parameters, invocation):
        if method_name in _MUTATING and not self._polkit_allowed(sender):
            invocation.return_dbus_error(
                "org.SambaConfTool.NotAuthorized",
                "polkit action %s is not authorized for this caller" % POLKIT_ACTION)
            return

        try:
            result = self._dispatch(method_name, parameters)
        except Exception as exc:  # surface backend errors to the client
            invocation.return_dbus_error("org.SambaConfTool.Error", str(exc))
            return

        out_sig = self._out_signature(method_name)
        if out_sig:
            invocation.return_value(GLib.Variant("(s)" if out_sig == "s"
                                                 else "(%s)" % out_sig, result))
        else:
            invocation.return_value(None)

        if method_name in _MUTATING:
            self._emit_changed()

    def _dispatch(self, method_name, params):
        args = params.unpack() if params is not None else ()

        if method_name == "ReadConfig":
            return (self.backend.readSmbConf(),)

        if method_name == "WriteConfig":
            text = args[0]
            # Round-trip through the model so on-disk state and parse cache
            # stay consistent; writeSmbConf validates with testparm.
            self.backend.writeSmbConf(text)
            self.backend.restartSamba()
            return None

        if method_name == "ListSambaUsers":
            self.backend.readSmbPasswords()
            names = [ln.split(":")[0] for ln in self.backend.getPasswdFile() if ln.strip()]
            return (names,)

        if method_name == "GetUserAliasMap":
            self.backend.readSmbUsersFile()
            return (self.backend.get_user_alias_map(),)

        if method_name == "AddSambaUser":
            self.backend.addUser(args[0], args[1], args[2])
            return None

        if method_name == "ChangeUserPassword":
            self.backend.changePassword(args[0], args[1])
            return None

        if method_name == "SetUserAlias":
            self.backend.changeWindowsUserName(args[0], args[1])
            return None

        if method_name == "DeleteSambaUser":
            self.backend.deleteUser(args[0])
            return None

        if method_name == "IsServiceActive":
            return (self.backend.isSambaRunning(),)

        if method_name == "StartService":
            self.backend.startSamba()
            return None

        if method_name == "RestartService":
            self.backend.restartSamba()
            return None

        raise NotImplementedError(method_name)

    def _out_signature(self, method_name):
        return {
            "ReadConfig": "s",
            "ListSambaUsers": "as",
            "GetUserAliasMap": "a{ss}",
            "IsServiceActive": "b",
        }.get(method_name)

    def _emit_changed(self):
        self.bus.emit_signal(None, BACKEND_OBJECT_PATH, BACKEND_INTERFACE,
                             "Changed", GLib.Variant("()", ()))


def _build_bus():
    address = os.environ.get("SAMBA_CONF_TOOL_BUS")
    if address:
        return Gio.DBusConnection.new_for_address_sync(
            address,
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
            | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None, None)
    return Gio.bus_get_sync(Gio.BusType.SYSTEM, None)


def _build_backend():
    return SambaBackend(
        smb_conf_path=os.environ.get("SAMBA_CONF_TOOL_SMB_CONF"),
        smbusers_path=os.environ.get("SAMBA_CONF_TOOL_SMBUSERS"),
    )


def _own_name(bus):
    """Acquire the well-known bus name on the given connection."""
    reply = bus.call_sync(
        "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
        "RequestName", GLib.Variant("(su)", (BACKEND_BUS_NAME, 0x1 | 0x4)),
        GLib.VariantType("(u)"), Gio.DBusCallFlags.NONE, -1, None)
    code = reply.get_child_value(0).get_uint32()
    # 1 = PRIMARY_OWNER, 2 = IN_QUEUE
    if code not in (1, 2):
        raise RuntimeError("failed to acquire bus name %s (code %d)" %
                           (BACKEND_BUS_NAME, code))


def main(argv=None):
    bus = _build_bus()
    require_polkit = os.environ.get("SAMBA_CONF_TOOL_DISABLE_POLKIT") != "1"
    service = BackendService(bus, _build_backend(), require_polkit=require_polkit)
    _own_name(bus)

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
