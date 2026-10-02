# License: GPL v2 or later
# Copyright Red Hat Inc. 2010

ifndef ICONS_THEMES
ICONS_THEMES = hicolor
endif

ICONSDIR = $(DATADIR)/icons

icons-install:
	topdir="$$PWD"; \
	for theme in $(ICONS_THEMES); do \
		pushd "$${topdir}/icons/$${theme}"; \
		for res in *x*; do \
			pushd "$$res"; \
			for cat in *; do \
				pushd "$$cat"; \
				targetdir="$(DESTDIR)/$(ICONSDIR)/$${theme}/$${res}/$${cat}"; \
				mkdir -p "$$targetdir" ; \
				for image in *.png; do \
					install -m 0644 "$$image" "$${targetdir}/$${image}"; \
				done; \
				popd; \
			done; \
			popd; \
		done; \
		popd; \
	done
