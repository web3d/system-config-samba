"""samba-conf-tool: modern Python 3 + GTK4/libadwaita rewrite of system-config-samba.

Original program: system-config-samba (C) Red Hat, Inc. — GPL-2.0-or-later.
This rewrite targets GTK4 + libadwaita and a polkit-gated root backend.
"""

APP_ID = "org.SambaConfTool"
BACKEND_BUS_NAME = "org.SambaConfTool"
BACKEND_OBJECT_PATH = "/org/SambaConfTool/Backend"
BACKEND_INTERFACE = "org.SambaConfTool.Backend"
POLKIT_ACTION = "org.SambaConfTool.configure"

__version__ = "0.1.0"
