# -*- coding: utf-8 -*-
# Copyright © 2002 - 2010 Red Hat, Inc. (original system-config-samba)
# GTK4 / libadwaita rewrite for samba-conf-tool.
#
# Main window: a share list (Directory / Share name / Permissions /
# Visibility / Description) with Add / Properties / Delete actions plus
# Server Settings and Samba Users entries in the primary menu. Selection
# drives the sensitivity of Properties and Delete, as the original did.

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
from gi.repository import Adw, Gio, GLib, Gtk, Pango  # noqa: E402

from scsamba import __version__
from scsamba.core.sambaView import (
    load_config_text, parse_shares, serialize_config, service_is_active_local)
from scsamba.core import SambaSection
from scsamba.dbus.proxy import BackendError, NotAuthorized
from shareWindow import ShareEditor, ShareSpec
from basicPreferencesWin import ServerSettingsDialog, ServerSpec
from sambaUserWin import UsersDialog, _system_users
from addUserWin import AddUserDialog

COLUMNS = ("Directory", "Share name", "Permissions", "Visibility", "Description")
# Fixed per-column widths shared by the header and every data row so the
# column boundaries line up exactly and all cells stay left-aligned; the last
# (Description) column additionally expands to fill the remaining width.
COLUMN_WIDTHS = (260, 150, 130, 120, 200)


class ShareRow(Gtk.Box):
    """One list row: five left-aligned labels laid out proportionally."""

    def __init__(self, *args, **kwargs):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.get_style_context().add_class("share-row")
        self.set_size_request(-1, 34)
        self.labels = []
        for idx, width in enumerate(COLUMN_WIDTHS):
            lbl = Gtk.Label(xalign=0)
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            lbl.set_size_request(width, -1)
            lbl.set_hexpand(idx == len(COLUMN_WIDTHS) - 1)
            self.labels.append(lbl)
            self.append(lbl)

    def bind(self, item):
        vals = (item.directory, item.name, item.permissions_label,
                item.visibility_label, item.comment)
        for lbl, text in zip(self.labels, vals):
            lbl.set_text(text or "")


class SambaMainWindow(Adw.ApplicationWindow):
    def __init__(self, application, client=None):
        super().__init__(application=application)
        self.client = client
        self.set_title(_("Samba Share Configuration"))
        self.set_default_size(940, 600)

        self._parser = None
        self.selected_item = None

        # ---- actions
        for name, handler, accels in (
            ("add-share", self.on_add_share, ["<primary>n"]),
            ("edit-share", self.on_edit_share, ["<primary>p"]),
            ("delete-share", self.on_delete_share, ["<primary>Delete"]),
            ("server-settings", self.on_server_settings, None),
            ("manage-users", self.on_manage_users, None),
            ("reload", lambda *a: self.reload(), ["<primary>r"]),
            ("about", self.on_about, None),
            ("quit", lambda *a: self.destroy(), ["<primary>q"]),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", handler)
            self.add_action(action)
            if accels:
                self.get_application().set_accels_for_action(
                    f"win.{name}", accels)

        self.properties_button = self._header_button(
            "document-edit-symbolic", _("Properties"), "win.edit-share")
        self.delete_button = self._header_button(
            "user-trash-symbolic", _("Delete"), "win.delete-share")
        self.add_button = self._header_button(
            "list-add-symbolic", _("Add Share"), "win.add-share")

        header = Adw.HeaderBar()
        # Primary action (Add) leads the left group; a gap separates it from
        # the row-edit buttons, and another gap separates Reload. The add
        # button no longer sits on the right next to the menu.
        header.pack_start(self.add_button)
        self.properties_button.set_margin_start(12)
        header.pack_start(self.properties_button)
        header.pack_start(self.delete_button)
        self.reload_button = self._header_button(
            "view-refresh-symbolic", _("Reload"), "win.reload")
        self.reload_button.set_margin_start(12)
        header.pack_start(self.reload_button)

        menu = Gio.Menu()
        menu.append(_("Server Settings"), "win.server-settings")
        menu.append(_("Samba Users"), "win.manage-users")
        menu.append(_("About samba-conf-tool"), "win.about")
        menu.append(_("Keyboard Shortcuts"), "win.shortcuts")
        self._menu_button = Gtk.MenuButton(
            icon_name="open-menu-symbolic", menu_model=menu)
        header.pack_end(self._menu_button)

        sc = Gio.SimpleAction.new("shortcuts", None)
        sc.connect("activate", lambda *a: self._show_shortcuts())
        self.add_action(sc)

        # ---- list (Gtk.ListBox keeps this simple in PyGObject)
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_box.add_css_class("data-table")
        self.list_box.connect("row-selected", self._on_row_selected)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self.list_box)
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(self._build_column_header())
        content.append(scrolled)
        content.append(self._build_statusbar())

        self.status = Adw.ToastOverlay(child=content)

        # Adw.ApplicationWindow needs an Adw.ToolbarView to host the header
        # bar; without it the HeaderBar (and its window controls) is never
        # added to the widget tree and the window has no top bar at all.
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(self.status)
        self.set_content(toolbar)
        self._header = header
        self._toolbar = toolbar

        self.reload()

        # A focusable GtkListBox with SINGLE selection auto-selects its first
        # row the moment it receives the window's initial focus, which would
        # highlight a share on startup. Park the initial focus on the (harmless)
        # menu button so the list starts with nothing selected.
        self._menu_button.grab_focus()

    # ------------------------------------------------------------------ helpers
    def _header_button(self, icon, tooltip, action_name):
        btn = Gtk.Button(icon_name=icon)
        btn.set_tooltip_text(tooltip)
        btn.set_action_name(action_name)
        return btn

    def _build_column_header(self):
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header.add_css_class("heading")
        for idx, (title, width) in enumerate(zip(COLUMNS, COLUMN_WIDTHS)):
            lbl = Gtk.Label(xalign=0)
            lbl.set_label(title)
            lbl.set_size_request(width, -1)
            lbl.set_hexpand(idx == len(COLUMN_WIDTHS) - 1)
            header.append(lbl)
        return header

    def _build_statusbar(self):
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        bar.add_css_class("toolbar")
        self.service_status_label = Gtk.Label(xalign=0)
        bar.append(self.service_status_label)
        return bar

    def _make_row(self, item):
        row = Gtk.ListBoxRow()
        box = ShareRow()
        box.bind(item)
        row.set_child(box)
        row.share_name = item.name
        return row

    def _on_row_selected(self, listbox, row):
        has_sel = row is not None
        self.properties_button.set_sensitive(has_sel)
        self.delete_button.set_sensitive(has_sel)

    def _selected_name(self):
        row = self.list_box.get_selected_row()
        return getattr(row, "share_name", None) if row else None

    # ------------------------------------------------------------------ reload
    def reload(self):
        text = load_config_text(self.client)
        parser, items = parse_shares(text)
        self._parser = parser
        # clear existing rows
        row = self.list_box.get_row_at_index(0)
        while row is not None:
            self.list_box.remove(row)
            row = self.list_box.get_row_at_index(0)
        for it in items:
            self.list_box.append(self._make_row(it))
        self._update_button_sensitivity()
        self._refresh_service_status()

    def _update_button_sensitivity(self):
        has_sel = self.list_box.get_selected_row() is not None
        self.properties_button.set_sensitive(has_sel)
        self.delete_button.set_sensitive(has_sel)

    def _refresh_service_status(self):
        # Prefer the authoritative backend view; fall back to a plain
        # (non-privileged) `systemctl is-active` query. Distinguish
        # "unknown" from "not running" so we never misreport.
        active = None
        if self.client is not None:
            try:
                active = self.client.is_service_active()
            except BackendError:
                active = None
        if active is None:
            active = service_is_active_local()

        if active is True:
            text, css = _("SMB service: running"), "success"
        elif active is False:
            text, css = _("SMB service: not running"), "dim-label"
        else:
            text, css = _("SMB service: status unknown"), "warning"
        self.service_status_label.set_text(text)
        for cls in ("success", "dim-label", "warning"):
            self.service_status_label.remove_css_class(cls)
        self.service_status_label.add_css_class(css)

    # ------------------------------------------------------------------ actions
    def on_add_share(self, *_ignored):
        editor = ShareEditor(
            self, spec=None, users=self._get_users(),
            existing_names=[it.name for it in self._items()],
            on_apply=self._apply_share,
            get_users=self._get_users, add_user=self._prompt_add_user)
        editor.present()

    def on_edit_share(self, *_ignored):
        name = self._selected_name()
        if not name:
            return
        editor = ShareEditor(
            self, spec=self._spec_for(name), users=self._get_users(),
            existing_names=[it.name for it in self._items()],
            on_apply=self._apply_share,
            get_users=self._get_users, add_user=self._prompt_add_user)
        editor.present()

    def _prompt_add_user(self, parent, on_added):
        # Open the add-user dialog from inside another dialog (the share editor)
        # and invoke on_added() once a Samba account has actually been created,
        # so the caller can refresh its user list.
        def do_add(unix, windows, password):
            self.client.add_samba_user(unix, windows, password)
            try:
                self.client.set_user_alias(unix, windows)
            except BackendError:
                pass  # alias is best-effort; the account itself was created
            if on_added is not None:
                on_added()
        dlg = AddUserDialog(
            parent, "add",
            system_users=_system_users(),
            existing_samba_users=self._get_users(),
            on_add=do_add)
        dlg.present()

    # ------------------------------------------------------- share read/write
    def _items(self):
        __, items = parse_shares(load_config_text(self.client))
        return items

    def _get_users(self):
        if self.client is None:
            return []
        try:
            return sorted(self.client.list_samba_users())
        except BackendError:
            return []

    def _spec_for(self, name):
        parser, __ = parse_shares(load_config_text(self.client))
        section = parser.getSection(name.lower())
        raw_users = section.getKey("valid users") or ""
        valid_users = [u.strip() for u in raw_users.split(",") if u.strip()]
        comment = section.getKey("comment") or ""
        if comment.lower() == "none":
            comment = ""
        return ShareSpec(
            name=section.name or name,
            directory=section.getKey("path") or "",
            comment=comment,
            writable=_yesno(section.getKey("writeable")),
            browseable=_yesno(section.getKey("browseable"), default=True),
            everyone=_yesno(section.getKey("guest ok")),
            valid_users=valid_users,
            original_name=section.name or name)

    def _apply_share(self, spec: ShareSpec):
        # Runs inside the editor's apply handler: raise to surface an error
        # dialog there; success leaves the editor to close itself.
        if self.client is None:
            raise RuntimeError(_("No backend connected; cannot write."))
        parser, __ = parse_shares(load_config_text(self.client))
        if spec.original_name is None:
            if spec.name.lower() in [s for s in parser.sections if s]:
                raise ValueError(_("A share named \u201c%s\u201d already exists.")
                                 % spec.name)
            section = SambaSection(parser, spec.name)
        else:
            section = parser.getSection(spec.original_name.lower())

        section.setKey("path", spec.directory)
        if spec.comment:
            section.setKey("comment", spec.comment)
        else:
            section.delKey("comment")
        section.setKey("writeable", "yes" if spec.writable else "no")
        section.setKey("browseable", "yes" if spec.browseable else "no")
        if spec.everyone:
            section.setKey("guest ok", "yes")
            section.delKey("valid users")
        else:
            section.setKey("guest ok", "no")
            section.setKey("valid users", ", ".join(spec.valid_users))

        # WriteConfig on the backend already restarts smb after a successful
        # atomic write, so there is no separate restart call here.
        self.client.write_config(serialize_config(parser))
        self.reload()
        self._toast(_("Saved share \u201c%s\u201d.") % spec.name)

    def on_server_settings(self, *_ignored):
        dialog = ServerSettingsDialog(self, self._server_spec(),
                                      on_apply=self._apply_server)
        dialog.present()

    # ------------------------------------------------------ server read/write
    def _global_section(self, parser):
        try:
            return parser.getSection("global")
        except KeyError:
            return SambaSection(parser, "global")

    def _server_spec(self):
        parser, __ = parse_shares(load_config_text(self.client))
        try:
            g = parser.getSection("global")
        except KeyError:
            return ServerSpec("WORKGROUP", "", "user", "", "", True, None)
        guest_ok = _yesno(g.getKey("guest ok"))
        guest_account = g.getKey("guest account") if guest_ok else None
        if guest_account and guest_account.lower() in ("none", "guest"):
            guest_account = "nobody"
        return ServerSpec(
            workgroup=g.getKey("workgroup") or "",
            server_string=g.getKey("server string") or "",
            security=(g.getKey("security") or "user").lower(),
            password_server=g.getKey("password server") or "",
            realm=g.getKey("realm") or "",
            encrypt=_yesno(g.getKey("encrypt passwords"), default=True),
            guest_account=guest_account)

    def _apply_server(self, spec: ServerSpec):
        if self.client is None:
            raise RuntimeError(_("No backend connected; cannot write."))
        parser, __ = parse_shares(load_config_text(self.client))
        g = self._global_section(parser)
        g.setKey("workgroup", spec.workgroup)
        if spec.server_string:
            g.setKey("server string", spec.server_string)
        else:
            g.delKey("server string")
        g.setKey("security", spec.security)
        if spec.security in ("server", "domain", "ads") and spec.password_server:
            g.setKey("password server", spec.password_server)
        else:
            g.delKey("password server")
        if spec.security == "ads" and spec.realm:
            g.setKey("realm", spec.realm)
        else:
            g.delKey("realm")
        g.setKey("encrypt passwords", "yes" if spec.encrypt else "no")
        if spec.guest_account:
            g.setKey("guest ok", "yes")
            g.setKey("guest account", spec.guest_account)
        else:
            g.setKey("guest ok", "no")
            g.setKey("guest account", "nobody")

        # WriteConfig restarts smb internally (see backend dispatch).
        self.client.write_config(serialize_config(parser))
        self.reload()
        self._toast(_("Server settings saved."))

    def on_manage_users(self, *_ignored):
        UsersDialog(self, self.client).present()

    def on_delete_share(self, *_ignored):
        name = self._selected_name()
        if not name:
            return

        confirm = Adw.MessageDialog(
            transient_for=self, modal=True,
            heading=_("Delete share “%s”?") % name,
            body=_("The share section is removed from smb.conf and Samba is restarted."))
        confirm.add_response("cancel", _("Cancel"))
        confirm.add_response("delete", _("Delete"))
        confirm.set_default_response("delete")
        confirm.set_close_response("cancel")
        confirm.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        confirm.connect("response", self._confirm_delete, name)
        confirm.present()

    def _confirm_delete(self, dialog, response, name):
        dialog.destroy()
        if response != "delete":
            return
        if self.client is None:
            self._toast(_("No backend connected; cannot write."))
            return
        parser, __ = parse_shares(load_config_text(self.client))
        section = parser.getSection(name)
        section.delete()
        new_text = "".join(str(parser.getSection(n)) for n in parser.sections)
        try:
            self.client.write_config(new_text)
            self.reload()
            self._toast(_("Deleted share “%s”.") % name)
        except NotAuthorized:
            self._toast(_("Not authorized."))
        except BackendError as e:
            self._toast(_("Write failed: %s") % e)

    # ------------------------------------------------------------ self-check
    def selfcheck_open_dialogs(self):
        """Headlessly construct every dialog so import/widget errors surface
        during the launch smoke test, then discard them."""
        # Structural guard: a constructed-but-detached HeaderBar renders an
        # invisible top bar (no window controls), which a plain construct
        # smoke test would not catch. add_top_bar wraps the bar in internal
        # containers, so check ancestry to the ToolbarView, not the direct
        # parent.
        assert self._header.get_ancestor(Adw.ToolbarView) is self._toolbar, \
            "HeaderBar is not attached to the ToolbarView (no top bar)"
        users = ["nobody", "guest"]
        existing = [it.name for it in self._items()]
        new_editor = ShareEditor(self, spec=None, users=users,
                                 existing_names=existing, on_apply=lambda s: None)
        new_editor._show_error("probe")   # exercise the error-dialog API
        new_editor.destroy()
        if existing:
            edit_editor = ShareEditor(
                self, spec=self._spec_for(existing[0]), users=users,
                existing_names=existing, on_apply=lambda s: None)
            edit_editor.destroy()
        server_dialog = ServerSettingsDialog(
            self, self._server_spec(), on_apply=lambda s: None)
        server_dialog._show_error("probe")
        server_dialog.destroy()
        users_dialog = UsersDialog(self, self.client)
        users_dialog._report(BackendError("probe"))
        users_dialog.destroy()
        add_dlg = AddUserDialog(self, "add", system_users=["root", "nobody"],
                                existing_samba_users=[], on_add=lambda *a: None)
        add_dlg._error("probe")
        add_dlg.destroy()
        AddUserDialog(self, "edit", unix_name="nobody", windows_name="Nobody",
                      on_edit=lambda *a: None).destroy()
        # Guard the two-button confirm API (used by share/user delete) that
        # the construct-only smoke test never touched.
        confirm = Adw.MessageDialog(heading="probe", body="probe")
        confirm.add_response("cancel", "Cancel")
        confirm.add_response("delete", "Delete")
        confirm.set_default_response("delete")
        confirm.set_close_response("cancel")
        confirm.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        confirm.destroy()

    def on_about(self, *_ignored):
        about = Adw.AboutWindow(
            transient_for=self, application_name="samba-conf-tool",
            application_icon="network-server-symbolic",
            developer_name="Rewrite of system-config-samba (C) Red Hat, Inc.",
            version=__version__, license_type=Gtk.License.GPL_2_0)
        about.present()

    def _show_shortcuts(self):
        self._toast(_("Keyboard shortcuts: Ctrl+N add, Ctrl+P edit, "
                      "Ctrl+Delete delete, Ctrl+R reload."))

    def _toast(self, message):
        self.status.add_toast(Adw.Toast(title=message))


def _(*args):
    # gettext passthrough hook (catalog wiring lands in a later phase).
    return args[0] if len(args) == 1 else args


def _yesno(value, default=False) -> bool:
    if not value:
        return default
    return value.strip().lower() in ("yes", "1", "true")
