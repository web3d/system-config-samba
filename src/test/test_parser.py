# -*- coding: utf-8 -*-
"""Round-trip and edit tests for the migrated smb.conf model.

Pure logic — no GTK, no root. Run with:
    python3 -m unittest discover -s src/test
or
    python3 src/test/test_parser.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scsamba.core import SambaBackend, SambaConfig, SambaParser  # noqa: E402

SAMPLE = """\
# Samba example configuration
# a leading comment in the preamble

[global]
\tworkgroup = MYGROUP
\tserver string = Samba Server %v
\tmap to guest = Bad User
\tsecurity = user
\tpassdb backend = tdbsam
\t; encrypt passwords = yes   # commented default, kept as key

[profiles]
\tcomment = Network Profiles Service
\tpath = %H
\tread only = No
\tstore dos attributes = Yes

[printers]
\tcomment = All Printers
\tpath = /var/spool/samba
\tcreate mask = 0700
\tprintable = Yes
\tbrowseable = No

[publicshare]
\tcomment = A public read-only share
\tpath = /srv/public
\tbrowseable = yes
\tread only = yes
\tguest ok = yes
"""


class ParserReadTests(unittest.TestCase):
    def setUp(self):
        self.parser = SambaParser()
        self.parser.parse(SAMPLE)

    def test_headers_and_share_filter(self):
        self.assertIn("global", self.parser.getHeaders())
        shares = self.parser.getShareHeaders()
        # homes/printers/global excluded; profiles & publicshare are shares
        self.assertIn("profiles", shares)
        self.assertIn("publicshare", shares)
        self.assertNotIn("printers", shares)
        self.assertNotIn("global", shares)

    def test_get_key_values(self):
        g = self.parser.getSection("global")
        self.assertEqual(g.getKey("workgroup"), "MYGROUP")
        self.assertEqual(g.getKey("security"), "user")

        pub = self.parser.getSection("publicshare")
        self.assertEqual(pub.getKey("path"), "/srv/public")
        # read only = yes -> getKey("writeable") inverts to No
        self.assertEqual(pub.getKey("read only"), "yes")

    def test_default_when_absent(self):
        # a key not present in the section falls back to defaults table
        pub = self.parser.getSection("publicshare")
        self.assertIsNotNone(pub.getKey("read only"))


class RoundTripTests(unittest.TestCase):
    @staticmethod
    def _ser(p):
        return "".join(str(p.getSection(n)) for n in p.sections)

    def test_serialize_reaches_fixed_point(self):
        # The normalizer (default-value masking, yes/No casing) needs one pass
        # to canonicalise; after that it is a fixed point: ser(parse(x)) is
        # stable from the 2nd iteration on.
        p1 = SambaParser(); p1.parse(SAMPLE)
        out1 = self._ser(p1)
        p2 = SambaParser(); p2.parse(out1)
        out2 = self._ser(p2)
        p3 = SambaParser(); p3.parse(out2)
        out3 = self._ser(p3)
        self.assertEqual(out2, out3, "serialize->parse must reach a stable fixed point")
        self.assertTrue(out1.endswith("\n"), "no spurious trailing blank line")
        self.assertFalse(out1.endswith("\n\n\n"))

    def test_comments_and_shares_survive(self):
        p = SambaParser()
        p.parse(SAMPLE)
        out = "".join(str(p.getSection(n)) for n in p.sections)
        for marker in ("# Samba example configuration", "[profiles]",
                       "[publicshare]", "workgroup = MYGROUP"):
            self.assertIn(marker, out)


class EditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile("w", suffix=".smb.conf",
                                               delete=False, encoding="utf-8")
        self.tmp.write(SAMPLE)
        self.tmp.close()
        self.backend = SambaBackend(smb_conf_path=self.tmp.name,
                                    smbusers_path=self.tmp.name + ".users")
        self.cfg = SambaConfig(self.backend)

    def tearDown(self):
        for f in (self.tmp.name, self.tmp.name + ".users"):
            try:
                os.unlink(f)
            except OSError:
                pass

    def test_set_and_get_key(self):
        share = self.cfg.getSection("publicshare")
        share.setKey("read only", "no")
        self.assertEqual(share.getKey("read only"), "no")

    def test_add_new_section(self):
        from scsamba.core.sambaParser import SambaSection
        from scsamba.core.sambaToken import SambaToken
        sec = SambaSection(self.cfg, "newshare")
        sec.content.append(SambaToken(SambaToken.SAMBA_TOKEN_KEYVAL,
                                      ("path", "/srv/new")))
        sec.content.append(SambaToken(SambaToken.SAMBA_TOKEN_KEYVAL,
                                      ("read only", "yes")))
        self.assertIn("newshare", self.cfg.getShareHeaders())

    def test_write_roundtrip_through_backend(self):
        share = self.cfg.getSection("publicshare")
        share.setKey("comment", "edited comment")
        self.cfg.writeFile()

        # re-read from disk via a fresh config
        cfg2 = SambaConfig(SambaBackend(
            smb_conf_path=self.tmp.name,
            smbusers_path=self.tmp.name + ".users"))
        self.assertEqual(cfg2.getSection("publicshare").getKey("comment"),
                         "edited comment")

    def test_validate_accepts_sample(self):
        # sample is a syntactically valid config; testparm must not error
        text = "".join(str(self.cfg.getSection(n)) for n in self.cfg.sections)
        self.backend.validate(text)  # raises ValueError on failure


if __name__ == "__main__":
    unittest.main(verbosity=2)
