# License: GPL v2 or later
# Copyright Red Hat Inc. 2009

ifndef PO_RULES_INCLUDED
PO_RULES_INCLUDED	= 1

PO_POTFILE		= po/$(PKGNAME).pot
PO_INSTALL		= /usr/bin/install -c
PO_INSTALL_DATA	= $(PO_INSTALL) -m 644
PO_INSTALL_DIR	= /usr/bin/install -d

# destination directory
PO_INSTALL_NLS_DIR = $(DESTDIR)$(DATADIR)/locale

# commands
PO_DIFF		= /usr/bin/diff
PO_GREP		= /bin/grep

# PO catalog handling
PO_MSGMERGE	= msgmerge -v -N
PO_XGETTEXT	= xgettext --from-code=utf-8 --default-domain=$(PKGNAME) \
		  --add-comments
PO_MSGFMT		= msgfmt --statistics --verbose
PO_INTLTOOLEXTRACT = intltool-extract
PO_INTLTOOLMERGE = intltool-merge

# What do we need to do
PO_POFILES		= $(wildcard po/*.po)
PO_MOFILES		= $(patsubst %.po,%.mo,$(PO_POFILES))
PO_GLADEH_FILES	= $(patsubst %.glade,%.glade.h,$(GLADE_SOURCES))

po-all: po-update-po $(PO_MOFILES)

po_diff_and_mv_or_rm  = \
	if [ ! -f "$(1)" ] || ($(PO_DIFF) "$(1)" "$(2)" | $(PO_GREP) -v '^. "POT-Creation-Date:' | $(PO_GREP) -q '^[<>] [^\#]'); then \
		echo "Creating/updating $(1)"; \
		mv -f $(2) $(1); \
	else \
		rm -f $(2); \
	fi

po_diff_and_mv_or_rm_func = \
	function po_diff_and_mv_or_rm () { \
		$(call po_diff_and_mv_or_rm,$$1,$$2) \
	}

po-update-pot: $(PO_POTFILE)
$(PO_POTFILE): $(PO_SOURCES)
	$(PO_XGETTEXT) --keyword=_ --keyword=N_ $(PO_SOURCES)
	@$(call po_diff_and_mv_or_rm,$(PO_POTFILE),$(PKGNAME).po)

po-update: po-update-po
po-update-po: Makefile $(filter po_rules.mk polkit_rules.mk,$(wildcard *.mk)) $(PO_POTFILE) po-refresh-po

po-refresh: po-refresh-po
po-refresh-po: Makefile
	@$(po_diff_and_mv_or_rm_func); \
	for cat in $(PO_POFILES); do \
		lang=`basename $$cat .po`; \
		if $(PO_MSGMERGE) po/$$lang.po $(PO_POTFILE) > po/$$lang.pot ; then \
			echo "$(PO_MSGMERGE) of $$lang succeeded" ; \
			po_diff_and_mv_or_rm po/$$lang.po po/$$lang.pot; \
		else \
			echo "$(PO_MSGMERGE) of $$lang failed" ; \
			rm -f po/$$lang.pot ; \
		fi; \
	done

po-clean:
	@rm -fv po/*.mo po/*~
	@rm -fv $(PO_GLADEH_FILES)

po-install: $(PO_MOFILES)
	@for n in $(PO_MOFILES); do \
	    l=`basename $$n .mo`; \
	    $(PO_INSTALL_DIR) $(PO_INSTALL_NLS_DIR)/$$l/LC_MESSAGES; \
	    $(PO_INSTALL_DATA) --verbose $$n $(PO_INSTALL_NLS_DIR)/$$l/LC_MESSAGES/$(PKGNAME).mo; \
	done

%.mo: %.po
	$(PO_MSGFMT) -o $@ $<

%.glade.h: %.glade
	$(PO_INTLTOOLEXTRACT) -t gettext/glade $<

endif
