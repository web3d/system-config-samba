# -*- coding: utf-8 -*-
# Copyright © 2002 - 2009 Red Hat, Inc.
# Copyright © 2002, 2003 Brent Fox <bfox@redhat.com>
#
# GPL-2.0-or-later. Python 2 -> Python 3 rewrite of sambaParser.py.
#
# Loss-tolerant smb.conf parser: splits the file into sections of tokens so
# that unrelated lines (comments, blank lines, other shares) survive an
# edit-and-save round trip untouched.

from __future__ import annotations

from . import sambaDefaults
from . import sambaToken
from .sambaToken import (
    _remove_ws, _map_remove_ws, SambaToken,
    sambaTokenCanonicalNameValue, UnknownKeyError,
)


class SambaSection(object):
    def __init__(self, parser, name=None, literal=None, prototype=False):
        assert parser is not None
        self.parser = parser
        self.name = None
        self.literal = None
        self.content = []
        if not prototype and not self.set_name(name, literal):
            raise Exception("section %s already defined" % (name))

    def __str__(self):
        out = ""
        if self.literal:
            out += "%s\n" % self.literal
        elif self.name:
            out += "[%s]\n" % (self.name)
        for tok in self.content:
            tokendata = tok.getData()
            if tokendata:
                if tokendata.strip() == "None":
                    raise Exception(
                        "refusing to write illegal token %s which would yield %s"
                        % (tok, tokendata))
                out += tokendata
        return out

    def __repr__(self):
        contentstrings = [repr(tok) for tok in self.content]
        name = self.name if self.name else "preamble"
        return "<%s instance %s:\n%s\n>" % (
            self.__class__.__name__, name, "\n".join(contentstrings))

    def delete(self):
        name = _remove_ws(self.name).lower()
        if name and name in self.parser.sections_dict:
            del self.parser.sections_dict[name]
        if name in self.parser.sections:
            self.parser.sections.remove(name)

    def set_name(self, newname, newliteral=None):
        if newname is not None:
            assert newname[:1] not in (" ", "\t", "[", "]")
            assert newname[-1:] not in (" ", "\t", "[", "]")

        if isinstance(newname, str):
            _newname = _remove_ws(newname).lower()
        else:
            _newname = newname
        if _newname not in _map_remove_ws(self.parser.sections):
            if self.name:
                self.parser.sections[
                    self.parser.sections.index(_remove_ws(self.name).lower())
                ] = _newname
                del self.parser.sections_dict[_remove_ws(self.name).lower()]
            else:
                self.parser.sections.append(_newname)
            self.name = newname
            self.literal = newliteral
            self.parser.sections_dict[_newname] = self
            return True
        return False

    def fetchKey(self, name):
        canonicalName = sambaTokenCanonicalNameValue(name, "")[0]
        for tok in self.content:
            if tok.type == SambaToken.SAMBA_TOKEN_KEYVAL:
                try:
                    if tok.canonicalNameValue()[0].lower() == canonicalName.lower():
                        return tok
                except UnknownKeyError:
                    # don't trip over unknown smb.conf keys here
                    pass
        return None

    def keyExists(self, name):
        return bool(self.fetchKey(name))

    def getKey(self, name):
        # returns canonical value (may be None when the key is absent and has
        # no known default)
        tok = self.fetchKey(name)
        if tok:
            (keyname, keyval, _inverted) = tok.canonicalNameValue()
            (_foo, _bar, inverted) = sambaTokenCanonicalNameValue(name, None)
            if inverted:
                # revert to non-inverted value
                if keyval.lower() == "no":
                    keyval = "yes"
                elif keyval.lower() == "yes":
                    keyval = "no"
            return keyval
        # no explicit token found, assume default
        return sambaDefaults.get_default(name)

    def setKey(self, name, value, comment=None):
        tok = self.fetchKey(name)
        if tok:
            (name, _value, new_inverted) = sambaTokenCanonicalNameValue(name, value)
            (_foo, _bar, old_inverted) = sambaTokenCanonicalNameValue(tok.keyname, None)
            if new_inverted != old_inverted:
                value = sambaToken.sambaTokenInvertValue(value)
            self.content[self.content.index(tok)] = SambaToken(
                SambaToken.SAMBA_TOKEN_KEYVAL, (tok.keyname, value), tok.comment)
        else:
            (name, _value, _inverted) = sambaTokenCanonicalNameValue(name, value)
            tok = SambaToken(SambaToken.SAMBA_TOKEN_KEYVAL, (name, _value), comment)
            # insert before trailing blank lines / comments (which may belong
            # to the next section)
            index = len(self.content) - 1
            while index >= 0 and self.content[index].type in (
                    SambaToken.SAMBA_TOKEN_STRING,
                    SambaToken.SAMBA_TOKEN_BLANKLINE):
                index -= 1
            self.content.insert(index + 1, tok)

    def delKey(self, name):
        tok = self.fetchKey(name)
        if tok:
            self.content.remove(tok)


class SambaParser(object):
    def __init__(self):
        self.warnings = []
        self.honour_default_value_comments = True
        self.sections_reset()

    def sections_reset(self):
        self.sections = []
        self.sections_dict = {}

    def createToken(self, line, section):
        # eat trailing newline
        if len(line) > 0 and line[-1] == "\n":
            line = line[:-1]

        stripped_line = line.strip()
        if stripped_line != "":
            tmp = tuple(stripped_line)
        else:
            return SambaToken(SambaToken.SAMBA_TOKEN_BLANKLINE, line)

        if tmp[0] in ("#", ";"):
            try:
                commented_section = stripped_line[1:].strip()
                if commented_section and (commented_section[0] == "["
                                          and commented_section[-1] == "]"):
                    # a commented out section header: from here on, treat
                    # commented key/value pairs as plain comments until the
                    # next real section (used for the shipped example sections)
                    self.honour_default_value_comments = False
            except IndexError:
                pass

        if tmp[0] == "#":
            return SambaToken(SambaToken.SAMBA_TOKEN_STRING, line)

        if tmp[0] == ";":
            # possibly a commented out default key value
            name = None
            value = None
            try:
                name, value = line.split("=", 1)
                name = name[1:].strip()
                value = value.strip()
            except ValueError:
                pass

            if name and self.honour_default_value_comments:
                if not self.isDuplicateKey(name, section):
                    default_value = sambaDefaults.get_default(name)
                    try:
                        if value.lower() == default_value.lower():
                            return SambaToken(
                                SambaToken.SAMBA_TOKEN_KEYVAL,
                                (name, default_value))
                    except (AttributeError, UnknownKeyError):
                        pass
                else:
                    return None

            # possibly just a comment
            return SambaToken(SambaToken.SAMBA_TOKEN_STRING, line)

        if tmp[0] == "[" and tmp[-1] == "]":
            # section header
            self.honour_default_value_comments = True
            return SambaToken(SambaToken.SAMBA_TOKEN_SECTION_HEADER, line, None)

        # key/value line
        comment_token = None
        if "#" in line:
            data, comment = line.split("#", 1)
            comment_token = comment
            line = data
        else:
            data = line

        name, value = data.split("=", 1)
        name = name.strip()
        value = value.strip()

        if comment_token:
            return SambaToken(
                SambaToken.SAMBA_TOKEN_KEYVAL, (name, value), comment_token)

        if not self.isDuplicateKey(name, section):
            try:
                return SambaToken(SambaToken.SAMBA_TOKEN_KEYVAL, (name, value))
            except UnknownKeyError:
                return SambaToken(
                    SambaToken.SAMBA_TOKEN_KEYVAL, (name, value),
                    accept_unknown=True)
        # duplicate key: drop it so duplicates never enter the model
        return None

    def parse(self, smbconf_text):
        self.sections_reset()
        self.warnings = []
        self.honour_default_value_comments = True

        lines = smbconf_text.split("\n")
        # A trailing newline makes split() emit one empty element that is NOT a
        # real blank line; dropping it prevents each read->write pass from
        # appending a spurious blank line (which would otherwise grow unbounded).
        if lines and lines[-1] == "":
            lines = lines[:-1]
        if lines:
            section = SambaSection(self, None)

            lineno = 0
            for line in lines:
                lineno += 1
                token = self.createToken(line, section)
                if token:
                    if token.type == SambaToken.SAMBA_TOKEN_SECTION_HEADER:
                        section_name = token.value.strip()
                        assert section_name.startswith("[")
                        assert section_name.endswith("]")
                        section_name = _remove_ws(section_name[1:-1]).lower()
                        assert len(section_name) > 0
                        section = SambaSection(self, section_name, token.value)
                    else:
                        section.content.append(token)
                        if token.unknown:
                            self.warnings.append([lineno, token])

    def printSections(self):
        for name in self.getSections():
            print(str(self.getSection(name)))

    def getSections(self):
        return self.sections

    def getSection(self, name):
        if name is not None:
            name = _remove_ws(name.lower())
        return self.sections_dict[name]

    def getShareHeaders(self):
        return [h for h in self.getHeaders()
                if h not in ("global", "printers", "homes")]

    def getHeaders(self):
        return [name for name in self.sections if name]

    def isDuplicateKey(self, name, section):
        try:
            return section.keyExists(name)
        except UnknownKeyError:
            return False
