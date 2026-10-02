## sambaParser.py - the smb.conf file parser for system-config-samba
## -*- coding: utf-8 -*-
## Copyright © 2009 Red Hat, Inc.

## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.

## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

## Authors:
## Nils Philippsen <nils@redhat.com>

import sambaParser

class SambaConfig (sambaParser.SambaParser):
    def __init__(self, backend):
        super (SambaConfig, self).__init__ ()
        self.backend = backend
        self.parseFile ()

    def parseFile(self):
        return self.parse (self.backend.readSmbConf ())

    def writeFile(self):
        lines = ""
        for name in self.sections:
            lines += str (self.getSection (name))
        self.backend.writeSmbConf (lines)
