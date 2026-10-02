ifdef PO_RULES_INCLUDED
$(error po_rules.mk must be included after $(lastword $(MAKEFILE_LIST)))
endif

ifndef PKGNAME
$(error PKGNAME must be set before including $(lastword $(MAKEFILE_LIST)))
endif

ifndef PO_INTLTOOLEXTRACT
PO_INTLTOOLEXTRACT = intltool-extract
endif

ifndef PO_INTLTOOLMERGE
PO_INTLTOOLMERGE = intltool-merge
endif

ifndef DESKTOP_DIR
DESKTOP_DIR			= $(DATADIR)/applications
endif

ifndef DESKTOP_INSTALL
DESKTOP_INSTALL		= $(if $(INSTALL),$(INSTALL),install --verbose)
endif

ifndef DESKTOP_INSTALL_D
DESKTOP_INSTALL_D	= $(DESKTOP_INSTALL) -D
endif

DESKTOPIN_FILES  		= $(wildcard *.desktop.in)
DESKTOPINH_FILES 		= $(patsubst %.desktop.in,%.desktop.in.h,$(DESKTOPIN_FILES))
DESKTOP_FILES			= $(patsubst %.in,%,$(DESKTOPIN_FILES))

%.desktop: %.desktop.in po-update-pot po/*.po
	$(PO_INTLTOOLMERGE) -u -d po/ $< $@

%.desktop.in.h: %.desktop.in
	$(PO_INTLTOOLEXTRACT) -t gettext/ini $<

desktop-all: $(DESKTOP_FILES)

desktop-install: $(DESKTOP_FILES)
	@$(foreach file,$(DESKTOP_FILES),$(DESKTOP_INSTALL_D) -m 0644 $(PKGNAME).desktop $(DESTDIR)$(DESKTOP_DIR)/$(file); )

desktop-clean:
	@rm -fv $(DESKTOP_FILES) $(DESKTOPINH_FILES)
