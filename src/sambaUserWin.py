# -*- coding: utf-8 -*-
# Copyright © 2002 - 2010 Red Hat, Inc. (original system-config-samba)
# GTK4 / libadwaita rewrite for system-config-samba.
#
# Samba user management window (old sambaUserWin). Lists the pdbedit users
# with their smbusers Windows aliases and offers Add / Properties / Delete.
# Every mutating action goes through the privileged backend (polkit-gated);
# without a backend the list is simply empty and writes report why.

from __future__ import annotations

import pwd

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from scsamba.dbus.proxy import BackendError, NotAuthorized
from addUserWin import AddUserDialog


def _system_users():
    return sorted({pw.pw_name for pw in pwd.getpwall()})


class _UserRow(Gtk.ListBoxRow):
    def __init__(self, unix_name, windows_name):
        super().__init__()
        self.unix_name = unix_name
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(12)
        box.set_margin_end(12)
        name = Gtk.Label(xalign=0)
        name.set_text(unix_name)
        name.set_size_request(220, -1)
        alias = Gtk.Label(xalign=0)
        alias.set_text(windows_name)
        alias.add_css_class("dim-label")
        alias.set_hexpand(True)
        alias.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        box.append(name)
        box.append(alias)
        self.set_child(box)


class UsersDialog(Gtk.Window):
    def __init__(self, parent, client):
        super().__init__()
        self.client = client
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_title(_("Samba Users"))
        self.set_default_size(600, 440)

        # Gtk.Window draws its own CSD titlebar; promote the Adw.HeaderBar to
        # be it rather than stacking a second bar inside a ToolbarView.
        header = Adw.HeaderBar()

        # Match the main window: the primary Add action leads the left group,
        # a gap separates it from the row-edit buttons (Properties, Delete).
        add_btn = Gtk.Button(icon_name="list-add-symbolic")
        add_btn.set_tooltip_text(_("Add Samba user"))
        add_btn.connect("clicked", self.on_add)
        header.pack_start(add_btn)

        self.edit_btn = Gtk.Button(icon_name="document-edit-symbolic")
        self.edit_btn.set_tooltip_text(_("Properties"))
        self.edit_btn.set_sensitive(False)
        self.edit_btn.set_margin_start(12)
        self.edit_btn.connect("clicked", self.on_edit)
        header.pack_start(self.edit_btn)

        self.delete_btn = Gtk.Button(icon_name="user-trash-symbolic")
        self.delete_btn.set_tooltip_text(_("Delete user"))
        self.delete_btn.set_sensitive(False)
        self.delete_btn.connect("clicked", self.on_delete)
        header.pack_start(self.delete_btn)

        self.set_titlebar(header)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_box.add_css_class("boxed-list")
        self.list_box.connect("row-selected", self._on_row_selected)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=12,
                        margin_bottom=12, margin_start=12, margin_end=12)
        # Column header for the two fields each _UserRow shows. Kept above the
        # boxed-list (not as a list row) so it reads as a table header; its
        # margins and first-column width mirror _UserRow so labels line up.
        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header_row.set_margin_start(12)
        header_row.set_margin_end(12)
        header_row.set_margin_top(6)
        header_row.set_margin_bottom(6)
        col_user = Gtk.Label(xalign=0)
        col_user.set_text(_("System user"))
        col_user.set_size_request(220, -1)
        col_user.add_css_class("dim-label")
        col_alias = Gtk.Label(xalign=0)
        col_alias.set_text(_("Windows username"))
        col_alias.add_css_class("dim-label")
        col_alias.set_hexpand(True)
        header_row.append(col_user)
        header_row.append(col_alias)
        self.empty_notice = Gtk.Label()
        self.empty_notice.add_css_class("dim-label")
        self.empty_notice.set_wrap(True)
        inner.append(header_row)
        inner.append(self.empty_notice)
        inner.append(scrolled)
        scrolled.set_child(self.list_box)
        self.set_child(inner)

        self.refresh()

    # ------------------------------------------------------------------ data
    def _safe(self, method, default):
        # Take the method name (not a bound call) so that a None client never
        # triggers attribute access at the call site.
        if self.client is None:
            return default
        try:
            return getattr(self.client, method)()
        except BackendError:
            return default

    def refresh(self):
        users = self._safe("list_samba_users", [])
        aliases = self._safe("get_user_alias_map", {})
        row = self.list_box.get_row_at_index(0)
        while row is not None:
            self.list_box.remove(row)
            row = self.list_box.get_row_at_index(0)
        for unix in sorted(users):
            self.list_box.append(_UserRow(unix, aliases.get(unix, unix)))
        has_users = bool(users)
        self.empty_notice.set_visible(not has_users)
        if self.client is None:
            self.empty_notice.set_text(
                _("The privileged backend is not connected, so Samba users "
                  "cannot be listed or edited. Install and start "
                  "system-config-samba-backend to manage users."))
        elif not has_users:
            self.empty_notice.set_text(_("No Samba users yet."))
        self._update_sensitivity()

    def _selected(self):
        row = self.list_box.get_selected_row()
        return row.unix_name if row else None

    def _on_row_selected(self, *_ignored):
        self._update_sensitivity()

    def _update_sensitivity(self):
        has_sel = self._selected() is not None
        self.edit_btn.set_sensitive(has_sel)
        self.delete_btn.set_sensitive(has_sel)

    # ------------------------------------------------------------------ errors
    def _report(self, exc):
        if isinstance(exc, NotAuthorized):
            msg = _("Not authorized: the polkit action was declined.")
        else:
            msg = _("Operation failed: %s") % exc
        dlg = Adw.MessageDialog(transient_for=self, modal=True,
                                heading=_("User Management"), body=msg)
        dlg.add_response("ok", _("OK"))
        dlg.set_default_response("ok")
        dlg.present()

    # ------------------------------------------------------------------ actions
    def on_add(self, *_ignored):
        dlg = AddUserDialog(
            self, "add",
            system_users=_system_users(),
            existing_samba_users=self._safe("list_samba_users", []),
            on_add=self._do_add)
        dlg.present()

    def _do_add(self, unix, windows, password):
        self.client.add_samba_user(unix, windows, password)
        try:
            self.client.set_user_alias(unix, windows)
        except BackendError:
            pass  # alias is best-effort; the account itself was created
        self.refresh()

    def on_edit(self, *_ignored):
        unix = self._selected()
        if not unix:
            return
        aliases = self._safe("get_user_alias_map", {})
        dlg = AddUserDialog(
            self, "edit", unix_name=unix, windows_name=aliases.get(unix, unix),
            on_edit=lambda u, w, p: self._do_edit(u, w, p))
        dlg.present()

    def _do_edit(self, unix, windows, password):
        if password:
            self.client.change_user_password(unix, password)
        self.client.set_user_alias(unix, windows)
        self.refresh()

    def on_delete(self, *_ignored):
        unix = self._selected()
        if not unix:
            return
        confirm = Adw.MessageDialog(
            transient_for=self, modal=True,
            heading=_("Delete Samba user \u201c%s\u201d?") % unix,
            body=_("The account is removed from the Samba password database."))
        confirm.add_response("cancel", _("Cancel"))
        confirm.add_response("delete", _("Delete"))
        confirm.set_default_response("delete")
        confirm.set_close_response("cancel")
        confirm.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        confirm.connect("response", self._confirm_delete, unix)
        confirm.present()

    def _confirm_delete(self, dialog, response, unix):
        dialog.destroy()
        if response != "delete":
            return
        try:
            self.client.delete_samba_user(unix)
            self.refresh()
        except Exception as e:
            self._report(e)


def _(*args):
    return args[0] if len(args) == 1 else args
