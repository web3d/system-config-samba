# License: GPL v2 or later
# Copyright Red Hat Inc. 2001 - 2009  (original system-config-samba)
#
# GTK4 / Python 3 rewrite build.
#
# This keeps the upstream autotools-style variable layout (PKGNAME / PKGDATADIR
# / standard FHS dirs) but is SELF-CONTAINED: it does NOT include the retired
# `*_rules.mk` python2 fragments (they are gone and only run under the old RPM
# toolchain). Instead it installs the Python 3 payload pip-free and drops the
# D-Bus / polkit / systemd / desktop / icon integration files renamed to the
# upstream identity (org.fedoraproject.Config.Samba / system-config-samba).

PKGNAME  = system-config-samba
NAME     = system-config-samba
VERSION  = 2.0.0

PYTHON   ?= $(shell command -v python3)

# Staging root for packaging (e.g. DESTDIR=/tmp/pkg).
DESTDIR  ?=

# --- install layout -------------------------------------------------------
# PREFIX defaults to /usr/local so a locally built rewrite never fights the
# legacy RPM's files under /usr. Override with `make install PREFIX=/usr`.
PREFIX      ?= /usr/local
BINDIR       = $(PREFIX)/bin
LIBEXECDIR   = $(PREFIX)/libexec
DATADIR      = $(PREFIX)/share
SYSTEMDDIR   = $(PREFIX)/lib/systemd/system
PKGDATADIR   = $(DATADIR)/$(PKGNAME)
# The whole Python payload (flat UI/entry scripts + the scsamba package + the
# D-Bus introspection XML) is installed under PKGDATADIR; the launchers insert
# it on sys.path, so no site-packages juggling is needed.
SITEPKG      =

# dbus-daemon and polkit only scan fixed system directories, NOT $(PREFIX)/share,
# so these land in absolute system locations even for a /usr/local install
# (systemd *does* read $(PREFIX)/lib/systemd/system; the desktop file / icon
# under /usr/local/share are found via XDG_DATA_DIRS).
DBUS_POLICY_DIR  = /etc/dbus-1/system.d
DBUS_SERVICE_DIR = /usr/share/dbus-1/system-services
POLKITDIR        = /usr/share/polkit-1/actions
DESKTOPDIR       = $(DATADIR)/applications
ICONDIR          = $(DATADIR)/icons/hicolor/scalable/apps

# Upstream identity (kept in sync with src/scsamba/__init__.py).
BUS_NAME        = org.fedoraproject.Config.Samba
POLKIT_ID       = org.fedoraproject.config.samba

UI_SRC     = src/system-config-samba.py
MECH_SRC   = src/system-config-samba-mechanism.py

.PHONY: all help check dev-run install uninstall

all: help

help:
	@echo "system-config-samba $(VERSION) — GTK4 / Python 3 rewrite"
	@echo "Targets:"
	@echo "  make check         run the unit test suite (no root needed)"
	@echo "  make dev-run       launch the UI straight from the source tree"
	@echo "  sudo make install  install UI + backend + dbus/polkit/systemd/desktop/icon"
	@echo "  sudo make uninstall  remove everything install placed"

check:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s src/test -p "test_*.py" -v

dev-run:
	SYSTEM_CONFIG_SAMBA_SELFCHECK=0 $(PYTHON) $(UI_SRC)

# ---------------------------------------------------------------------------
# Install.  Order: python payload -> launchers -> integration files.
# ---------------------------------------------------------------------------
install: install-python install-launchers install-data
	@echo "Installed system-config-samba $(VERSION) under $(DESTDIR)$(PREFIX)."
	@echo "Reload systemd/D-Bus/polkit so the backend is picked up:"
	@echo "  systemctl daemon-reload"
	@echo "  # the $(BUS_NAME) name activates on first call"

# Python payload: flat UI/entry scripts + importable scsamba package + the
# D-Bus introspection XML (dropped next to the service module the backend
# reads it from at runtime).
install-python:
	rm -rf $(DESTDIR)$(PKGDATADIR)
	install -d -m 0755 $(DESTDIR)$(PKGDATADIR)
	cp -r src/scsamba $(DESTDIR)$(PKGDATADIR)/
	install -m 0644 src/*.py $(DESTDIR)$(PKGDATADIR)/
	find $(DESTDIR)$(PKGDATADIR) -name __pycache__ -type d -prune -exec rm -rf {} +
	install -m 0644 config/$(BUS_NAME).Backend.xml \
		$(DESTDIR)$(PKGDATADIR)/scsamba/dbus/
	chmod 0755 $(DESTDIR)$(PKGDATADIR)/$(notdir $(UI_SRC)) \
		$(DESTDIR)$(PKGDATADIR)/$(notdir $(MECH_SRC))

# Two thin launchers that insert PKGDATADIR on sys.path and runpy the real
# entry script as __main__. The UI launcher goes to $(BINDIR); the privileged
# backend launcher goes to $(LIBEXECDIR) and is what the systemd Type=dbus
# unit Execs.
install-launchers: install-python
	install -d -m 0755 $(DESTDIR)$(BINDIR)
	install -d -m 0755 $(DESTDIR)$(LIBEXECDIR)
	printf '#!%s\nimport sys, runpy\nP = "%s"\nif P not in sys.path:\n    sys.path.insert(0, P)\nrunpy.run_path(P + "/$(PKGNAME).py", run_name="__main__")\n' \
		"$(PYTHON)" "$(PKGDATADIR)" \
		> $(DESTDIR)$(BINDIR)/$(NAME)
	chmod 0755 $(DESTDIR)$(BINDIR)/$(NAME)
	printf '#!%s\nimport sys, runpy\nP = "%s"\nif P not in sys.path:\n    sys.path.insert(0, P)\nrunpy.run_path(P + "/$(PKGNAME)-mechanism.py", run_name="__main__")\n' \
		"$(PYTHON)" "$(PKGDATADIR)" \
		> $(DESTDIR)$(LIBEXECDIR)/$(NAME)-backend
	chmod 0755 $(DESTDIR)$(LIBEXECDIR)/$(NAME)-backend

# Integration files.  @python@ / @libexecdir@ placeholders are substituted so
# the shipped files carry the real absolute paths of this install.
install-data:
	install -d -m 0755 $(DESTDIR)$(SYSTEMDDIR)
	install -d -m 0755 $(DESTDIR)$(DBUS_POLICY_DIR)
	install -d -m 0755 $(DESTDIR)$(DBUS_SERVICE_DIR)
	install -d -m 0755 $(DESTDIR)$(POLKITDIR)
	install -d -m 0755 $(DESTDIR)$(DESKTOPDIR)
	install -d -m 0755 $(DESTDIR)$(ICONDIR)
	sed -e 's|@python@|$(PYTHON)|g' -e 's|@libexecdir@|$(LIBEXECDIR)|g' \
		config/$(NAME)-backend.service \
		> $(DESTDIR)$(SYSTEMDDIR)/$(NAME)-backend.service
	sed -e 's|@python@|$(PYTHON)|g' -e 's|@libexecdir@|$(LIBEXECDIR)|g' \
		config/$(BUS_NAME).service \
		> $(DESTDIR)$(DBUS_SERVICE_DIR)/$(BUS_NAME).service
	install -m 0644 config/$(BUS_NAME).conf \
		$(DESTDIR)$(DBUS_POLICY_DIR)/$(BUS_NAME).conf
	sed -e 's|@libexecdir@|$(LIBEXECDIR)|g' \
		config/$(POLKIT_ID).policy \
		> $(DESTDIR)$(POLKITDIR)/$(POLKIT_ID).policy
	install -m 0644 config/$(NAME).desktop \
		$(DESTDIR)$(DESKTOPDIR)/$(NAME).desktop
	install -m 0644 icons/$(NAME).svg \
		$(DESTDIR)$(ICONDIR)/$(NAME).svg

# ---------------------------------------------------------------------------
uninstall:
	rm -rf $(DESTDIR)$(PKGDATADIR)
	rm -f $(DESTDIR)$(BINDIR)/$(NAME)
	rm -f $(DESTDIR)$(LIBEXECDIR)/$(NAME)-backend
	rm -f $(DESTDIR)$(SYSTEMDDIR)/$(NAME)-backend.service
	rm -f $(DESTDIR)$(DBUS_SERVICE_DIR)/$(BUS_NAME).service
	rm -f $(DESTDIR)$(DBUS_POLICY_DIR)/$(BUS_NAME).conf
	rm -f $(DESTDIR)$(POLKITDIR)/$(POLKIT_ID).policy
	rm -f $(DESTDIR)$(DESKTOPDIR)/$(NAME).desktop
	rm -f $(DESTDIR)$(ICONDIR)/$(NAME).svg
