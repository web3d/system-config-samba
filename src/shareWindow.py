# -*- coding: utf-8 -*-
# Copyright © 2002 - 2010 Red Hat, Inc. (original system-config-samba)
# GTK4 / libadwaita rewrite for system-config-samba.
#
# Share create/edit dialog. Mirrors the fields of the old shareWindow:
# directory (with browse + existence check), auto-suggested share name,
# name de-dup / reserved-word validation, description, writable and
# browseable switches, and the access mode (guest ok for everyone versus an
# explicit "valid users" multi-select). Saving hands a ShareSpec back to the
# caller which mutates the parsed config and writes it through the backend.

from __future__ import annotations

import os
from dataclasses import dataclass, field

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

RESERVED_NAMES = ("global", "homes", "printers")
BAD_NAME_CHARS = set('/\\[]:;|=,+*?<>|')


@dataclass
class ShareSpec:
    name: str
    directory: str
    comment: str
    writable: bool
    browseable: bool
    everyone: bool
    valid_users: list = field(default_factory=list)
    original_name: str | None = None  # None => creating a new share


def suggest_share_name(directory: str) -> str:
    """Best-effort share name from a directory path (old suggestShareName)."""
    path = directory.rstrip("/\\")
    base = os.path.basename(path) if path else ""
    return base or ""


def validate_name(name: str, is_new: bool, existing: set) -> str | None:
    """Return an error message, or None when the name is acceptable."""
    if not name:
        return "Share name must be specified."
    if name.lower() in RESERVED_NAMES:
        return "Share name may not be one of: global, homes, printers."
    bad = sorted({c for c in name if c in BAD_NAME_CHARS})
    if bad:
        return "Share name may not contain: " + " ".join(bad)
    if is_new and name.lower() in {e.lower() for e in existing}:
        return "A share named “%s” already exists." % name
    return None


def validate_directory(directory: str) -> str | None:
    if not directory:
        return "A share must have a directory."
    if not os.path.isabs(directory):
        return "The directory must be an absolute path."
    if not os.path.isdir(directory):
        return "The directory does not exist or is not a folder:\n%s" % directory
    return None


class ShareEditor(Gtk.Window):
    """A modal, transient form window for one share."""

    def __init__(self, parent, spec: ShareSpec | None, users, existing_names,
                 on_apply, *, get_users=None, add_user=None):
        super().__init__()
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_title(_("Create Share") if spec is None
                       else _("Share Properties"))
        self.set_default_size(540, -1)
        self.set_resizable(False)

        self._spec = spec
        self._users = list(users)
        self._existing = set(existing_names)
        self._on_apply = on_apply
        self._get_users = get_users
        self._add_user = add_user
        self._name_edited = spec is not None  # only auto-fill for untouched new

        # Gtk.Window already draws its own CSD titlebar, so we promote our
        # Adw.HeaderBar to be that titlebar instead of stacking a second bar
        # inside a ToolbarView (which would show two duplicate headers).
        header = Adw.HeaderBar()

        cancel = Gtk.Button(label=_("Cancel"))
        cancel.connect("clicked", lambda *_ignored: self.destroy())
        header.pack_start(cancel)

        self._apply_btn = Gtk.Button(label=_("OK"))
        self._apply_btn.add_css_class("suggested-action")
        self._apply_btn.connect("clicked", self._on_apply_clicked)
        header.pack_end(self._apply_btn)
        # Cancel already closes this dialog, so drop the redundant window
        # close button that set_titlebar() would otherwise add after OK.
        header.set_show_end_title_buttons(False)
        self.set_titlebar(header)

        page = Adw.PreferencesPage()
        self.set_child(page)

        # ---- Basic group
        basic = Adw.PreferencesGroup(title=_("Basic"))
        self.dir_row = Adw.EntryRow(title=_("Directory"))
        browse = Gtk.Button(icon_name="folder-open-symbolic", valign=Gtk.Align.CENTER)
        browse.set_tooltip_text(_("Browse for a directory…"))
        browse.connect("clicked", self._on_browse)
        self.dir_row.add_suffix(browse)
        self.dir_row.connect("notify::text", self._on_dir_changed)

        self.name_row = Adw.EntryRow(title=_("Share name"))
        self.name_row.connect("notify::text", self._on_name_changed)

        self.comment_row = Adw.EntryRow(title=_("Description"))
        for row in (self.dir_row, self.name_row, self.comment_row):
            basic.add(row)
        page.add(basic)

        # ---- Access group
        access = Adw.PreferencesGroup(title=_("Access"))
        self.writable_row = Adw.SwitchRow(title=_("Writable"))
        self.browseable_row = Adw.SwitchRow(title=_("Browseable"))
        self.browseable_row.set_active(True)
        self.everyone_row = Adw.SwitchRow(
            title=_("Allow access to everyone"),
            subtitle=_("Guest access, no password (guest ok = yes)"))
        self.everyone_row.connect("notify::active", self._on_everyone_toggled)
        for row in (self.writable_row, self.browseable_row, self.everyone_row):
            access.add(row)
        page.add(access)

        # ---- Allowed users group (only meaningful when not "everyone")
        self.users_group = Adw.PreferencesGroup(title=_("Allowed users"))
        # Entry point for creating a Samba user straight from here: without it
        # a new user has no clue that an account must exist before it can be
        # granted access. Rebuilds the list below once one is added.
        add_user_btn = Gtk.Button()
        add_user_btn.add_css_class("flat")
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_box.append(Gtk.Image.new_from_icon_name("list-add-symbolic"))
        btn_box.append(Gtk.Label(label=_("Add user")))
        add_user_btn.set_child(btn_box)
        add_user_btn.connect("clicked", self._on_add_user_clicked)
        self.users_group.set_header_suffix(add_user_btn)

        self._users_hint = Gtk.Label(xalign=0)
        self._users_hint.set_wrap(True)
        self._users_hint.add_css_class("dim-label")
        self._users_hint.set_margin_top(6)
        self._users_hint.set_margin_bottom(6)
        self._users_hint.set_markup(
            _("No Samba users yet. Use \u201cAdd user\u201d to create one, "
              "or enable guest access above."))
        self.users_group.add(self._users_hint)

        # Rows live in a boxed ListBox (not added straight to the group) so the
        # list can be cleared and rebuilt on refresh after a user is added.
        self.users_list = Gtk.ListBox()
        self.users_list.add_css_class("boxed-list")
        self.users_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.users_group.add(self.users_list)

        self._checkrows = {}
        self._populate_users()
        page.add(self.users_group)

        if spec is not None:
            self._load_spec(spec)
        self._sync_users_visibility()

    # ------------------------------------------------------------------ populate
    def _load_spec(self, spec: ShareSpec):
        self.dir_row.set_text(spec.directory)
        self.name_row.set_text(spec.name)
        self.comment_row.set_text(spec.comment)
        self.writable_row.set_active(spec.writable)
        self.browseable_row.set_active(spec.browseable)
        self.everyone_row.set_active(spec.everyone)
        for uname in spec.valid_users:
            crow = self._checkrows.get(uname)
            if crow is not None:
                crow.set_active(True)

    # ------------------------------------------------------------------ signals
    def _on_dir_changed(self, *_ignored):
        # Auto-suggest the share name from the directory until the user edits
        # the name field themselves (matches the original behaviour).
        if self._name_edited:
            return
        self.name_row.set_text(suggest_share_name(self.dir_row.get_text()))

    def _on_name_changed(self, *args):
        self._name_edited = True

    def _on_everyone_toggled(self, *_ignored):
        self._sync_users_visibility()

    def _sync_users_visibility(self):
        everyone = self.everyone_row.get_active()
        self.users_group.set_visible(not everyone)
        self.users_group.set_sensitive(not everyone)

    # ------------------------------------------------------- allowed users
    def _populate_users(self):
        # Rebuild the "valid users" check rows from self._users, preserving any
        # current selection so a refresh after "Add user" keeps the checks.
        selected = {u for u, c in self._checkrows.items() if c.get_active()}
        row = self.users_list.get_row_at_index(0)
        while row is not None:
            self.users_list.remove(row)
            row = self.users_list.get_row_at_index(0)
        self._checkrows = {}
        for uname in self._users:
            # Gtk.CheckRow is not exposed by this system's GI typelib, so use
            # an Adw.ActionRow with a trailing Gtk.CheckButton holding state.
            action = Adw.ActionRow(title=uname)
            check = Gtk.CheckButton(valign=Gtk.Align.CENTER)
            check.set_active(uname in selected)
            action.add_suffix(check)
            action.set_activatable_widget(check)
            self.users_list.append(action)
            self._checkrows[uname] = check
        has_users = bool(self._users)
        self._users_hint.set_visible(not has_users)
        self.users_list.set_visible(has_users)

    def _refresh_users(self):
        if self._get_users is not None:
            self._users = list(self._get_users())
        self._populate_users()

    def _on_add_user_clicked(self, *_ignored):
        if self._add_user is not None:
            # The parent opens the add-user dialog transient to this window and
            # calls _refresh_users once a new account has been created.
            self._add_user(self, self._refresh_users)

    def _on_browse(self, *_ignored):
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Choose a directory to share"))
        dialog.select_folder(self, None, self._on_folder_chosen, None)

    def _on_folder_chosen(self, dialog, result, _data):
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        if folder is not None:
            self.dir_row.set_text(folder.get_path() or "")

    # ------------------------------------------------------------------ apply
    def _collect(self) -> ShareSpec:
        selected = [u for u, c in self._checkrows.items() if c.get_active()]
        return ShareSpec(
            name=self.name_row.get_text().strip(),
            directory=self.dir_row.get_text().strip(),
            comment=self.comment_row.get_text().strip(),
            writable=self.writable_row.get_active(),
            browseable=self.browseable_row.get_active(),
            everyone=self.everyone_row.get_active(),
            valid_users=selected,
            original_name=self._spec.name if self._spec else None,
        )

    def _on_apply_clicked(self, *_ignored):
        spec = self._collect()
        is_new = self._spec is None
        error = (validate_name(spec.name, is_new, self._existing)
                 or validate_directory(spec.directory))
        if not spec.everyone and not spec.valid_users:
            error = error or _("Select at least one user, or allow everyone.")
        if error:
            self._show_error(error)
            return
        try:
            self._on_apply(spec)
        except Exception as e:  # surfaced from the write callback
            self._show_error(str(e))
            return
        self.destroy()

    def _show_error(self, message: str):
        dlg = Adw.MessageDialog(
            transient_for=self, modal=True, heading=_("Invalid Share"),
            body=message)
        dlg.add_response("ok", _("OK"))
        dlg.set_default_response("ok")
        dlg.present()


# ``gettext`` passthrough hook (catalog wiring lands in a later phase).
def _(*args):
    return args[0] if len(args) == 1 else args
