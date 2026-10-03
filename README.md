# samba-conf-tool

A modern **Python 3 + GTK4 / libadwaita** rewrite of the retired
`system-config-samba` graphical Samba administrator. It lets an ordinary user
manage Samba **shares**, **server settings** and **Samba users**; every
privileged operation (writing `smb.conf`, editing the passdb / `smbusers`,
restarting `smb`) is delegated to a small **root backend** reached over D-Bus
and gated by **polkit**.

The name (`samba-conf-tool`, D-Bus `org.SambaConfTool`) is deliberately
different from the old RPM so the two never collide.

## Layout

The directory layout deliberately mirrors upstream `system-config-samba` so the
rewrite reads as an evolution of it: the importable library lives in
`src/scsamba/`, the UI + entry scripts are flat modules in `src/`, and the
integration files live in `config/` and `icons/`.

```
src/
├── system-config-samba.py            # Adw.Application entry point (run directly)
├── system-config-samba-mechanism.py  # privileged backend launcher (systemd Exec)
├── mainWindow.py                     # share list + HeaderBar (primary window)
├── shareWindow.py                    # create / edit a share
├── basicPreferencesWin.py            # [global] server settings
├── sambaUserWin.py                   # Samba user list (add / properties / delete)
├── addUserWin.py                     # add / edit a single user
├── scsamba/                          # importable library (py3 port of upstream)
│   ├── __init__.py                   # bus / polkit name constants
│   ├── core/                         # token / parser / config / backend / view model
│   └── dbus/                         # proxy.py (UI client) + service.py (root backend)
└── test/                             # parser round-trip + private-bus backend tests
config/                               # D-Bus policy + activation, polkit, systemd unit,
                                      # introspection XML, .desktop
icons/                                # application icon
```

> Upstream's `src/*.glade`, `po/*.po` and the autotools `*_rules.mk` build were
> dropped in the rewrite (UI is built in code; see *Implementation deviations*).

## Privilege model

```
UI (you, GTK4)  --system bus-->  org.SambaConfTool backend (root, systemd-activated)
                                    └─ polkit action org.SambaConfTool.configure
```

The UI reads `smb.conf` directly (world-readable) so the share list works even
before the backend is installed. Writes go through the backend. The shipped
polkit policy uses **`allow_active=yes`**: a user with an active local login
session is authorised *without* a password prompt (this was an explicit design
decision — it trades a little security for convenience). Inactive / remote
sessions still require an admin password.

## Requirements

- Fedora-style Linux with `python3` (3.10+), **GTK4**, **libadwaita 1.x**
  (`gi` bindings via PyGObject).
- `smbd` / `pdbedit` / `smbpasswd` / `testparm` / `systemctl` for the backend.
- `polkit`, D-Bus system bus, systemd.

## Run from the source tree (no install)

```bash
python3 src/system-config-samba.py     # launches the GUI
make check                             # runs the unit tests (no root needed)
```

Without the backend installed the window opens in read-only preview: the share
list is populated, but Save / Delete / user edits report that no backend is
connected. The service-status line falls back to a plain `systemctl is-active
smb` query, so it is accurate even without the backend.

## Install (UI + privileged backend)

```bash
sudo make install
sudo systemctl daemon-reload           # pick up the new systemd unit
```

`make install` puts the Python package under `$(PREFIX)` (default
`/usr/local`), writes the backend launcher to `/usr/local/libexec`, and
installs the polkit / D-Bus / systemd / desktop / icon files with the
`@python@` and `@libexecdir@` placeholders substituted. The
`org.SambaConfTool` bus name is **D-Bus socket activated** — the backend starts
on the first call, no manual `systemctl start` needed.

Override paths with e.g. `make install PREFIX=/usr SYSTEMDDIR=/usr/lib/systemd/system`.

Remove everything with `sudo make uninstall`.

## SELinux / firewall notes

- Fedora ships SELinux **enforcing**. The backend runs as root and writes
  `/etc/samba/smb.conf`; if you relocate the config or run the backend from a
  non-standard path you may need an SELinux policy module. The stock
  `samba` policy already permits `smbd` to read `/etc/samba/smb.conf`.
- Opening a new share for Windows clients also needs the Samba firewall
  services enabled: `sudo firewall-cmd --add-service=samba --permanent && sudo firewall-cmd --reload`.
- New share directories may need `samba_share_t` labeling:
  `sudo semanage fcontext -a -t samba_share_t /srv/mysubdir && sudo restorecon -Rv /srv/mysubdir`.

## Implementation deviations from the original plan

- **UI is built programmatically** with libadwaita rows (`Adw.EntryRow`,
  `Adw.SwitchRow`, `Adw.ComboRow`, `Gtk.CheckRow`) rather than from
  `GtkBuilder .ui` files. The old `.glade` was GTK2-only and could not be
  mechanically converted; building in code keeps the dialogs consistent and
  testable. The plan's `data/ui/*.ui` are therefore not present.
- **Two D-Bus data files** are shipped: the bus *policy*
  (`org.SambaConfTool.conf` → `dbus-1/system.d`) and the *activation* record
  (`org.SambaConfTool.service` → `dbus-1/system-services`). Both are required
  for systemd `Type=dbus` activation.
- The share editor preserves the original field set and validations
  (directory existence, name de-dup / reserved words, guest-ok vs valid-users
  access modes); the server dialog preserves the security-mode linkage
  (password-server / realm requirements, domain forces encrypted passwords).

## License

GPL-2.0-or-later. Derived from `system-config-samba` © Red Hat, Inc.
(Brent Fox, Nils Philippsen and contributors); rewritten for GTK4 / Python 3.
