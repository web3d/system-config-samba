# -*- coding: utf-8 -*-
"""Read-model: turn smb.conf text into displayable share rows.

Kept separate from the GTK widgets so it can be unit-tested headless. Uses
the same token parser as the backend so the UI and the writer agree on what
counts as a share and how its permission/visibility labels read.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .sambaParser import SambaParser

DEFAULT_SMB_CONF = "/etc/samba/smb.conf"


@dataclass
class ShareItem:
    name: str
    directory: str
    writable: bool
    browseable: bool
    comment: str
    # guest ok / valid users for the editor to round-trip
    guest_ok: bool

    @property
    def permissions_label(self) -> str:
        return "Read/Write" if self.writable else "Read Only"

    @property
    def visibility_label(self) -> str:
        return "Visible" if self.browseable else "Hidden"


def _yesno(value, default=False) -> bool:
    if not value:
        return default
    return value.strip().lower() in ("yes", "1", "true")


def parse_shares(text: str):
    """Return (parser, [ShareItem]) parsed from smb.conf text."""
    parser = SambaParser()
    parser.parse(text)
    items = []
    for name in parser.getShareHeaders():
        section = parser.getSection(name)
        # getShareHeaders yields lower-cased keys; keep the on-disk casing so
        # the editor and selection refer to the share by its real name.
        display_name = section.name or name
        # writeable is the inverted synonym of read only; getKey("writeable")
        # resolves the inversion for us.
        writable = _yesno(section.getKey("writeable"), default=False)
        browseable = _yesno(section.getKey("browseable"), default=True)
        guest_ok = _yesno(section.getKey("guest ok"), default=False)
        comment = section.getKey("comment") or ""
        if comment.lower() == "none":
            comment = ""
        items.append(ShareItem(
            name=display_name,
            directory=section.getKey("path") or "",
            writable=writable,
            browseable=browseable,
            comment=comment,
            guest_ok=guest_ok,
        ))
    return parser, items


def load_config_text(client=None, conf_path=None) -> str:
    """Prefer the privileged backend; fall back to a direct read so the list
    can be previewed without root or a running backend."""
    if client is not None:
        try:
            return client.read_config()
        except Exception:
            pass
    path = conf_path or os.environ.get("SAMBA_CONF_TOOL_SMB_CONF") or DEFAULT_SMB_CONF
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return "[global]\n"


def serialize_config(parser) -> str:
    """Render a parsed config back to smb.conf text, preserving the preamble
    and every unrelated token (comments/blank lines)."""
    return "".join(str(parser.getSection(name)) for name in parser.sections)


def service_is_active_local() -> "bool | None":
    """Query the smb service state with plain `systemctl is-active`.

    This is a non-privileged read, so it works even when the root D-Bus
    backend is not installed. Returns True/False, or None if systemctl itself
    could not be consulted (so the caller can show 'unknown' rather than a
    wrong 'not running').
    """
    import subprocess

    units = ["smb.service"]
    try:
        has_nmb = subprocess.run(
            ["systemctl", "cat", "nmb.service"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=10).returncode == 0
        if has_nmb:
            units.append("nmb.service")
    except (OSError, subprocess.SubprocessError):
        pass

    result = False
    for unit in units:
        try:
            out = subprocess.run(
                ["systemctl", "is-active", unit],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None  # cannot tell
        if out == "active":
            result = True
    return result
