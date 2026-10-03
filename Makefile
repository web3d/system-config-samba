# samba-conf-tool — install / uninstall helpers.
#
# Layout mirrors upstream system-config-samba: the importable library lives in
# src/scsamba/, the UI + entry scripts are flat modules in src/, and the
# D-Bus / polkit / systemd / desktop / icon integration files live in config/
# and icons/.
#
# The UI installs as a normal Python package (pip-free copy); the privileged
# backend is wired up as a D-Bus activated systemd service with a polkit
# action. System directories require root, so run `sudo make install`.

PYTHON      ?= $(shell command -v python3)
PREFIX      ?= /usr/local
LIBEXECDIR  ?= $(PREFIX)/libexec
DATADIR     ?= $(PREFIX)/share
# Pure-Python package location under $(PREFIX). NOTE: on this Fedora the system
# interpreter does NOT put $(PREFIX)/lib/pythonX.Y/site-packages on its default
# sys.path, so the launchers generated below insert it explicitly.
PYVER       ?= $(shell $(PYTHON) -c 'import sys;print("%d.%d"%sys.version_info[:2])')
SITEPKG     ?= $(PREFIX)/lib/python$(PYVER)/site-packages
BINDIR      ?= $(PREFIX)/bin
SYSTEMDDIR  ?= $(PREFIX)/lib/systemd/system
# Private install dir holding the flat UI/entry scripts (imported at runtime).
APPDIR      ?= $(DATADIR)/samba-conf-tool
SRCDIR      ?= $(APPDIR)/src
# dbus-daemon and polkit only scan fixed system directories, NOT $(PREFIX)/share,
# so these integration files must land in the absolute system locations even for
# a /usr/local install (systemd *does* read $(PREFIX)/lib/systemd/system, and the
# desktop file / icon under /usr/local/share are found via XDG_DATA_DIRS).
DBUS_SYSD   ?= /etc/dbus-1/system.d
DBUS_SERVICES ?= /usr/share/dbus-1/system-services
POLKITDIR   ?= /usr/share/polkit-1/actions
DESKTOPDIR  ?= $(DATADIR)/applications
ICONDIR     ?= $(DATADIR)/icons/hicolor/scalable/apps

# Prepend a staging root (e.g. DESTDIR=/tmp/pkg for packaging).
DESTDIR     ?=

NAME        = samba-conf-tool

.PHONY: all check install uninstall dev-run help
.PHONY: install-python uninstall-python install-backend install-data

all: help

help:
	@echo "Targets:"
	@echo "  make check      run the unit test suite (no root needed)"
	@echo "  make dev-run    launch the UI from the source tree"
	@echo "  sudo make install    install UI + backend + polkit/dbus/systemd"
	@echo "  sudo make uninstall  remove everything install placed"

check:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s src/test -p "test_*.py" -v

dev-run:
	SAMBA_CONF_TOOL_SELFCHECK=0 $(PYTHON) src/system-config-samba.py

# ---------------------------------------------------------------- Python pkg
# Install the scsamba library into site-packages (with the introspection XML
# the backend reads, dropped next to the service module), and the flat UI /
# entry scripts into a private $(SRCDIR).
install-python:
	rm -rf $(DESTDIR)$(SITEPKG)/scsamba
	install -d -m 0755 $(DESTDIR)$(SITEPKG)
	cp -r src/scsamba $(DESTDIR)$(SITEPKG)/
	find $(DESTDIR)$(SITEPKG)/scsamba -name __pycache__ -type d -prune -exec rm -rf {} +
	install -m 0644 config/org.SambaConfTool.Backend.xml \
		$(DESTDIR)$(SITEPKG)/scsamba/dbus/
	rm -rf $(DESTDIR)$(SRCDIR)
	install -d -m 0755 $(DESTDIR)$(SRCDIR)
	install -m 0644 src/*.py $(DESTDIR)$(SRCDIR)/

uninstall-python:
	rm -rf $(DESTDIR)$(SITEPKG)/scsamba
	rm -rf $(DESTDIR)$(APPDIR)
	rm -f $(DESTDIR)$(BINDIR)/$(NAME)

# ------------------------------------------------------------- launchers
# Two thin Python launchers that insert the (non-default) site-packages and the
# private script dir, then runpy the real entry script as __main__.
install-backend: install-python
	install -d -m 0755 $(DESTDIR)$(LIBEXECDIR)
	install -d -m 0755 $(DESTDIR)$(BINDIR)
	printf '#!%s\nimport sys, runpy\nfor p in ("%s", "%s"):\n    if p not in sys.path:\n        sys.path.insert(0, p)\nrunpy.run_path("%s/system-config-samba.py", run_name="__main__")\n' \
		"$(PYTHON)" "$(SRCDIR)" "$(SITEPKG)" "$(SRCDIR)" \
		> $(DESTDIR)$(BINDIR)/$(NAME)
	chmod 0755 $(DESTDIR)$(BINDIR)/$(NAME)
	printf '#!%s\nimport sys, runpy\nfor p in ("%s", "%s"):\n    if p not in sys.path:\n        sys.path.insert(0, p)\nrunpy.run_path("%s/system-config-samba-mechanism.py", run_name="__main__")\n' \
		"$(PYTHON)" "$(SRCDIR)" "$(SITEPKG)" "$(SRCDIR)" \
		> $(DESTDIR)$(LIBEXECDIR)/$(NAME)-backend
	chmod 0755 $(DESTDIR)$(LIBEXECDIR)/$(NAME)-backend

# --------------------------------------------------------- data (root-owned)
install-data: install-backend
	install -d -m 0755 $(DESTDIR)$(SYSTEMDDIR)
	install -d -m 0755 $(DESTDIR)$(DBUS_SYSD)
	install -d -m 0755 $(DESTDIR)$(DBUS_SERVICES)
	install -d -m 0755 $(DESTDIR)$(POLKITDIR)
	install -d -m 0755 $(DESTDIR)$(DESKTOPDIR)
	install -d -m 0755 $(DESTDIR)$(ICONDIR)
	sed -e 's|@python@|$(PYTHON)|g' -e 's|@libexecdir@|$(LIBEXECDIR)|g' \
		config/$(NAME)-backend.service \
		> $(DESTDIR)$(SYSTEMDDIR)/$(NAME)-backend.service
	sed -e 's|@python@|$(PYTHON)|g' -e 's|@libexecdir@|$(LIBEXECDIR)|g' \
		config/org.SambaConfTool.service \
		> $(DESTDIR)$(DBUS_SERVICES)/org.SambaConfTool.service
	install -m 0644 config/org.SambaConfTool.conf \
		$(DESTDIR)$(DBUS_SYSD)/org.SambaConfTool.conf
	sed -e 's|@libexecdir@|$(LIBEXECDIR)|g' \
		config/org.SambaConfTool.policy \
		> $(DESTDIR)$(POLKITDIR)/org.SambaConfTool.policy
	install -m 0644 config/$(NAME).desktop \
		$(DESTDIR)$(DESKTOPDIR)/$(NAME).desktop
	install -m 0644 icons/$(NAME).svg \
		$(DESTDIR)$(ICONDIR)/$(NAME).svg

install: install-data
	@echo "Installed. Reload systemd/D-Bus/polkit so the backend is picked up:"
	@echo "  systemctl daemon-reload"
	@echo "  # the org.SambaConfTool name activates on first call"

uninstall: uninstall-python
	rm -f $(DESTDIR)$(LIBEXECDIR)/$(NAME)-backend
	rm -f $(DESTDIR)$(SYSTEMDDIR)/$(NAME)-backend.service
	rm -f $(DESTDIR)$(DBUS_SERVICES)/org.SambaConfTool.service
	rm -f $(DESTDIR)$(DBUS_SYSD)/org.SambaConfTool.conf
	rm -f $(DESTDIR)$(POLKITDIR)/org.SambaConfTool.policy
	rm -f $(DESTDIR)$(DESKTOPDIR)/$(NAME).desktop
	rm -f $(DESTDIR)$(ICONDIR)/$(NAME).svg
