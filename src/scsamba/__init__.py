"""system-config-samba: a modern Python 3 + GTK4/libadwaita rewrite.

Original program: system-config-samba (C) Red Hat, Inc. — GPL-2.0-or-later.
This rewrite targets GTK4 + libadwaita and a polkit-gated root backend.
"""

APP_ID = "org.fedoraproject.Config.Samba"
BACKEND_BUS_NAME = "org.fedoraproject.Config.Samba"
BACKEND_OBJECT_PATH = "/org/fedoraproject/Config/Samba"
BACKEND_INTERFACE = "org.fedoraproject.Config.Samba.Backend"
POLKIT_ACTION = "org.fedoraproject.config.samba.configure"

__version__ = "2.0.0"
