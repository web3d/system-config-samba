# -*- coding: utf-8 -*-
# scsamba.dbus.service.sambaBackend: DBUS wrapper for system-config-samba
# backend
# Copyright © 2008, 2009 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See then
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# Authors:
# Nils Philippsen <nils@redhat.com>

import dbus.service
import slip.dbus.service

import scsamba.core.sambaBackend
from scsamba.dbus import dbus_service_name

class SambaBackend (slip.dbus.service.Object):
    default_polkit_auth_required = "org.fedoraproject.config.samba.configure"

    def __init__ (self, bus_name, object_path):
        slip.dbus.service.Object.__init__ (self, bus_name, object_path)

        self.backend = scsamba.core.sambaBackend.SambaBackend ()

    @dbus.service.method (dbus_interface = dbus_service_name + ".Backend", out_signature = "b")
    def isSambaRunning (self):
        return self.backend.isSambaRunning ()

    @dbus.service.method (dbus_interface = dbus_service_name + ".Backend")
    def startSamba (self):
        return self.backend.startSamba ()

    @dbus.service.method (dbus_interface = dbus_service_name + ".Backend")
    def restartSamba (self):
        return self.backend.restartSamba ()

    @dbus.service.method (dbus_interface = dbus_service_name + ".Backend", out_signature = "s")
    def readSmbConf (self):
        return self.backend.readSmbConf ()

    @dbus.service.method (dbus_interface = dbus_service_name + ".Backend", in_signature = "ay", byte_arrays = True)
    def writeSmbConf (self, contents):
        return self.backend.writeSmbConf (contents)

    @dbus.service.method (dbus_interface = dbus_service_name + ".Backend", out_signature = "as")
    def getPasswdFile (self):
        return self.backend.getPasswdFile ()

    @dbus.service.method (dbus_interface = dbus_service_name + ".Backend", out_signature = "s")
    def getUsersFile (self):
        return self.backend.getUsersFile ()

    @dbus.service.method (dbus_interface = dbus_service_name + ".Backend", out_signature = "a{ss}")
    def getUserDict (self):
        return self.backend.getUserDict ()

    @dbus.service.method (dbus_interface = dbus_service_name + ".Backend")
    def writeSmbUsersFile (self):
        return self.backend.writeSmbUsersFile ()

    @dbus.service.method (dbus_interface = dbus_service_name + ".Backend", in_signature = "sss")
    def addUser (self, unix_name, windows_name, password):
        return self.backend.addUser (unix_name, windows_name, password)

    @dbus.service.method (dbus_interface = dbus_service_name + ".Backend", in_signature = "ss")
    def changePassword (self, unix_name, password):
        return self.backend.changePassword (unix_name, password)

    @dbus.service.method (dbus_interface = dbus_service_name + ".Backend", in_signature = "ss")
    def changeWindowsUserName (self, unix_name, windows_name):
        return self.backend.changeWindowsUserName (unix_name, windows_name)

    @dbus.service.method (dbus_interface = dbus_service_name + ".Backend", in_signature = "s")
    def deleteUser (self, name):
        return self.backend.deleteUser (name)

    @dbus.service.method (dbus_interface = dbus_service_name + ".Backend", in_signature = "s", out_signature = "b")
    def userExists (self, user):
        return self.backend.userExists (user)
