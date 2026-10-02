# sambaToken.py - data structure for system-config-samba
# -*- coding: utf-8 -*-
# Copyright © 2002 - 2009 Red Hat, Inc.
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

from sambaDefaults import synonym_dict, inverted_synonym_dict, \
        all_keys_expander_dict, section_keys, global_keys, \
        nomask_default_list, get_default

def _remove_ws (s):
    if isinstance (s, (str, unicode)):
        return s.replace (" ", "").replace ("\t", "")
    else:
        return s

def _map_remove_ws (l):
    return map (_remove_ws, l)

def sambaTokenInvertValue (value):
    if not isinstance (value, basestring):
        return value
    if value.lower () == "no":
        return "yes"
    elif value.lower () == "yes":
        return "no"
    return value

class UnknownKeyError (Exception):
    pass

def sambaTokenCanonicalNameValue (keyname, keyval):
    inverted = False
    # whitespace is irrelevant
    _keyname = _remove_ws (keyname).lower ()
    # We need a sane way of handling samba keyname synonyms.
    # Otherwise we could have conflicting tags.
    for key in synonym_dict.keys ():
        if _keyname in _map_remove_ws (synonym_dict [key]):
            # We've found a synonym, so convert it to the real keyname
            _keyname = _remove_ws (key).lower ()
            break

    # Now we need to check for the insane concept of inverted keynames.
    for key in inverted_synonym_dict.keys ():
        if _keyname == _remove_ws (key).lower ():
            # We've found a synonym, so convert it to the real keyname
            _keyname = _remove_ws (inverted_synonym_dict[key])

            # Now we need to invert the value.
            # AFAIK, the inverted case is only for yes/no values.
            keyval = sambaTokenInvertValue (keyval)
            inverted = True
            break

    try:
        keyname = all_keys_expander_dict[_keyname]
    except KeyError:
        raise UnknownKeyError (keyname)

    return (keyname, keyval, inverted)

class SambaToken(object):
    SAMBA_TOKEN_STRING = 1
    SAMBA_TOKEN_SECTION_HEADER = 2
    SAMBA_TOKEN_KEYVAL = 3
    SAMBA_TOKEN_BLANKLINE = 4

    def __init__ (self, type, value, comment = None, accept_unknown = False):

        self.unknown = False
        if type == SambaToken.SAMBA_TOKEN_KEYVAL:
            _value_0 = _remove_ws (value[0]).lower ()
            if _value_0 not in _map_remove_ws (section_keys.keys ()) and _value_0 not in _map_remove_ws (global_keys.keys ()):
                if not accept_unknown:
                    raise UnknownKeyError (value[0])
                self.unknown = True

            self.keyname = value[0]
            self.keyval = value[1]

            if _remove_ws (self.keyname) in _map_remove_ws (nomask_default_list):
                self.mask_default = False
            else:
                self.mask_default = True

        self.type = type
        self.value = value
        self.comment = comment

    def canonicalNameValue (self):
        return sambaTokenCanonicalNameValue (self.keyname, self.keyval)

    def getData(self):
        if self.type == SambaToken.SAMBA_TOKEN_STRING:
            return ("%s\n" % self.value)
        elif self.type == SambaToken.SAMBA_TOKEN_SECTION_HEADER:
            return ("%s\n" % self.value)
        elif self.type == SambaToken.SAMBA_TOKEN_KEYVAL:
            default_mask = False
            default = get_default (self.keyname)

            if default:
                default = str(default).lower()
            if default == None and self.keyval == None:
                return
            elif default == str(self.keyval).lower():
                default_mask = True

            if default_mask and self.mask_default:
                default_mask_char = ';'
            else:
                default_mask_char = '';

            if self.comment:
                return ("%s\t%s = %s \t#%s\n" % (default_mask_char, self.keyname, self.keyval, self.comment))
            else:
                return ("%s\t%s = %s\n" % (default_mask_char, self.keyname, self.keyval))

        elif self.type == SambaToken.SAMBA_TOKEN_BLANKLINE:
            return "\n"

    def __repr__(self):
        d = self.getData ()
        if d:
            d = d.strip()
        else:
            d = ''
        return "<%s instance %d: '%s'>" % (self.__class__.__name__, self.type, d)
