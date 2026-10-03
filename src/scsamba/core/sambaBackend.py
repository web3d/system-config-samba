# -*- coding: utf-8 -*-
# Copyright © 2002 - 2009 Red Hat, Inc.
# Copyright © 2002, 2003 Brent Fox <bfox@redhat.com>
#
# GPL-2.0-or-later. Python 2 -> Python 3 rewrite of sambaBackend.py.
#
# Owns on-disk state and privileged commands: smb.conf read/write (atomic,
# validated with testparm), the smbusers map, the passdb (pdbedit/smbpasswd),
# and the smb/nmb service lifecycle. In samba-conf-tool this runs on the
# polkit-gated root backend side; file/command paths are injectable so the
# model can be unit-tested against a temp smb.conf without root.

from __future__ import annotations

import errno
import gettext
import os
import shutil
import subprocess

from .sambaParser import SambaParser

_ = gettext.gettext

DEFAULT_SMB_CONF = "/etc/samba/smb.conf"
DEFAULT_TEMPLATE_CANDIDATES = (
    "/usr/share/doc/samba/examples/smb.conf.SUSE",
    "/usr/share/samba/smb.conf",
    "/usr/share/system-config-samba/smb.conf.template",
)


class SambaBackend(object):
    pdbedit_cmd = "/usr/bin/pdbedit"
    smbpasswd_cmd = "/usr/bin/smbpasswd"
    testparm_cmd = "/usr/bin/testparm"

    def __init__(self, smb_conf_path=None, smbusers_path=None):
        self.parser = SambaParser()
        self.smb_conf_path = smb_conf_path or DEFAULT_SMB_CONF
        self._explicit_smbusers = smbusers_path
        self.samba_passwd_file = []
        self.samba_users_file = []

    # ---------------------------------------------------------------- service
    def _unit_exists(self, unit: str) -> bool:
        try:
            return subprocess.run(
                ["systemctl", "cat", unit],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            ).returncode == 0
        except OSError:
            return False

    def nmbIsService(self) -> bool:
        # nmb may be its own unit on some Samba builds
        if self._service_ops_disabled():
            return False
        return self._unit_exists("nmb.service")

    def _services(self):
        units = ["smb.service"]
        if self.nmbIsService():
            units.append("nmb.service")
        return units

    @staticmethod
    def _service_ops_disabled() -> bool:
        # Tests / previews must not actually drive systemd (a non-root
        # "systemctl restart" can block on a polkit agent that isn't present).
        return os.environ.get("SAMBA_CONF_TOOL_SKIP_SERVICE") == "1"

    def isSambaRunning(self) -> bool:
        if self._service_ops_disabled():
            return False
        for unit in self._services():
            try:
                out = subprocess.run(
                    ["systemctl", "is-active", unit],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True, timeout=10,
                ).stdout.strip()
            except (OSError, subprocess.SubprocessError):
                return False
            if out != "active":
                return False
        return True

    def startSamba(self):
        if self._service_ops_disabled():
            return
        for unit in self._services():
            subprocess.run(["systemctl", "start", unit], check=False, timeout=10)

    def restartSamba(self):
        if self._service_ops_disabled():
            return
        for unit in self._services():
            subprocess.run(["systemctl", "restart", unit], check=False, timeout=10)

    # ---------------------------------------------------------------- smb.conf
    def readSmbConf(self) -> str:
        try:
            with open(self.smb_conf_path, "r", encoding="utf-8") as fh:
                contents = fh.read()
        except (IOError, OSError):
            contents = self._bootstrap_conf()

        self.parser.parse(contents)
        self.readSmbPasswords()
        self.readSmbUsersFile()
        return contents

    def _bootstrap_conf(self) -> str:
        for tpl in DEFAULT_TEMPLATE_CANDIDATES:
            if os.path.exists(tpl):
                shutil.copyfile(tpl, self.smb_conf_path)
                with open(self.smb_conf_path, "r", encoding="utf-8") as fh:
                    return fh.read()
        minimal = (
            "[global]\n"
            "\tworkgroup = WORKGROUP\n"
            "\tserver string = %h server\n"
            "\tsecurity = user\n"
            "\tmap to guest = Bad User\n"
            "\tpassdb backend = tdbsam\n\n"
        )
        with open(self.smb_conf_path, "w", encoding="utf-8") as fh:
            fh.write(minimal)
        return minimal

    def validate(self, contents: str) -> None:
        """Raise ValueError if testparm reports errors for this config text."""
        import tempfile
        fd, tmp = tempfile.mkstemp(suffix=".smb.conf")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(contents)
            proc = subprocess.run(
                [self.testparm_cmd, "-s", tmp],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                text=True,
            )
            if proc.returncode != 0:
                raise ValueError(proc.stderr.strip())
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def writeSmbConf(self, contents: str):
        validate = os.environ.get("SAMBA_CONF_TOOL_SKIP_VALIDATE") != "1"
        if validate:
            self.validate(contents)

        try:
            oldmode = os.stat(self.smb_conf_path)[0] & 0o7777
        except OSError:
            oldmode = 0o644

        new_path = self.smb_conf_path + ".new"
        try:
            os.unlink(new_path)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
        with open(new_path, "w", encoding="utf-8") as fh:
            fh.write(contents)
        os.chmod(new_path, oldmode)
        os.rename(new_path, self.smb_conf_path)

        self.parser.parse(contents)
        self.readSmbPasswords()
        self.readSmbUsersFile()

    # ---------------------------------------------------------------- passdb
    def readSmbPasswords(self):
        entries = []
        proc = subprocess.run(
            [self.pdbedit_cmd, "-L", "-w"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True,
        )
        for line in proc.stdout.splitlines():
            stripped = line.strip()
            if stripped and stripped[0] != "#":
                entries.append(line)

        if proc.returncode == 0:
            self.samba_passwd_file = entries
        elif os.getuid() != 0:
            # Non-root reads of passdb are expected to fail (passdb.tdb is
            # root-only). The production path runs this on the root backend;
            # for unit tests / non-privileged previews, degrade gracefully.
            self.samba_passwd_file = []
        else:
            raise RuntimeError(
                _("Error while reading Samba password list:\n%s")
                % "\n".join(x.strip() for x in entries))

    # ---------------------------------------------------------------- smbusers
    @property
    def smbusers_file_path(self):
        if self._explicit_smbusers:
            return self._explicit_smbusers
        globalsection = self.parser.getSection("global")
        if not globalsection.keyExists("username map"):
            globalsection.setKey("username map", "/etc/samba/smbusers")
        return globalsection.getKey("username map")

    def readSmbUsersFile(self):
        path = self.smbusers_file_path
        if os.access(path, os.F_OK):
            if os.access(path, os.R_OK):
                with open(path, "r", encoding="utf-8") as fh:
                    self.samba_users_file = fh.readlines()
            else:
                raise RuntimeError(
                    _("Cannot read %s.  Program will now exit." % path))

    def getPasswdFile(self):
        return self.samba_passwd_file

    def getUsersFile(self):
        return self.samba_users_file

    def getUserDict(self):
        user_dict = {}
        for line in self.samba_users_file:
            tmp_line = line.strip()
            if tmp_line and tmp_line[0] != "#":
                tokens = tmp_line.split("=")
                user_dict[tokens[0].strip()] = line
        return user_dict

    def get_user_alias_map(self):
        """Return {unix_name: windows_alias} parsed from the smbusers map."""
        alias = {}
        for line in self.samba_users_file:
            tmp_line = line.strip()
            if tmp_line and tmp_line[0] != "#" and "=" in tmp_line:
                unix_part, windows_part = tmp_line.split("=", 1)
                windows = windows_part.strip().split()
                alias[unix_part.strip()] = windows[0] if windows else ""
        return alias

    def writeSmbUsersFile(self):
        path = self.smbusers_file_path
        pathnew = path + ".new"
        if not ((os.access(path, os.W_OK) or not os.access(path, os.F_OK))
                and (os.access(pathnew, os.W_OK) or not os.access(pathnew, os.F_OK))):
            raise RuntimeError(_("Cannot write %s." % path))
        try:
            oldmode = os.stat(path)[0] & 0o7777
        except OSError:
            oldmode = 0o644
        try:
            os.unlink(pathnew)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
        with open(pathnew, "w", encoding="utf-8") as fh:
            for line in self.samba_users_file:
                fh.write(line)
        os.chmod(pathnew, oldmode)
        os.rename(pathnew, path)

    # ---------------------------------------------------------------- users
    def addUser(self, unix_name, windows_name, password):
        self.readSmbPasswords()
        self.readSmbUsersFile()
        if windows_name and len(windows_name) > 0 and unix_name != windows_name:
            self.samba_users_file.append("%s = %s\n" % (unix_name, windows_name))
            self.writeSmbUsersFile()

        subprocess.run(
            [self.smbpasswd_cmd, "-a", "-s", unix_name],
            input="%s\n%s\n" % (password, password),
            text=True, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        self.readSmbPasswords()
        self.readSmbUsersFile()

    def changePassword(self, unix_name, password):
        subprocess.run(
            [self.smbpasswd_cmd, "-s", unix_name],
            input="%s\n%s\n" % (password, password),
            text=True, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def changeWindowsUserName(self, unix_name, windows_name):
        userDict = self.getUserDict()
        found = 0
        for line in list(self.samba_users_file):
            try:
                if line == userDict.get(unix_name):
                    if windows_name and len(windows_name) > 0 and unix_name != windows_name:
                        self.samba_users_file[self.samba_users_file.index(line)] = (
                            "%s = %s\n" % (unix_name, windows_name))
                    else:
                        del self.samba_users_file[self.samba_users_file.index(line)]
                    found = 1
            except (ValueError, KeyError):
                pass

        if not found and windows_name and len(windows_name) > 0 and unix_name != windows_name:
            self.samba_users_file.append("%s = %s\n" % (unix_name, windows_name))

        self.writeSmbUsersFile()
        self.readSmbUsersFile()

    def deleteUser(self, name):
        subprocess.run(
            [self.pdbedit_cmd, "-x", "-u", name],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        user_dict = self.getUserDict()
        if name in user_dict:
            try:
                self.samba_users_file.remove(user_dict[name])
            except ValueError:
                pass
        self.writeSmbUsersFile()
        self.readSmbUsersFile()
        self.readSmbPasswords()

    def userExists(self, user) -> bool:
        self.readSmbUsersFile()
        for line in self.samba_users_file:
            tokens = line.split()
            if tokens and user == tokens[0]:
                return True
        self.readSmbPasswords()
        for line in self.samba_passwd_file:
            tokens = line.split(":")
            if tokens and user == tokens[0]:
                return True
        return False
