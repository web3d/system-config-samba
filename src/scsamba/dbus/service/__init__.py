#!/usr/bin/python
# -*- coding: utf-8 -*-
# scsamba.dbus.service: dbus backend service for system-config-samba
#
# Copyright © 2008, 2009 Red Hat, Inc.
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Authors:
# Nils Philippsen <nils@redhat.com>

import gobject
import dbus
import dbus.mainloop.glib

try:
    from slip.dbus.bus import SystemBus
except ImportError:
    SystemBus = dbus.SystemBus
import slip.dbus.service

from sambaBackend import SambaBackend

from scsamba.dbus import dbus_service_name, dbus_service_path

##############################################################################

def run_service ():
    mainloop = gobject.MainLoop ()
    dbus.mainloop.glib.DBusGMainLoop (set_as_default=True)

    system_bus = SystemBus ()

    name = dbus.service.BusName (dbus_service_name, system_bus)

    backend = SambaBackend (name, dbus_service_path + "/Backend")

    slip.dbus.service.set_mainloop (mainloop)
    print "Running system-config-samba dbus service at '%s'." % dbus_service_name
    mainloop.run ()

##############################################################################

if __name__ == "__main__":
    run_service ()
