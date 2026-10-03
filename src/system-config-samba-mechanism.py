#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Privileged backend launcher for system-config-samba.

Thin entry point that mirrors upstream's system-config-samba-mechanism.py: the
real polkit-gated D-Bus service lives in :mod:`scsamba.dbus.service`. The
systemd ``Type=dbus`` unit Execs this script, which owns the bus name and
serves client calls as root.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scsamba.dbus.service import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
