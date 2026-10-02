#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# sambaoptionscheck.py -
#       check whether samba options are consistent with man page
# Copyright © 2004 Red Hat, Inc.
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
# Nils Philippsen <nils@redhat.com>

"""Usage: man smb.conf | ./sambaoptionscheck.py"""

import sambaDefaults
import re
import sys

if __name__ == "__main__":
    global_re = re.compile ('^\s*(?P<option>.*\S)\s+\(G\)\s+$')
    section_re = re.compile ('^\s*(?P<option>.*\S)\s+\(S\)\s+$')

    lines = sys.stdin.readlines ()
    global_options = {}
    section_options = {}

    for line in lines:
        line = line.rstrip ()
        m = global_re.match (line)
        if m:
            option = m.group("option")
            global_options[option] = option
        else:
            m = section_re.match (line)
            if m:
                option = m.group("option")
                section_options[option] = option

    keys = sambaDefaults.global_keys.keys ()
    keys.sort ()
    for o in keys:
        if not global_options.has_key (o):
            print "unknown global option", o

    keys = sambaDefaults.section_keys.keys ()
    keys.sort ()
    for o in keys:
        if not section_options.has_key (o):
            print "unknown section option", o

    keys = global_options.keys ()
    keys.sort ()
    for o in keys:
        if sambaDefaults.section_keys.has_key (o):
            print "should be global option:", o
        elif not sambaDefaults.global_keys.has_key (o):
            print "missing global option", o

    keys = section_options.keys ()
    keys.sort ()
    for o in keys:
        if sambaDefaults.global_keys.has_key (o):
            print "should be section option:", o
        if not sambaDefaults.section_keys.has_key (o):
            print "missing section option", o
