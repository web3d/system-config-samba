# -*- coding: utf-8 -*-
# Copyright © 2002 - 2010 Red Hat, Inc. (original system-config-samba)
# GTK4 / libadwaita rewrite for samba-conf-tool.
#
# Add / edit Samba user dialog (old addUserWin). "add" picks a system (unix)
# account from pwd, sets a Windows alias and a confirmed password; "edit"
# keeps the unix name fixed, allows renaming the alias, and only changes the
# password when a new one is actually typed.

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402


class AddUserDialog(Gtk.Window):
    def __init__(self, parent, mode, *, unix_name="", windows_name="",
                 system_users=(), existing_samba_users=(),
                 on_add=None, on_edit=None):
        super().__init__()
        assert mode in ("add", "edit")
        self.mode = mode
        self._unix_name = unix_name
        self._orig_windows = windows_name
        self._existing = {u.lower() for u in existing_samba_users}
        self._on_add = on_add
        self._on_edit = on_edit

        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_title(_("Add Samba User") if mode == "add"
                       else _("Samba User Properties"))
        self.set_default_size(480, -1)
        self.set_resizable(False)

        # Gtk.Window draws its own CSD titlebar; promote the Adw.HeaderBar to
        # be it rather than stacking a second bar inside a ToolbarView.
        header = Adw.HeaderBar()
        cancel = Gtk.Button(label=_("Cancel"))
        cancel.connect("clicked", lambda *_ignored: self.destroy())
        header.pack_start(cancel)
        ok = Gtk.Button(label=_("OK"))
        ok.add_css_class("suggested-action")
        ok.connect("clicked", self._on_ok)
        header.pack_end(ok)
        # Cancel already closes this dialog; drop the redundant window close.
        header.set_show_end_title_buttons(False)
        self.set_titlebar(header)

        page = Adw.PreferencesPage()
        self.set_child(page)

        group = Adw.PreferencesGroup()
        page.add(group)

        if mode == "add":
            self.user_row = Adw.ComboRow(
                title=_("System user"),
                model=Gtk.StringList.new(list(system_users)))
            group.add(self.user_row)
        else:
            self.user_row = Adw.EntryRow(title=_("System user"))
            self.user_row.set_text(unix_name)
            self.user_row.set_sensitive(False)
            group.add(self.user_row)

        self.windows_row = Adw.EntryRow(title=_("Windows username"))
        self.windows_row.set_text(windows_name or unix_name)
        group.add(self.windows_row)

        # Picking a system user should prefill the Windows username, but a name
        # the user typed by hand must not be clobbered. Track the last value we
        # auto-filled so we only overwrite an empty or still-untouched field.
        self._last_auto = self.windows_row.get_text()
        if mode == "add":
            self.user_row.connect("notify::selected-item",
                                  self._on_user_selected)

        self.password_row = Adw.PasswordEntryRow(title=_("Password"))
        self.confirm_row = Adw.PasswordEntryRow(title=_("Confirm password"))
        group.add(self.password_row)
        group.add(self.confirm_row)
        if mode == "edit":
            # Adw.PasswordEntryRow has no set_subtitle (that is an ActionRow
            # API); convey the hint in the title instead.
            self.password_row.set_title(
                _("Password (leave blank to keep current)"))
            self.confirm_row.set_visible(False)

    def _on_user_selected(self, *_ignored):
        unix = self._selected_unix()
        current = self.windows_row.get_text()
        if unix and (not current or current == self._last_auto):
            self.windows_row.set_text(unix)
            self._last_auto = unix

    def _selected_unix(self) -> str:
        if self.mode == "add":
            # Gtk.StringList.get_item() returns a StringObject (a GObject
            # wrapper), not a str; use get_string(pos) to get the plain text.
            model = self.user_row.get_model()
            pos = self.user_row.get_selected()
            if 0 <= pos < model.get_n_items():
                return model.get_string(pos)
            return ""
        return self._unix_name

    def _error(self, message):
        dlg = Adw.MessageDialog(
            transient_for=self, modal=True, heading=_("Invalid User"),
            body=message)
        dlg.add_response("ok", _("OK"))
        dlg.set_default_response("ok")
        dlg.present()

    def _on_ok(self, *_ignored):
        unix = self._selected_unix()
        windows = self.windows_row.get_text().strip()
        password = self.password_row.get_text()
        confirm = self.confirm_row.get_text()

        if self.mode == "add":
            if not unix:
                return self._error(_("Select a system user."))
            if not windows:
                return self._error(_("Please enter a Windows username."))
            if not password or password != confirm:
                return self._error(_("The passwords do not match. Please try again."))
            if unix.lower() in self._existing:
                return self._error(_("An account for this user already exists."))
            try:
                self._on_add(unix, windows, password)
            except Exception as e:
                return self._error(str(e))
            self.destroy()
            return

        # edit mode
        if not windows:
            return self._error(_("Please enter a Windows username."))
        if password and password != confirm:
            return self._error(_("The passwords do not match. Please try again."))
        try:
            self._on_edit(unix, windows, password or None)
        except Exception as e:
            return self._error(str(e))
        self.destroy()


def _(*args):
    return args[0] if len(args) == 1 else args
