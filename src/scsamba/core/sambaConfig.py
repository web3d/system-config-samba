# -*- coding: utf-8 -*-
# Copyright © 2009 Red Hat, Inc.
#
# GPL-2.0-or-later. Python 2 -> Python 3 rewrite of sambaConfig.py.
#
# Thin model wrapper binding the token parser to a backend (which owns the
# actual file locations), and serialising the section list back to text.

from __future__ import annotations

from .sambaParser import SambaParser


class SambaConfig(SambaParser):
    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        self.parseFile()

    def parseFile(self):
        return self.parse(self.backend.readSmbConf())

    def serialize(self) -> str:
        lines = ""
        for name in self.sections:
            lines += str(self.getSection(name))
        return lines

    def writeFile(self):
        self.backend.writeSmbConf(self.serialize())
