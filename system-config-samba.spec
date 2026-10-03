%global bus_name   org.fedoraproject.Config.Samba
%global polkit_id  org.fedoraproject.config.samba

Name:           system-config-samba
Version:        2.0.0
Release:        1%{?dist}
Summary:        Graphical Samba shares, server and users configuration tool

License:        GPL-2.0-or-later
URL:            https://github.com/web3d/system-config-samba
Source0:        %{name}-%{version}.tar.bz2

# Pure Python 3 + data files; no compiled extension.
BuildArch:      noarch

BuildRequires:  make
BuildRequires:  desktop-file-utils
BuildRequires:  gettext
BuildRequires:  systemd-rpm-macros

# Runtime: GTK4 / libadwaita UI + PyGObject over the system bus + the Samba
# tooling the root backend shells out to (testparm / smbpasswd / pdbedit),
# plus the polkit / D-Bus / systemd privilege stack.
Requires:       python3 >= 3.10
Requires:       python3-gobject-base
Requires:       gtk4
Requires:       libadwaita
Requires:       samba
Requires:       samba-common
Requires:       polkit
Requires:       dbus
Requires:       systemd
Requires:       hicolor-icon-theme

%description
A modern Python 3 / GTK4 / libadwaita rewrite of the retired GTK2 system-config-samba.
It graphically manages Samba shares, server settings and Samba users on the local
machine.  Privileged operations (writing /etc/samba/smb.conf, managing the Samba
passdb and restarting the smb service) are delegated to a small root backend reached
over the system D-Bus and gated by polkit.

%prep
%autosetup -p1

%build
# Nothing to compile: the application is pure Python and the UI is built in code.

%install
# The Makefile honours DESTDIR + PREFIX; with PREFIX=%{_prefix}=/usr the systemd
# unit lands in %%{_unitdir}, dbus/polkit files in their fixed system dirs.
make install DESTDIR=%{buildroot} PREFIX=%{_prefix}

%check
# Only the dependency-free parser suite runs in the build root (the D-Bus
# integration test needs a live session bus / GUI stack).  Full suite: `make check`.
PYTHONPATH=src %{__python3} -m unittest discover -s src/test -p "test_parser.py" -v

%post
# Backend is D-Bus socket activated (see the system-services file), so the unit is
# installed but intentionally NOT enabled: no boot-time daemon.
%systemd_post system-config-samba-backend.service
update-desktop-database &> /dev/null || :
touch --no-create %{_datadir}/icons/hicolor &> /dev/null || :

%preun
%systemd_preun system-config-samba-backend.service

%postun
%systemd_postun_with_restart system-config-samba-backend.service
update-desktop-database &> /dev/null || :
if [ $1 -eq 0 ] ; then
    gtk-update-icon-cache -q -t -f %{_datadir}/icons/hicolor &> /dev/null || :
fi

%posttrans
gtk-update-icon-cache -q -t -f %{_datadir}/icons/hicolor &> /dev/null || :

%files
%license COPYING
%doc README.md AUTHORS
%{_bindir}/%{name}
%{_libexecdir}/%{name}-backend
%dir %{_datadir}/%{name}
%{_datadir}/%{name}/*
%{_datadir}/applications/%{name}.desktop
%{_datadir}/icons/hicolor/scalable/apps/%{name}.svg
%{_unitdir}/%{name}-backend.service
%{_sysconfdir}/dbus-1/system.d/%{bus_name}.conf
%{_datadir}/dbus-1/system-services/%{bus_name}.service
%{_datadir}/polkit-1/actions/%{polkit_id}.policy

%changelog
* Sat Oct 03 2026 web3d <web3d@live.cn> - 2.0.0-1
- Modern Python 3 / GTK4 / libadwaita rewrite.
- Reuse upstream identity (D-Bus org.fedoraproject.Config.Samba, polkit
  org.fedoraproject.config.samba.configure) and packaging name system-config-samba.
- pip-free Makefile drives %%install; backend is D-Bus socket activated.
