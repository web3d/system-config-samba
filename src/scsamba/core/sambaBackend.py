## sambaBackend.py - contains the backend code for system-config-samba
## -*- coding: utf-8 -*-
## Copyright © 2002 - 2009 Red Hat, Inc.
## Copyright © 2002, 2003 Brent Fox <bfox@redhat.com>

## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See then
## GNU General Public License for more details.

## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

## Authors:
## Brent Fox <bfox@redhat.com>
## Nils Philippsen <nils@redhat.com>

import os
import errno
from slip.util.files import copyfile

from sambaParser import SambaParser

import gettext
_ = lambda x: unicode(gettext.ldgettext("system-config-samba", x), "utf-8")

class SambaBackend (object):
    smb_conf_path = "/etc/samba/smb.conf"
    smb_conf_template_path = "/usr/share/system-config-samba/smb.conf.template"
    pdbedit_cmd = '/usr/bin/pdbedit'

    def __init__ (self):
        self.parser = SambaParser ()

    def nmbIsService (self):
        # Check if nmb is its own service
        s = os.system ('/sbin/chkconfig --list nmb >& /dev/null')
        if s == 0:
            return True
        else:
            return False

    def isSambaRunning (self):
        services = [ ('smb', 'smbd') ]

        if self.nmbIsService ():
            services.append ( ('nmb', 'nmbd') )

        for service, procname in services:
            fd = os.popen ('LC_MESSAGES=C /sbin/service %s status' % service)
            lines = fd.readlines ()
            fd.close ()

            for line in lines:
                if line.find (procname) >= 0:
                    if not line.find ('running') > 0:
                        return False

        return True

    def startSamba(self):
        services = ['smb']

        if self.nmbIsService ():
            services.append ('nmb')

        for service in services:
            os.system ('/sbin/service %s start > /dev/null' % service)

    def restartSamba(self):
        services = ['smb']

        if self.nmbIsService ():
            services.append ('nmb')

        for service in services:
            os.system ('/sbin/service %s restart > /dev/null' % service)

    def readSmbConf (self):
        try:
            file = open (self.smb_conf_path, "rb")
        except IOError:
            copyfile (self.smb_conf_template_path, self.smb_conf_path)
            file = open (self.smb_conf_path, "rb")
        filecontents = file.read ()
        file.close ()

        # make eventual changes take effect
        self.parser.parse (filecontents)
        self.readSmbPasswords ()
        self.readSmbUsersFile ()

        return filecontents

    def writeSmbConf (self, contents):
        try:
            oldmode = os.stat (self.smb_conf_path)[0] & 07777
        except OSError:
            oldmode = 0644

        try:
            os.unlink (self.smb_conf_path + ".new")
        except OSError, e:
            if e.errno != errno.ENOENT:
                raise e
        file = open (self.smb_conf_path + ".new", 'wb', oldmode)
        file.write (contents)
        file.close ()
        os.rename (self.smb_conf_path + ".new", self.smb_conf_path)

        # make eventual changes take effect
        self.parser.parse (contents)
        self.readSmbPasswords ()
        self.readSmbUsersFile ()

    def readSmbPasswords (self):
        # Try to read the Samba passwords
        list = []

        fd = os.popen ('%s -L -w 2>&1' % (self.pdbedit_cmd), 'r')

        for line in fd.readlines ():
            if line.strip ()[0] != "#":
                list.append(line)
        status = fd.close()

        if not status or os.WEXITSTATUS (status) == 0:
            self.samba_passwd_file = list
        else:
            if os.getuid () != 0:
                raise RuntimeError, (_("You do not have permission to execute %s." % self.pdbedit_cmd))
            else:
                raise RuntimeError, (_("Error while reading Samba password list:\n%s") % "\n".join (map (str.strip, list)))

    @property
    def smbusers_file_path (self):
        globalsection = self.parser.getSection ("global")
        if not globalsection.keyExists ("username map"):
            globalsection.setKey ("username map", "/etc/samba/smbusers")
        return globalsection.getKey ("username map")

    def readSmbUsersFile(self):
        path = self.smbusers_file_path

        if os.access(path, os.F_OK) == 1:
            #The file exists.  Now check to see if we can read it or not

            if os.access(path, os.R_OK) == 1:
                fd = open(path, 'r')
                lines = fd.readlines()
                fd.close()
                self.samba_users_file = lines
            else:
                raise RuntimeError, (_("Cannot read %s.  Program will now exit." % path))

    def getPasswdFile(self):
        return self.samba_passwd_file

    def getUsersFile(self):
        return self.samba_users_file

    def getUserDict(self):
        user_dict = {}
        for line in self.samba_users_file:
            tmp_line = line.strip ()
            if tmp_line and tmp_line[0] != '#':
                tokens = tmp_line.split ('=')
                user_dict[tokens[0].strip ()] = line
        return user_dict

    def writeSmbUsersFile(self):
        path = self.smbusers_file_path
        pathnew = path + ".new"
        if (os.access (path, os.W_OK) or not os.access (path, os.F_OK)) and \
                (os.access (pathnew, os.W_OK) or not os.access (pathnew, os.F_OK)):
            try:
                oldmode = os.stat (path)[0] & 07777
            except OSError:
                oldmode = 0644

            try:
                os.unlink (path + ".new")
            except OSError, e:
                if e.errno != errno.ENOENT:
                    raise e
            fd = open(pathnew, 'w', oldmode)
        else:
            raise
        for line in self.samba_users_file:
            fd.write (line)

        fd.close()

        os.rename (pathnew, path)

    def addUser(self, unix_name, windows_name, password):
        self.readSmbPasswords ()
        self.readSmbUsersFile ()
        if windows_name and len (windows_name) > 0 and unix_name != windows_name:
            line = unix_name + " = " + windows_name + '\n'
            self.samba_users_file.append(line)
            self.writeSmbUsersFile()

        pipe = os.popen ('/usr/bin/smbpasswd -a -s "%s"' % (unix_name), "w")
        for i in (1, 2):
            pipe.write ("%s\n" % (password))
        pipe.close ()

        self.readSmbPasswords()
        self.readSmbUsersFile()

    def changePassword(self, unix_name, password):
        pipe = os.popen('/usr/bin/smbpasswd -s "%s"' % (unix_name), "w")
        for i in (1, 2):
            pipe.write ("%s\n" % (password))
        pipe.close ()

    def changeWindowsUserName(self, unix_name, windows_name):
        userDict = self.getUserDict()

        found = 0
        for line in self.samba_users_file:
            try:
                if line == userDict[unix_name]:
                    if windows_name and len (windows_name) > 0 and unix_name != windows_name:
                        new_line = unix_name + " = " + windows_name + '\n'
                        self.samba_users_file[self.samba_users_file.index(line)] = new_line
                    else:
                        del self.samba_users_file[self.samba_users_file.index(line)]
                    found = 1
            except:
                pass

        if not found:
            #There's no current entry in smbusers
            line = unix_name + " = " + windows_name + '\n'
            if windows_name and len (windows_name) > 0 and unix_name != windows_name:
                self.samba_users_file.append(line)
                self.writeSmbUsersFile()
                self.readSmbPasswords()
                self.readSmbUsersFile()

        self.writeSmbUsersFile()
        self.readSmbUsersFile()

    def deleteUser (self, name):
        # Remove the user from the smbpasswd file/tdb/ldap
        os.system ('%s -x -u "%s" >/dev/null' % (self.pdbedit_cmd, name))

        # Get a dict of the smbusers file
        user_dict = self.getUserDict ()
        user_keys = user_dict.keys ()

        # If this user had an entry in smbusers, remove that line
        if name in user_keys:
            self.samba_users_file.remove (user_dict[name])

        self.writeSmbUsersFile ()
        self.readSmbUsersFile ()
        self.readSmbPasswords ()

    def userExists (self, user):
        # Check to see if the user is already in the smbusers file
        self.readSmbUsersFile ()
        for line in self.samba_users_file:
            tokens = line.split ()
            if tokens and user == tokens[0]:
                return True

        # Check to see if the user is already in the smbpasswd file/tdb/ldap
        self.readSmbPasswords ()
        for line in self.samba_users_file:
            tokens = line.split ()
            if tokens and user == tokens[0]:
                return True

        return False
