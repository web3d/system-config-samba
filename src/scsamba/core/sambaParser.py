# sambaParser.py - the smb.conf file parser for system-config-samba
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

import sambaToken
from sambaToken import _remove_ws, _map_remove_ws, SambaToken, \
        sambaTokenCanonicalNameValue, UnknownKeyError
import sambaDefaults

class SambaSection(object):
    def __init__ (self, parser, name = None, literal = None, prototype = False):
        assert parser != None
        self.parser = parser
        self.name = None
        self.content = []
        if not prototype and not self.set_name (name, literal):
            raise Exception ("section %s already defined" % (name))

    def __str__ (self):
        str = ""
        if self.literal:
            str += "%s\n" % self.literal
        elif self.name:
            str += "[%s]\n" % (self.name)
        for token in self.content:
            tokendata = token.getData ()
            if tokendata:
                # no default value
                if tokendata.strip () == "None":
                    raise Exception ("refusing to write illegal token %s which would yield %s" % (token, tokendata))
                else:
                    str += tokendata
        return str

    def __repr__ (self):
        contentstrings = []
        for token in self.content:
            contentstrings.append (repr (token))
        if self.name:
            name = self.name
        else:
            name = "preamble"
        return "<%s instance %s:\n%s\n>" % (self.__class__.__name__, name, "\n".join (contentstrings))

    def delete (self):
        name = _remove_ws (self.name).lower ()
        if name and self.parser.sections_dict.has_key (name):
            del self.parser.sections_dict[name]
        if name in self.parser.sections:
            self.parser.sections.remove (name)
        del (self)

    def set_name (self, newname, newliteral=None):
        if newname is not None:
            assert(newname[:1] not in (' ', '\t', '[', ']'))
            assert(newname[-1:] not in (' ', '\t', '[', ']'))

        if isinstance (newname, basestring):
            _newname = _remove_ws (newname).lower ()
        else:
            _newname = newname
        if not _newname in _map_remove_ws (self.parser.sections):
            if self.name:
                self.parser.sections[self.parser.sections.index (_remove_ws (self.name).lower ())] = _newname
                del self.parser.sections_dict[_remove_ws (self.name).lower ()]
            else:
                self.parser.sections.append (_newname)
            self.name = newname
            self.literal = newliteral
            self.parser.sections_dict[_newname] = self
            return True
        return False

    def fetchKey (self, name):
        canonicalName = sambaToken.sambaTokenCanonicalNameValue (name, "")[0]
        for token in self.content:
            if token.type == sambaToken.SambaToken.SAMBA_TOKEN_KEYVAL:
                try:
                    if (token.canonicalNameValue ()[0].lower () ==
                            canonicalName.lower ()):
                        return token
                except UnknownKeyError:
                    # don't trip over unknown smb.conf keys here
                    pass

    def keyExists (self, name):
        if self.fetchKey (name):
            return True
        else:
            return False

    def getKey (self, name):
        # returns canonical names and values
        token = self.fetchKey (name)
        if token:
            (keyname, keyval, _inverted) = token.canonicalNameValue ()
            (foo, bar, inverted) = sambaTokenCanonicalNameValue (name, None)
            if inverted:
                # revert to non inverted value
                if keyval.lower () == "no":
                    keyval = "yes"
                elif keyval.lower () == "yes":
                    keyval = "no"
            return keyval
        else:
            # no explicit token found, assume default
            return sambaDefaults.get_default (name)

    def setKey (self, name, value, comment = None):
        token = self.fetchKey (name)
        if token:
            (name, _value, new_inverted) = sambaToken.sambaTokenCanonicalNameValue (name, value)
            (foo, bar, old_inverted) = sambaToken.sambaTokenCanonicalNameValue (token.keyname, None)
            if new_inverted != old_inverted:
                value = sambaToken.sambaTokenInvertValue (value)
            self.content[self.content.index (token)] = sambaToken.SambaToken (sambaToken.SambaToken.SAMBA_TOKEN_KEYVAL, (token.keyname, value), token.comment)
        else:
            (name, _value, inverted) = sambaToken.sambaTokenCanonicalNameValue (name, value)
            token = sambaToken.SambaToken (sambaToken.SambaToken.SAMBA_TOKEN_KEYVAL, (name, _value), comment)
            # insert before eventual blank lines or comments (which may as well
            # be for the next section)
            index = len (self.content) - 1
            while index >= 0 and (self.content[index].type == sambaToken.SambaToken.SAMBA_TOKEN_STRING or self.content[index].type == sambaToken.SambaToken.SAMBA_TOKEN_BLANKLINE):
                index -= 1
            self.content.insert (index + 1, token)

    def delKey (self, name):
        token = self.fetchKey (name)
        if token:
            self.content.remove (token)
            del token

class SambaParser (object):
    def __init__(self):
        self.warnings = []
        self.sections_reset ()

    def sections_reset (self):
        self.sections = []
        for section in getattr (self, "sections_dict", {}).itervalues ():
            del section
        self.sections_dict = {}

    def createToken(self, line, section):
        # eat trailing newline
        if len (line) > 0 and line[-1] == '\n':
            line = line[:-1]

        stripped_line = line.strip ()
        if stripped_line != "":
            tmp = tuple(stripped_line)
        else:
            token = sambaToken.SambaToken(sambaToken.SambaToken.SAMBA_TOKEN_BLANKLINE, (line))
            return token

        if tmp:
            if tmp[0] == "#" or tmp[0] == ";":
                try:
                    commented_section = stripped_line[1:].strip ()
                    if commented_section[0] == '[' and commented_section[-1] == ']':
                        # we found a commented out section, treat commented out
                        # key value pairs as comments from now on until next
                        # section, e.g. for example sections
                        self.honour_default_value_comments = False
                except IndexError:
                    pass

            if tmp[0] == "#":
                #The line begins with a "#"
                token = sambaToken.SambaToken(sambaToken.SambaToken.SAMBA_TOKEN_STRING, (line))
                return token

            elif tmp[0] == ";":
                # possibly a commented out default key value
                name = None
                try:
                    name, value = line.split ("=", 1)
                    name = name[1:].strip ()
                    value = value.strip ()
                except ValueError:
                    pass

                if name and self.honour_default_value_comments:
                    if not self.isDuplicateKey(name, section):
                        default_value = sambaDefaults.get_default (name)
                        try:
                            if value.lower () == default_value.lower ():
                                token = sambaToken.SambaToken(sambaToken.SambaToken.SAMBA_TOKEN_KEYVAL, (name, default_value))
                                return token
                        except (AttributeError, sambaToken.UnknownKeyError):
                            pass
                    else:
                        return None

                # possibly just a comment
                token = sambaToken.SambaToken(sambaToken.SambaToken.SAMBA_TOKEN_STRING, (line))
                return token

            elif tmp[0] == "[" and tmp[-1] == "]":
                #The line contains a section header
                token = sambaToken.SambaToken(sambaToken.SambaToken.SAMBA_TOKEN_SECTION_HEADER, (line), None)
                # honour commented out key value pairs from now on
                self.honour_default_value_comments = True
                return token

            else:
                #The line isn't a section header and is probably a key/value line
                comment_token = None

                #See if there are any comments at the end of the line
                if "#" in line:
                    data, comment = line.split ("#", 1)
                    comment_token = comment
                    line = data
                else:
                    #There are no comments in the line
                    data = line

                name, value = line.split ("=", 1)
                name = name.strip ()
                value = value.strip ()

                if comment_token:
                    token = sambaToken.SambaToken(sambaToken.SambaToken.SAMBA_TOKEN_KEYVAL, (name, value), comment_token)
                    return token
                else:
                    if not self.isDuplicateKey(name, section):
                        try:
                            token = sambaToken.SambaToken(sambaToken.SambaToken.SAMBA_TOKEN_KEYVAL, (name, value))
                            return token
                        except sambaToken.UnknownKeyError:
                            token = sambaToken.SambaToken(sambaToken.SambaToken.SAMBA_TOKEN_KEYVAL, (name, value), accept_unknown = True)
                            return token
                    else:
                        #We've found a duplicate key, so return none.  This keeps duplicates from being
                        #added to the list
                        return None

    def parse (self, smbconf_text):
        self.sections_reset ()
        self.warnings = []

        lines = smbconf_text.split ("\n")

        if lines:
            section = SambaSection (self, None)

            lineno = 0
            for line in lines:
                lineno += 1
                token = self.createToken (line, section)
                if token:
                    if token.type == SambaToken.SAMBA_TOKEN_SECTION_HEADER:
                        section_name = token.value.strip()
                        assert(section_name.startswith("["))
                        assert(section_name.endswith("]"))
                        section_name = _remove_ws(section_name[1:-1]).lower()
                        assert(len(section_name) > 0)
                        section = SambaSection (self, section_name, token.value)
                    else:
                        #If the token is valid, then add it
                        section.content.append (token)
                        if token.unknown:
                            self.warnings.append ([lineno, token])

    def printSections (self):
        for name in self.getSections ():
            print str (self.getSection (name))

    def getSections (self):
        return self.sections

    def getSection (self, name):
        if name is not None:
            name = _remove_ws(name.lower())
        return self.sections_dict[name]

    def getShareHeaders(self):
        header_list = self.getHeaders ()
        share_header_list = []
        for header in header_list:
            if header not in ("global", "printers", "homes"):
                share_header_list.append (header)
        return share_header_list

    def getHeaders(self):
        header_list = []
        for name in self.sections:
            if name:
                header_list.append (name)
        return header_list

    def isDuplicateKey (self, name, section):
        try:
            return section.keyExists (name)
        except sambaToken.UnknownKeyError:
            return False
