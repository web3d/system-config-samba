# -*- coding: utf-8 -*-
# Copyright © 2002 - 2009 Red Hat, Inc.
# Copyright © 2002, 2003 Brent Fox <bfox@redhat.com>
#
# GPL-2.0-or-later. Python 2 -> Python 3 rewrite of sambaToken.py.
#
# Token data structure representing one line of smb.conf: a comment/string,
# a section header, a key/value pair, or a blank line. Preserving the token
# granularity is what lets the editor rewrite the file while keeping comments
# and blank lines in place.

from __future__ import annotations

from .sambaDefaults import (
    synonym_dict, inverted_synonym_dict, all_keys_expander_dict,
    section_keys, global_keys, nomask_default_list, get_default,
)


def _remove_ws(s):
    if isinstance(s, str):
        return s.replace(" ", "").replace("\t", "")
    return s


def _map_remove_ws(l):
    return [_remove_ws(item) for item in l]


def sambaTokenInvertValue(value):
    if not isinstance(value, str):
        return value
    if value.lower() == "no":
        return "yes"
    if value.lower() == "yes":
        return "no"
    return value


class UnknownKeyError(Exception):
    pass


def sambaTokenCanonicalNameValue(keyname, keyval):
    inverted = False
    # whitespace is irrelevant
    _keyname = _remove_ws(keyname).lower()

    # Samba key names have synonyms; normalise to the canonical name so we do
    # not emit conflicting tags.
    for key in synonym_dict:
        if _keyname in _map_remove_ws(synonym_dict[key]):
            _keyname = _remove_ws(key).lower()
            break

    # ...and there is the inverted-synonym concept (writeable <-> read only).
    for key in inverted_synonym_dict:
        if _keyname == _remove_ws(key).lower():
            _keyname = _remove_ws(inverted_synonym_dict[key])
            keyval = sambaTokenInvertValue(keyval)
            inverted = True
            break

    try:
        keyname = all_keys_expander_dict[_keyname]
    except KeyError:
        raise UnknownKeyError(keyname)

    return (keyname, keyval, inverted)


class SambaToken(object):
    SAMBA_TOKEN_STRING = 1
    SAMBA_TOKEN_SECTION_HEADER = 2
    SAMBA_TOKEN_KEYVAL = 3
    SAMBA_TOKEN_BLANKLINE = 4

    def __init__(self, type, value, comment=None, accept_unknown=False):
        self.unknown = False
        if type == SambaToken.SAMBA_TOKEN_KEYVAL:
            _value_0 = _remove_ws(value[0]).lower()
            if (_value_0 not in _map_remove_ws(list(section_keys))
                    and _value_0 not in _map_remove_ws(list(global_keys))):
                if not accept_unknown:
                    raise UnknownKeyError(value[0])
                self.unknown = True

            self.keyname = value[0]
            self.keyval = value[1]

            if _remove_ws(self.keyname) in _map_remove_ws(nomask_default_list):
                self.mask_default = False
            else:
                self.mask_default = True

        self.type = type
        self.value = value
        self.comment = comment

    def canonicalNameValue(self):
        return sambaTokenCanonicalNameValue(self.keyname, self.keyval)

    def getData(self):
        if self.type == SambaToken.SAMBA_TOKEN_STRING:
            return "%s\n" % self.value
        if self.type == SambaToken.SAMBA_TOKEN_SECTION_HEADER:
            return "%s\n" % self.value
        if self.type == SambaToken.SAMBA_TOKEN_KEYVAL:
            default_mask = False
            default = get_default(self.keyname)

            if default:
                default = str(default).lower()
            if default is None and self.keyval is None:
                return None
            elif default == str(self.keyval).lower():
                default_mask = True

            if default_mask and self.mask_default:
                default_mask_char = ";"
            else:
                default_mask_char = ""

            if self.comment:
                return "%s\t%s = %s \t#%s\n" % (
                    default_mask_char, self.keyname, self.keyval, self.comment)
            return "%s\t%s = %s\n" % (
                default_mask_char, self.keyname, self.keyval)

        if self.type == SambaToken.SAMBA_TOKEN_BLANKLINE:
            return "\n"
        return None

    def __repr__(self):
        d = self.getData()
        d = d.strip() if d else ""
        return "<%s instance %d: '%s'>" % (self.__class__.__name__, self.type, d)
