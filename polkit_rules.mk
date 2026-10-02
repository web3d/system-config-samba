# License: GPL v2 or later
# Copyright Red Hat Inc. 2009

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

ifndef POLKIT0_POLICY_DIR
POLKIT0_POLICY_DIR	= $(DATADIR)/PolicyKit/policy
endif

ifndef POLKIT1_POLICY_DIR
POLKIT1_POLICY_DIR	= $(DATADIR)/polkit-1/actions
endif

ifndef POLKIT_INSTALL
POLKIT_INSTALL		= $(if $(INSTALL),$(INSTALL),install --verbose)
endif

ifndef POLKIT_INSTALL_D
POLKIT_INSTALL_D	= $(POLKIT_INSTALL) -D
endif

_POLKIT0_FILES		= $(filter %.policy %.policy.0,$(POLKIT_FILES))
_POLKIT1_FILES		= $(filter %.policy %.policy.1,$(POLKIT_FILES))
_POLKIT_FILES		= $(sort $(_POLKIT0_FILES) $(_POLKIT1_FILES))

POLKITIN_FILES		= $(patsubst %,%.in,$(POLKIT_FILES))
POLKITINH_FILES		= $(patsubst %.in,%.in.h,$(POLKITIN_FILES))

# default to not installing PolicyKit <= 0.9 files if there aren't any files
# ending in ".0"
ifndef POLKIT0_SUPPORTED
POLKIT0_SUPPORTED	= $(if $(filter %.policy.0,$(POLKIT_FILES)),1,0)
endif

ifndef POLKIT1_SUPPORTED
POLKIT1_SUPPORTED	=
endif

%.policy.in.h: %.policy.in
	$(PO_INTLTOOLEXTRACT) -t gettext/xml $<

%.policy.0.in.h: %.policy.0.in
	$(PO_INTLTOOLEXTRACT) -t gettext/xml $<

%.policy.1.in.h: %.policy.1.in
	$(PO_INTLTOOLEXTRACT) -t gettext/xml $<

%.policy:	%.policy.in po-update-pot po/*.po
	$(PO_INTLTOOLMERGE) -u -x po/ $< $@

%.policy.0:	%.policy.0.in po-update-pot po/*.po
	$(PO_INTLTOOLMERGE) -u -x po/ $< $@

%.policy.1:	%.policy.1.in po-update-pot po/*.po
	$(PO_INTLTOOLMERGE) -u -x po/ $< $@

polkit-all: $(_POLKIT_FILES)

polkit-install: $(_POLKIT_FILES)
ifneq ($(POLKIT0_SUPPORTED),0)
	@$(foreach file,$(_POLKIT0_FILES),$(POLKIT_INSTALL_D) -m 0644 "$(file)" "$(DESTDIR)$(POLKIT0_POLICY_DIR)/$(notdir $(file:.0=))"; )
endif
ifneq ($(POLKIT1_SUPPORTED),0)
	@$(foreach file,$(_POLKIT1_FILES),$(POLKIT_INSTALL_D) -m 0644 "$(file)" "$(DESTDIR)$(POLKIT1_POLICY_DIR)/$(notdir $(file:.1=))"; )
endif

polkit-clean:
	@rm -fv $(POLKITINH_FILES) $(POLKIT_FILES)
