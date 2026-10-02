# License: GPL v2 or later
# Copyright Red Hat Inc. 2001 - 2009

PKGNAME=system-config-samba

SCM_REMOTEREPO_RE = ^ssh://(.*@)?git.fedorahosted.org/git/$(PKGNAME).git$
UPLOAD_URL = ssh://fedorahosted.org/$(PKGNAME)

PREFIX=/usr
SYSCONFDIR=/etc
BINDIR=${PREFIX}/bin
DATADIR=${PREFIX}/share
MANDIR=${DATADIR}/man
PKGDATADIR=${DATADIR}/${PKGNAME}
PKGIMAGEDIR=${PKGDATADIR}/pixmaps

DBUS_POLICY_DIR=$(SYSCONFDIR)/dbus-1/system.d
DBUS_SERVICE_DIR=$(DATADIR)/dbus-1/system-services

POLKIT_FILES			= config/org.fedoraproject.config.samba.policy.0 \
						  config/org.fedoraproject.config.samba.policy.1

PY_SRC_DIR				= src
PY_SRC_APPS				= addUserWin.py basicPreferencesWin.py mainWindow.py sambaUserWin.py shareWindow.py system-config-samba.py system-config-samba-mechanism.py
_PY_SRC_APPS			= $(patsubst %,$(PY_SRC_DIR)/%,$(PY_SRC_APPS))
PY_SRC_MODULES			= scsamba
_PY_SRC_MODULE_FILES	= $(shell find $(patsubst %,$(PY_SRC_DIR)/%,$(PY_SRC_MODULES)) -type f -a -name "*.py")
PY_SOURCES				= $(_PY_SRC_APPS) $(_PY_SRC_MODULE_FILES)

GLADE_SOURCES			= $(wildcard src/*.glade)

PO_SOURCES				= $(PY_SOURCES) $(PO_GLADEH_FILES) $(DESKTOPINH_FILES) $(POLKITINH_FILES)

all:	py-build po-all polkit-all desktop-all

include rpmspec_rules.mk
include py_rules.mk
include git_rules.mk
include upload_rules.mk
include polkit_rules.mk
include desktop_rules.mk
include po_rules.mk
include icons_rules.mk

install:	all py-install po-install polkit-install desktop-install \
	icons-install
	install -d $(DESTDIR)$(PKGDATADIR)
	install -d $(DESTDIR)$(BINDIR)
	install -d $(DESTDIR)$(PKGIMAGEDIR)

	install -m 0644 $(_PY_SRC_APPS) config/smb.conf.template $(DESTDIR)$(PKGDATADIR)/
	for py in $(_PY_SRC_APPS); do \
		sed -e s,@VERSION@,$(PKGVERSION),g $${py} > $(DESTDIR)$(PKGDATADIR)/`basename $${py}` ; \
	done
	chmod 0755 $(DESTDIR)$(PKGDATADIR)/system-config-samba.py
	chmod 0755 $(DESTDIR)$(PKGDATADIR)/system-config-samba-mechanism.py
	install -m 0644 src/*.glade $(DESTDIR)$(PKGDATADIR)
	softdir=$(PKGDATADIR); \
	if [ -n "$(DESTDIR)" ]; then \
		p=$(DESTDIR) ; \
		softdir=$${softdir/#$$p} ; \
	fi; \
	p=$(PREFIX) ; \
	softdir=$${softdir/#$$p} ; \
	softdir=$${softdir/#\/} ; \
	ln  -fs ../$${softdir}/system-config-samba.py $(DESTDIR)$(BINDIR)/system-config-samba
	install -D -m 0644 config/org.fedoraproject.Config.Samba.conf $(DESTDIR)$(DBUS_POLICY_DIR)/org.fedoraproject.Config.Samba.conf
	install -D -m 0644 config/org.fedoraproject.Config.Samba.service $(DESTDIR)$(DBUS_SERVICE_DIR)/org.fedoraproject.Config.Samba.service

clean: py-clean po-clean polkit-clean desktop-clean
