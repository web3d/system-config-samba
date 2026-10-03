# -*- coding: utf-8 -*-
# Copyright © 2002 - 2010 Red Hat, Inc. (original system-config-samba)
# GTK4 / libadwaita rewrite for system-config-samba.
#
# Server settings dialog (old basicPreferencesWin). Edits the [global]
# section: workgroup (required), server string, security mode with the
# password-server / realm linkage and the domain forced-encryption rule,
# encrypt passwords, and the guest account chosen from the system password
# database.

from __future__ import annotations

import pwd
from dataclasses import dataclass

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

# Order mirrors the original auth_option_menu (ADS, Domain, Server, Share,
# User); the value written to smb.conf is the lower-cased security= token.
SECURITY_MODES = [
    ("ADS", "ads"),
    ("Domain", "domain"),
    ("Server", "server"),
    ("Share", "share"),
    ("User", "user"),
]
SECURITY_VALUES = [v for _label, v in SECURITY_MODES]
NO_GUEST_LABEL = "No guest account"


@dataclass
class ServerSpec:
    workgroup: str
    server_string: str
    security: str
    password_server: str
    realm: str
    encrypt: bool
    guest_account: str | None  # None => guest access disabled


def _system_users():
    names = {pw.pw_name for pw in pwd.getpwall()}
    return sorted(names)


def validate_server(spec: ServerSpec) -> str | None:
    if not spec.workgroup.strip():
        return "You must specify a workgroup."
    if spec.security in ("server", "domain", "ads"):
        if not spec.password_server.strip():
            return ('To auto-locate a password server, enter "*" in the '
                    'Password server field. Otherwise a password server is '
                    'required for ADS, Domain or Server security.')
    if spec.security == "ads" and not spec.realm.strip():
        return "Please enter a Kerberos realm when using ADS security."
    return None


class ServerSettingsDialog(Gtk.Window):
    def __init__(self, parent, spec: ServerSpec, on_apply):
        super().__init__()
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_title(_("Server Settings"))
        self.set_default_size(560, -1)
        self.set_resizable(False)
        self._on_apply = on_apply

        # Gtk.Window draws its own CSD titlebar; promote the Adw.HeaderBar to
        # be it rather than stacking a second bar inside a ToolbarView.
        header = Adw.HeaderBar()
        cancel = Gtk.Button(label=_("Cancel"))
        cancel.connect("clicked", lambda *_ignored: self.destroy())
        header.pack_start(cancel)
        ok = Gtk.Button(label=_("OK"))
        ok.add_css_class("suggested-action")
        ok.connect("clicked", self._on_ok_clicked)
        header.pack_end(ok)
        # Cancel already closes this dialog; drop the redundant window close.
        header.set_show_end_title_buttons(False)
        self.set_titlebar(header)

        page = Adw.PreferencesPage()
        self.set_child(page)

        # ---- Identity
        identity = Adw.PreferencesGroup(title=_("Identity"))
        self.workgroup_row = Adw.EntryRow(title=_("Workgroup"))
        self.server_string_row = Adw.EntryRow(title=_("Server description"))
        identity.add(self.workgroup_row)
        identity.add(self.server_string_row)
        page.add(identity)

        # ---- Security
        security = Adw.PreferencesGroup(title=_("Security"))
        self.security_row = Adw.ComboRow(
            title=_("Security mode"),
            model=Gtk.StringList.new([label for label, _v in SECURITY_MODES]))
        self.security_row.connect("notify::selected", self._sync_sensitivity)
        self.password_server_row = Adw.EntryRow(title=_("Password server"))
        self.realm_row = Adw.EntryRow(title=_("Realm"))
        self.encrypt_row = Adw.ComboRow(
            title=_("Encrypt passwords"), model=Gtk.StringList.new(["Yes", "No"]))
        for row in (self.security_row, self.password_server_row,
                    self.realm_row, self.encrypt_row):
            security.add(row)
        page.add(security)

        # ---- Guest access
        guest = Adw.PreferencesGroup(title=_("Guest access"))
        users = [NO_GUEST_LABEL] + _system_users()
        self.guest_row = Adw.ComboRow(
            title=_("Guest account"), model=Gtk.StringList.new(users))
        guest.add(self.guest_row)
        page.add(guest)

        self._load_spec(spec)
        self._sync_sensitivity()

    def _index_of(self, values, value, default):
        try:
            return values.index(value.lower())
        except ValueError:
            return default

    def _load_spec(self, spec: ServerSpec):
        self.workgroup_row.set_text(spec.workgroup)
        self.server_string_row.set_text(spec.server_string)
        self.security_row.set_selected(
            self._index_of(SECURITY_VALUES, spec.security,
                           SECURITY_VALUES.index("user")))
        self.password_server_row.set_text(spec.password_server)
        self.realm_row.set_text(spec.realm)
        self.encrypt_row.set_selected(0 if spec.encrypt else 1)
        users_model = self.guest_row.get_model()
        target = spec.guest_account or NO_GUEST_LABEL
        idx = 0
        for i in range(users_model.get_n_items()):
            if users_model.get_string(i) == target:
                idx = i
                break
        self.guest_row.set_selected(idx)

    def _current_security(self) -> str:
        return SECURITY_VALUES[self.security_row.get_selected()]

    def _sync_sensitivity(self, *_ignored):
        sec = self._current_security()
        needs_server = sec in ("server", "domain", "ads")
        self.password_server_row.set_sensitive(needs_server)
        self.realm_row.set_sensitive(sec == "ads")
        if sec == "domain":
            # Domain security mandates encrypted passwords.
            self.encrypt_row.set_selected(0)
            self.encrypt_row.set_sensitive(False)
        else:
            self.encrypt_row.set_sensitive(True)

    def _collect(self) -> ServerSpec:
        guest_idx = self.guest_row.get_selected()
        guest_account = None
        if guest_idx > 0:
            # get_item() yields a StringObject; get_string() gives the plain str.
            guest_account = self.guest_row.get_model().get_string(guest_idx)
        return ServerSpec(
            workgroup=self.workgroup_row.get_text().strip().lower(),
            server_string=self.server_string_row.get_text().strip(),
            security=self._current_security(),
            password_server=self.password_server_row.get_text().strip(),
            realm=self.realm_row.get_text().strip(),
            encrypt=self.encrypt_row.get_selected() == 0,
            guest_account=guest_account,
        )

    def _on_ok_clicked(self, *_ignored):
        spec = self._collect()
        error = validate_server(spec)
        if error:
            self._show_error(error)
            return
        try:
            self._on_apply(spec)
        except Exception as e:
            self._show_error(str(e))
            return
        self.destroy()

    def _show_error(self, message: str):
        dlg = Adw.MessageDialog(
            transient_for=self, modal=True, heading=_("Invalid Settings"),
            body=message)
        dlg.add_response("ok", _("OK"))
        dlg.set_default_response("ok")
        dlg.present()


def _(*args):
    return args[0] if len(args) == 1 else args
