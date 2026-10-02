# -*- coding: utf-8 -*-
# scsamba.dbus.proxy.sambaBackend: DBUS proxy for system-config-samba
# backend
# Copyright © 2008 - 2010 Red Hat, Inc.
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

import dbus
from slip.dbus import polkit
from scsamba.dbus import dbus_service_name, dbus_service_path
from scsamba.exc import AuthError

class SambaBackend (object):
    def __init__ (self, bus):
        self.bus = bus
        self.dbus_service_path = "/".join ((dbus_service_path, "Backend"))
        self.dbus_object = bus.get_object (dbus_service_name, self.dbus_service_path)
        self.dbus_interface = dbus.Interface (self.dbus_object, "org.fedoraproject.Config.Samba.Backend")

    @polkit.enable_proxy(authfail_exception=AuthError)
    def isSambaRunning (self):
        return self.dbus_interface.isSambaRunning ()

    @polkit.enable_proxy(authfail_exception=AuthError)
    def startSamba (self):
        return self.dbus_interface.startSamba ()

    @polkit.enable_proxy(authfail_exception=AuthError)
    def restartSamba (self):
        return self.dbus_interface.restartSamba ()

    @polkit.enable_proxy(authfail_exception=AuthError)
    def readSmbConf (self):
        return self.dbus_interface.readSmbConf ()

    @polkit.enable_proxy(authfail_exception=AuthError)
    def writeSmbConf (self, contents):
        return self.dbus_interface.writeSmbConf (contents)

    @polkit.enable_proxy(authfail_exception=AuthError)
    def getPasswdFile (self):
        return self.dbus_interface.getPasswdFile ()

    @polkit.enable_proxy(authfail_exception=AuthError)
    def getUsersFile (self):
        return self.dbus_interface.getUsersFile ()

    @polkit.enable_proxy
    def getUserDict (self):
        return self.dbus_interface.getUserDict ()

    @polkit.enable_proxy
    def writeSmbUsersFile (self):
        return self.dbus_interface.writeSmbUsersFile ()

    @polkit.enable_proxy
    def addUser (self, unix_name, windows_name, password):
        return self.dbus_interface.addUser (unix_name, windows_name, password)

    @polkit.enable_proxy
    def changePassword (self, unix_name, password):
        return self.dbus_interface.changePassword (unix_name, password)

    @polkit.enable_proxy
    def changeWindowsUserName (self, unix_name, windows_name):
        return self.dbus_interface.changeWindowsUserName (unix_name, windows_name)

    @polkit.enable_proxy
    def deleteUser (self, name):
        return self.dbus_interface.deleteUser (name)

    @polkit.enable_proxy
    def userExists (self, user):
        return self.dbus_interface.userExists (user)
