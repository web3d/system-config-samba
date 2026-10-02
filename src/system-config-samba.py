#!/usr/bin/python
# -*- coding: utf-8 -*-
# 
# system-config-samba.py - Contains the startup script for system-config-samba
# Copyright © 2002 - 2004, 2008, 2009 Red Hat, Inc.
# Copyright © 2002, 2003 Brent Fox <bfox@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# Authors:
# Brent Fox <bfox@redhat.com>
# Nils Philippsen <nils@redhat.com>

import os
import sys
import signal

signal.signal (signal.SIGINT, signal.SIG_DFL)

import gettext
_ = lambda x: unicode(gettext.ldgettext("system-config-samba", x), "utf-8")

debug_flag = "--debug" in sys.argv
if "--no-dbus" in sys.argv:
    use_dbus = False
elif "--dbus" in sys.argv:
    use_dbus = True
else:
    use_dbus = None

try:
    import gtk
except:
    print >>sys.stderr, _("system-config-samba requires an X-Window display.")
    sys.exit(0)

os.umask (0022)

import mainWindow
from scsamba.exc import AuthError
main_window = None
try:
    main_window = mainWindow.MainWindow (debug_flag = debug_flag, use_dbus = use_dbus)
    if "main" in dir(gtk):
        gtk.main()
    else:
        gtk.mainloop()
except AuthError, e:
    parent_window = getattr(main_window, "main_window", None)
    dlg = gtk.MessageDialog(parent_window, gtk.MESSAGE_ERROR,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.BUTTONS_CLOSE, _("Authorization Error"))
    dlg.format_secondary_text(
            _("The authorization needed for '%(action_id)s' could not "
              "be obtained. The application will exit now.") % \
                      {'action_id': e.action_id})
    dlg.run()
    sys.exit(1)
