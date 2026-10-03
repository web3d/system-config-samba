# -*- coding: utf-8 -*-
# Copyright © 2002 - 2009 Red Hat, Inc.
# Copyright © 2002, 2003 Brent Fox <bfox@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Python 2 -> Python 3 rewrite of sambaDefaults.py for system-config-samba.
#
# Default values for the smb.conf data structure. The defaults are discovered
# by asking `testparm -s -v` about the Samba build on this host, so behaviour
# tracks the installed Samba version (same strategy as the original).

from __future__ import annotations

import re
import subprocess

__all__ = [
    "global_keys", "section_keys", "all_keys_expander_dict", "synonym_dict",
    "inverted_synonym_dict", "nomask_default_list", "get_default",
    "section_keys_list",
]

nomask_default_list = [
    "security",
    "workgroup",
]

# Samba parameters that may appear in a share ([section]) rather than [global].
section_keys_list = [
    "-valid", "acl compatibility", "acl check permissions", "admin users",
    "afs share", "allow hosts", "available", "blocking locks", "block size",
    "browsable", "browseable", "case sensitive", "casesignames", "comment",
    "copy", "create mask", "create mode", "csc policy", "cups options",
    "default case", "default devmode", "delete readonly", "delete veto files",
    "deny hosts", "directory mask", "directory mode", "directory",
    "directory security mask", "dont descend", "dos filemode",
    "dos filetime resolution", "dos filetimes", "ea support", "exec",
    "fake directory create times", "fake oplocks", "follow symlinks",
    "force create mode", "force directory mode", "force directory security mode",
    "force group", "force security mode", "force unknown acl user", "force user",
    "fstype", "group", "guest ok", "guest only", "hide dot files", "hide files",
    "hide special files", "hide unreadable", "hide unwriteable files",
    "hosts allow", "hosts deny", "inherit acls", "inherit permissions",
    "invalid users", "level2 oplocks", "locking", "lppause command",
    "lpq command", "lpresume command", "lprm command", "magic output",
    "magic script", "mangle case", "mangled map", "mangled names",
    "mangling char", "map acl inherit", "map archive", "map hidden",
    "map system", "max connections", "max print jobs",
    "max reported print jobs", "min print space", "msdfs proxy", "msdfs root",
    "nt acl support", "only user", "only guest", "oplock contention limit",
    "oplocks", "path", "posix locking", "postexec", "postscript", "preexec",
    "preexec close", "preserve case", "print command", "printable",
    "printcap name", "printer admin", "printer driver",
    "printer driver location", "printer name", "printer", "printing",
    "print ok", "profile acls", "public", "queuepause command",
    "queueresume command", "read list", "read only", "root postexec",
    "root preexec", "root preexec close", "security mask", "set directory",
    "share modes", "short preserve case", "status", "store dos attributes",
    "strict allocate", "strict locking", "strict sync", "sync always",
    "use client driver", "username", "user", "users", "use sendfile",
    "valid users", "veto files", "veto oplock files", "vfs object",
    "vfs objects", "vfs options", "volume", "wide links", "writeable",
    "writable", "write cache size", "write list", "write ok",
]

synonym_dict = {
    "browseable": ["browsable"],
    "case sensitive": ["casesignames"],
    "create mask": ["create mode"],
    "debug timestamp": ["timestamp logs"],
    "default service": ["default"],
    "directory mask": ["directory mode"],
    "force group": ["group"],
    "guest ok": ["public"],
    "guest only": ["only guest"],
    "hosts allow": ["allow hosts"],
    "hosts deny": ["deny hosts"],
    "idmap gid": ["winbind gid"],
    "idmap uid": ["winbind uid"],
    "lock directory": ["lock dir"],
    "log level": ["debuglevel"],
    "max protocol": ["protocol"],
    "min password length": ["min passwd length"],
    "path": ["directory"],
    "preexec": ["exec"],
    "preferred master": ["prefered master"],
    "preload": ["auto services"],
    "printable": ["print ok"],
    "printcap name": ["printcap"],
    "printer name": ["printer"],
    "root directory": ["root", "root dir"],
    "username": ["user", "users"],
    "vfs objects": ["vfs object"],
    "writeable": ["writable"],
}

inverted_synonym_dict = {
    "writeable": "read only",
}

# Overrides, presets (e.g. keys not mentioned by testparm).
global_keys = {
    "client ntlmv2 auth": "no",
    "iprint server": None,
    "nis homedir": "no",
}
section_keys = {
    "-valid": "yes",
    "read only": "yes",
}

kv_re = re.compile(r"^\s*(?P<key>[^=]*[^=\s])\s*=\s*(?P<value>.*\S)?\s*$")


def _query_testparm_defaults() -> None:
    """Populate global_keys / section_keys from the host's testparm output."""
    try:
        proc = subprocess.run(
            ["/usr/bin/testparm", "-s", "-v", "/dev/null"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        # testparm unavailable: keep the hardcoded overrides above.
        return

    for line in proc.stdout.splitlines():
        m = kv_re.match(line)
        if not m:
            continue
        key = m.group("key").lower()
        value = m.group("value")
        if value:
            value = value.lower()
        if key in section_keys_list:
            section_keys.setdefault(key, value)
        else:
            global_keys.setdefault(key, value)


_query_testparm_defaults()


def _apply_inverted_synonyms() -> None:
    ivdict = {
        "yes": "No",
        "1": "0",
        "true": "False",
        "no": "Yes",
        "0": "1",
        "false": "True",
    }
    for isynkey, isynvalue in inverted_synonym_dict.items():
        if isynvalue in global_keys:
            table = global_keys
        elif isynvalue in section_keys:
            table = section_keys
        else:
            raise LookupError(
                "isynkey %s value %s not in global_keys or section_keys"
                % (isynkey, isynvalue)
            )

        value = (table[isynvalue] or "").lower()
        try:
            ivalue = ivdict[value]
        except KeyError:
            raise ValueError("no inversion possible for '%s'" % (value))

        table[isynkey] = ivalue


def _apply_synonyms() -> None:
    for synkey in synonym_dict:
        if synkey in global_keys:
            table = global_keys
        elif synkey in section_keys:
            table = section_keys
        else:
            # allow unknown synonyms to handle different samba versions
            continue
        for synonym in synonym_dict[synkey]:
            table[synonym] = table[synkey]


_apply_inverted_synonyms()
_apply_synonyms()


def get_default(keyname):
    if keyname in global_keys:
        return global_keys[keyname]
    if keyname in section_keys:
        return section_keys[keyname]
    return None


all_keys_expander_dict = {}
for _key in list(global_keys) + list(section_keys):
    all_keys_expander_dict[_key.replace(" ", "").replace("\t", "").lower()] = _key
