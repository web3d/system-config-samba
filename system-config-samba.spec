%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib(0)")}
%{!?python_version: %global python_version %(%{__python} -c "from distutils.sysconfig import get_python_version; print get_python_version()")}

%if 0%{?fedora}%{?rhel} == 0 || 0%{?fedora} >= 12 || 0%{?rhel} >= 6
%bcond_without polkit1
%endif

# Enterprise versions pull in docs automatically
%if 0%{?rhel} > 0
%bcond_without require_docs
%else
%bcond_with require_docs
%endif

Summary: Samba server configuration tool
Name: system-config-samba
Version: 1.2.92
Release: 1%{?dist}
URL: http://fedorahosted.org/%{name}
License: GPLv2+
Group: System Environment/Base
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%__id_u -n)
BuildArch: noarch
Source0: http://fedorahosted.org/released/%{name}/%{name}-%{version}.tar.bz2
BuildRequires: python
BuildRequires: python-devel
BuildRequires: desktop-file-utils
BuildRequires: gettext
BuildRequires: intltool
Obsoletes: redhat-config-samba < 1.1.5
# Until version 1.2.67, system-config-samba contained online documentation.
# From version 1.2.68 on, online documentation is split off into its own
# package system-config-samba-docs. The following ensures that updating from
# earlier versions gives you both the main package and documentation.
Obsoletes: system-config-samba < 1.2.68
%if %{with require_docs}
Requires: system-config-samba-docs
%endif
Requires: dbus-python
Requires: pygtk2
Requires: pygtk2-libglade
Requires: python
Requires: python-slip >= 0.2.6
Requires: python-slip-dbus >= 0.2.9
Requires: samba
Requires: samba-common
Requires: hicolor-icon-theme

%description
system-config-samba is a graphical user interface for creating, 
modifying, and deleting samba shares.

%prep
%setup -q

%build
make %{?_smp_mflags}

%install
rm -rf %{buildroot}
make DESTDIR=%buildroot \
%if %{with polkit1}
    POLKIT0_SUPPORTED=0 \
%else
    POLKIT1_SUPPORTED=0 \
%endif
    install

desktop-file-install --vendor system --delete-original       \
  --dir %{buildroot}%{_datadir}/applications             \
%if 0%{?fedora}%{?rhel} && 0%{?fedora} <= 7 && 0%{?rhel} <= 5
  --add-category SystemSetup \
%endif
  %{buildroot}%{_datadir}/applications/system-config-samba.desktop

%find_lang %name

%clean
rm -rf %{buildroot}

%post
touch --no-create %{_datadir}/icons/hicolor
if [ -x %{_bindir}/gtk-update-icon-cache ]; then
  %{_bindir}/gtk-update-icon-cache --quiet %{_datadir}/icons/hicolor || :
fi

%postun
touch --no-create %{_datadir}/icons/hicolor
if [ -x %{_bindir}/gtk-update-icon-cache ]; then
  %{_bindir}/gtk-update-icon-cache --quiet %{_datadir}/icons/hicolor || :
fi

%files -f %{name}.lang
%defattr(-,root,root,-)
%doc COPYING
%{_bindir}/system-config-samba
%{_datadir}/system-config-samba
%{_datadir}/applications/system-config-samba.desktop
%{_datadir}/icons/hicolor/*/apps/system-config-samba.png
%{_sysconfdir}/dbus-1/system.d/*.conf
%{_datadir}/dbus-1/system-services/*.service
%if %{with polkit1}
%{_datadir}/polkit-1/actions/org.fedoraproject.config.samba.policy
%else
%{_datadir}/PolicyKit/policy/org.fedoraproject.config.samba.policy
%endif
%{python_sitelib}/scsamba
%{python_sitelib}/scsamba-%{version}-py%{python_version}.egg-info
%{python_sitelib}/scsamba.dbus-%{version}-py%{python_version}.egg-info

%changelog
* Tue Jun 21 2011 Nils Philippsen <nils@redhat.com> - 1.2.92-1
- don't trip over unknown smb.conf keys (#603964)

* Tue Oct 19 2010 Nils Philippsen <nils@redhat.com> - 1.2.91-1
- add and use jimmac's new themed icons (#562676)

* Tue Aug 24 2010 Nils Philippsen <nils@redhat.com> - 1.2.90-1
- pick up translation updates

* Wed Jun 30 2010 Nils Philippsen <nils@redhat.com>
- require docs in enterprise builds

* Wed Apr 28 2010 Nils Philippsen <nils@redhat.com>
- use different labels/shortcuts (#479486, #479487)

* Mon Apr 19 2010 Nils Philippsen <nils@redhat.com> - 1.2.89-1
- don't use string methods on unicode objects (#579279)

* Mon Apr 12 2010 Nils Philippsen <nils@redhat.com>
- remove obsolete PolicyKit-authentication-agent dependency (#581083)

* Fri Mar 26 2010 Nils Philippsen <nils@redhat.com> - 1.2.88-1
- fix auto-generation of share name alternatives

* Thu Mar 25 2010 Nils Philippsen <nils@redhat.com>
- make parser robust against indented section names (#573234)

* Tue Mar 23 2010 Nils Philippsen <nils@redhat.com> - 1.2.87-1
- pick up translation updates

* Mon Mar 22 2010 Nils Philippsen <nils@redhat.com>
- handle authorization problems better (#575473)

* Thu Feb 11 2010 Nils Philippsen <nils@redhat.com> - 1.2.86-1
- let SambaBackend.userExists() always return boolean values (#533743)

* Wed Feb 10 2010 Nils Philippsen <nils@redhat.com> - 1.2.85-1
- don't require libselinux-python directly anymore, this code was moved to
  slip.util.files
- actually set neverending timeout (#533743)

* Wed Feb 03 2010 Nils Philippsen <nils@redhat.com> - 1.2.84-1
- use monkey-patched SystemBus if available so that dbus methods don't time out
  (#533743)

* Wed Dec 30 2009 Nils Philippsen <nils@redhat.com>
- position dialogs centered on parents (#493827)

* Wed Dec 30 2009 Nils Philippsen <nils@redhat.com>
- use gtk.AboutDialog (#493928)

* Tue Sep 29 2009 Nils Philippsen <nils@redhat.com> - 1.2.83-1
- pick up new translations

* Tue Sep 15 2009 Nils Philippsen <nils@redhat.com>
- make polkit files translatable

* Mon Sep 14 2009 Nils Philippsen <nils@redhat.com> - 1.2.82-1
- pick up updated translations

* Wed Sep 02 2009 Nils Philippsen <nils@redhat.com> - 1.2.81-1
- initialize gettext correctly

* Fri Aug 28 2009 Nils Philippsen <nils@redhat.com> - 1.2.80-1
- initialize gettext at the right place

* Fri Aug 28 2009 Nils Philippsen <nils@redhat.com> - 1.2.79-1
- use str instead of unicode as N_ implementation

* Wed Aug 26 2009 Nils Philippsen <nils@redhat.com> - 1.2.78-1
- use gettext instead of rhpl

* Wed Aug 26 2009 Nils Philippsen <nils@redhat.com>
- explain obsoleting old versions

* Tue Aug 25 2009 Nils Philippsen <nils@redhat.com> - 1.2.77-1
- fix file list

* Tue Aug 25 2009 Nils Philippsen <nils@redhat.com>
- support PolicyKit 1.0

* Thu May 28 2009 Nils Philippsen <nils@redhat.com>
- use simplified source URL

* Thu May 28 2009 Nils Philippsen <nils@redhat.com> - 1.2.76-1
- handle missing smb.conf (#477944)

* Mon Apr 27 2009 Nils Philippsen <nils@redhat.com>
- avoid malformed username map entries (#460274)
- fix handling unknown configuration options (#460273)

* Thu Apr 09 2009 Nils Philippsen <nils@redhat.com> - 1.2.75-1
- fix sambaSection.getKey() for inverted keys
- allow auth_admin always (#494896)

* Thu Apr 09 2009 Nils Philippsen <nils@redhat.com> - 1.2.74-1
- fix use via dbus

* Thu Apr 09 2009 Nils Philippsen <nils@redhat.com> - 1.2.73-1
- fix antonym/inverted synonym handling regression
- various other fixes

* Tue Apr 07 2009 Nils Philippsen <nils@redhat.com> - 1.2.72-1
- merge SambaBackend and UserData classes (#490050)

* Mon Apr 06 2009 Nils Philippsen <nils@redhat.com>
- remove unnecessary mainWindow import
- keep section information with parser object

* Mon Mar 30 2009 Nils Philippsen <nils@redhat.com>
- further backend cleanup

* Tue Mar 24 2009 Nils Philippsen <nils@redhat.com>
- remove commented out old code
- don't pass off GUI objects into backend code

* Mon Mar 02 2009 Nils Philippsen <nils@redhat.com> - 1.2.71-1
- require PolicyKit-authentication-agent from F-11 on (#487191)

* Mon Feb 23 2009 Nils Philippsen <nils@redhat.com> - 1.2.70-1
- make parser cope with whitespace-less keywords (#460272)

* Mon Feb 16 2009 Nils Philippsen <nils@redhat.com>
- make warnings details expander show correct text and always use accelerators

* Wed Feb 11 2009 Nils Philippsen <nils@redhat.com>
- don't hardwire username map path (#460267)

* Thu Dec 11 2008 Nils Philippsen <nils@redhat.com> - 1.2.69-1
- new smb.conf template file (#474811)

* Tue Dec 09 2008 Nils Philippsen <nils@redhat.com>
- allow anyone to invoke dbus methods (#475524)

* Thu Dec 04 2008 Nils Philippsen <nils@redhat.com>
- fix parser, dbus wrapper to allow non-ASCII characters in configuration

* Fri Nov 28 2008 Nils Philippsen <nils@redhat.com> - 1.2.68-1
- split off documentation

* Wed Nov 12 2008 Nils Philippsen <nils@redhat.com> - 1.2.67-1
- use different defaults for PolicyKit authorizations (#470330)

* Fri Oct 31 2008 Nils Philippsen <nils@redhat.com> - 1.2.66-1
- fix typo that caused traceback

* Tue Oct 28 2008 Nils Philippsen <nils@redhat.com> - 1.2.65-1
- don't use consolehelper (#467784)
- fix installation without DESTDIR set

* Fri Oct 17 2008 Nils Philippsen <nils@redhat.com>
- use temporary smbusers file (/etc/samba/smbusers.new) for writing, then
  rename

* Fri Oct 10 2008 Nils Philippsen <nils@redhat.com>
- default to not using dbus as root and using dbus otherwise

* Fri Aug 29 2008 Nils Philippsen <nils@redhat.com>
- don't remove widgets in the add/edit user dialog when editing users (#460323)

* Thu Aug 28 2008 Nils Philippsen <nils@redhat.com>
- make --no-dbus work
- dump error message in case of pdbedit errors that don't stem from the user
  not being root (#460437)

* Tue Aug 19 2008 Nils Philippsen <nphilipp@redhat.com> - 1.2.64-1
- install dbus service mechanism

* Mon Aug 18 2008 Nils Philippsen <nphilipp@redhat.com>
- add python, python-devel build requirements
- remove usermode, libuser-python requirements
- add dbus-python, PolicyKit-gnome, python-slip-dbus requirements
- ship dbus, PolicyKit configuration and scsamba python module

* Fri Aug 15 2008 Nils Philippsen <nphilipp@redhat.com>
- use dbus/PolicyKit for privileged operations in the frontend
- use pwd.getpwall () instead of libuser for user enumeration

* Wed Aug 13 2008 Nils Philippsen <nphilipp@redhat.com>
- implement dbus service wrapping the backend

* Tue Aug 12 2008 Nils Philippsen <nphilipp@redhat.com>
- restructure source, prepare for dbus/PolicyKit

* Tue Apr 08 2008 Nils Philippsen <nphilipp@redhat.com> - 1.2.63-1
- pick up updated translations

* Tue Mar 25 2008 Nils Philippsen <nphilipp@redhat.com> - 1.2.62-1
- use hard links to avoid excessive disk space requirements

* Tue Jan 29 2008 Nils Philippsen <nphilipp@redhat.com> - 1.2.61-1
- migrate online help to yelp/Docbook XML

* Fri Jan 11 2008 Nils Philippsen <nphilipp@redhat.com> - 1.2.60-1
- use config-util for userhelper configuration from Fedora 9 on (#428393)

* Thu Dec 27 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.59-1
- rename sr@Latn to sr@latin (#426588)

* Wed Dec 05 2007 Nils Philippsen <nphilipp@redhat.com>
- overwrite *.pot and *.po files only on real changes

* Mon Oct 15 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.58-1
- avoid traceback when neither xdg-open nor htmlview is found

* Mon Oct 15 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.57-1
- re-add plain hicolor-icon-theme requirement to avoid unowned directories
- don't let gtk-update-icon-cache fail scriptlets
- remove obsolete no.po translation file (#332471)

* Mon Oct 15 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.56-1
- Merge review (#226468):
  - remove "ExclusiveOS: Linux"
  - remove hicolor-icon-theme requirement, call gtk-update-icon-cache with full
    path

* Fri Oct 12 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.55-1
- Merge review (#226468):
  - use xdg-open if available
  - obsolete redhat-config-samba with version
  - change license tag to GPLv2
  - install most python files not as executable
  - use %%config(noreplace)
  - add release tags to changelog entries to appease rpmlint
  - use "make %%{?_smp_mflags}"

* Mon Oct 08 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.54-1
- add "make diff" ("dif") and "make shortdiff" ("sdif")
- pull in updated translations

* Tue Oct 02 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.53-1
- pick up updated translations

* Sat Sep 15 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.52-1
- pick up updated translations

* Mon Sep 10 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.51-1
- update Polish, Serbian translations
- $RPM_BUILD_ROOT -> %%{buildroot}
- don't add distro specific desktop categories from Fedora 8 on (#277591)
- attempt to put the tool into the System -> Administration menu (#249440)
- require libuser-python from Fedora 8 on (#251354)
- make use of force tagging (since mercurial 0.9.4)

* Fri Aug 31 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.50-1
- bundle the GPL

* Thu Aug 30 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.49-1
- pull in updated translations

* Tue Aug 28 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.48-1
- gracefully handle unknown configuration options (#247541)

* Mon Aug 27 2007 Nils Philippsen <nphilipp@redhat.com>
- don't throw exceptions when encountering lines without trailing newlines
  (#253464)
- don't remove *.pyc files upon uninstalling the package (#256401)

* Mon Aug 13 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.47-1
- improve detection of commented out default values (#251477)
- use non-capital default values
- preserve whitespace better in comments
- don't use string module but str methods in sambaParser module

* Thu Aug 09 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.46-1
- honour default values in share window (#251477)
- try to deal sanely with commented out default values
- don't canonicalize key names when writing smb.conf

* Mon Jul 23 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.45-1
- make "make archive" work with Hg

* Wed Jun 27 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.44-1
- use gtk.FileChooseDialog instead of gtk.FileSelection (#245916, patch by Adel
  Gadllah)

* Wed Jun 27 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.43-1
- fix desktop file category (#245890)

* Thu Jun 14 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.42-1
- don't mask workgroup key when set to default value "workgroup" (#244169)

* Tue Apr 24 2007 Nils Philippsen <nphilipp@redhat.com>
- don't mark stuff translatable where it doesn't make sense (#237277)
- merge translatable strings that only differ in case (#237275)

* Tue Apr 17 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.41-1
- cope with separate nmb service (#234687)

* Tue Apr 17 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.40-1
- don't access smbpasswd directly but use pdbedit to allow for tdb/ldap
  backends (#236557)

* Thu Mar 22 2007 Nils Philippsen <nphilipp@redhat.com>
- update URL

* Tue Mar 20 2007 Nils Philippsen <nphilipp@redhat.com>
- mention that we are upstream
- clean buildroot before installing
- fix licensing blurb in PO files

* Mon Jan 15 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.39-1
- handle synonyms and inverted synonyms gracefully (#222595)

* Wed Jan 10 2007 Nils Philippsen <nphilipp@redhat.com> - 1.2.38-1
- get list of configuration parameters and defaults from testparm, fix
  duplicate dict keys (#219308)

* Tue Dec 12 2006 Nils Philippsen <nphilipp@redhat.com> - 1.2.37-1
- pick up updated translations (#216611)

* Fri Nov 24 2006 Nils Philippsen <nphilipp@redhat.com> - 1.2.36-1
- pick up updated translations (#216611)
- add dist tag

* Wed Mar 29 2006 Nils Philippsen <nphilipp@redhat.com> - 1.2.35-1
- don't require gnome module (#187200)
- don't wrap text in About dialog

* Fri Mar 03 2006 Nils Philippsen <nphilipp@redhat.com> - 1.2.34-1
- require hicolor-icon-theme (#182874, #182875)

* Mon Feb 06 2006 Nils Philippsen <nphilipp@redhat.com> - 1.2.33-1
- fix typo in PAM file (#179937)

* Thu Feb 02 2006 Nils Philippsen <nphilipp@redhat.com> - 1.2.32-1
- bump version

* Thu Dec 22 2005 Nils Philippsen <nphilipp@redhat.com>
- add sr@Latn.po to enable Serbian Latin translation

* Fri Oct 14 2005 Nils Philippsen <nphilipp@redhat.com>
- don't use pam_stack (#170642)

* Tue Jun 14 2005 Nils Philippsen <nphilipp@redhat.com>
- fix format string bug that broke lines with trailing comments in smb.conf
  (#160166)

* Fri May 06 2005 Nils Philippsen <nphilipp@redhat.com>
- make desktop file rebuild consistently

* Fri May 06 2005 Nils Philippsen <nphilipp@redhat.com> - 1.2.31-1
- use DESTDIR consistently

* Fri May 06 2005 Nils Philippsen <nphilipp@redhat.com> - 1.2.30-1
- make desktop file translatable (#156798)

* Wed Apr 27 2005 Jeremy Katz <katzj@redhat.com> - 1.2.29-2
- silence %%post

* Fri Apr 01 2005 Nils Philippsen <nphilipp@redhat.com> - 1.2.29-1
- fix deprecation warnings (#153051) with patch by Colin Charles
- update the GTK+ theme icon cache on (un)install (Christopher Aillon)

* Tue Mar 15 2005 Nils Philippsen <nphilipp@redhat.com> - 1.2.28-1
- fix dialog when share name is missing (#135119) again

* Wed Mar 09 2005 Nils Philippsen <nphilipp@redhat.com> - 1.2.27-1
- let users configure whether a share is browsable ("visible") or not ("hidden")

* Wed Feb 16 2005 Nils Philippsen <nphilipp@redhat.com>
- use UIManager when possible to avoid deprecation warnings (#134367, #143678)

* Wed Jan 12 2005 Nils Philippsen <nphilipp@redhat.com> - 1.2.26-1
- ignore case of share name when deleting share (#144504)
- when double clicking share, open properties dialog

* Tue Jan 11 2005 Nils Philippsen <nphilipp@redhat.com>
- assume default is "security == user" to avoid traceback on users dialog
  (#144511)
- update main window when changing share path (#144168)
- include Ukrainian translation in desktop file (#143659)

* Thu Jan 06 2005 Nils Philippsen <nphilipp@redhat.com> - 1.2.25-1
- use correct option menu for encrypt password
- use lower case for security value
- mask default values with a ";" instead of removing them altogether

* Sun Jan 02 2005 Nils Philippsen <nphilipp@redhat.com> - 1.2.24-1
- revamp BasicPreferencesWin.readFile() (#143951)
- remove stray debugging statement
- pick up new strings to be translated

* Sat Jan 01 2005 Nils Philippsen <nphilipp@redhat.com> - 1.2.23-1
- totally revamp how parsed smb.conf is handled internally (class
  SambaSection), among other things to not screw up smb.conf when editing share
  names (#143291)
- don't assume all users selected == "guest ok"
- make About/Copyright easily extensible without screwing up translations
- admit complicity
- remove tab indentation
- some more code consolidation
- pick up updated translations

* Tue Nov 23 2004 Nils Philippsen <nphilipp@redhat.com> - 1.2.22-1
- add missing options (#137756)

* Tue Oct 19 2004 Nils Philippsen <nphilipp@redhat.com> - 1.2.21-1
- don't raise exception when writing /etc/samba/smb.conf (#135946)
- updated translations

* Sun Oct 10 2004 Nils Philippsen <nphilipp@redhat.com> - 1.2.20-1
- use template file if smb.conf is missing (#131323)
- when saving smb.conf, write to new file and rename (#131323)
- set safe umask (#131323)

* Sat Oct 09 2004 Nils Philippsen <nphilipp@redhat.com> - 1.2.19-1
- fix dialog when share name is missing (#135119)

* Tue Oct 05 2004 Nils Philippsen <nphilipp@redhat.com> - 1.2.18-1
- use gtk.main() and gtk.main_quit() if available to avoid DeprecationWarnings
  (#134367)

* Mon Oct 04 2004 Nils Philippsen <nphilipp@redhat.com> - 1.2.17-1
- updated translations

* Thu Sep 23 2004 Nils Philippsen <nphilipp@redhat.com> - 1.2.16-1
- fix up translation of about window text (#133234)

* Wed Sep 15 2004 Nils Philippsen <nphilipp@redhat.com> - 1.2.15-1
- write smbpasswd file when adding user (#132084)

* Sun Aug 15 2004 Nils Philippsen <nphilipp@redhat.com> - 1.2.14-1
- make share name configurable (#110804, use patch from Philip Van Hoof, fix
  it up a bit)
- do some more code consolidation

* Tue Jul 20 2004 Brent Fox <bfox@redhat.com> - 1.2.13-1
- add 'cups option' entry (bug #128245)

* Wed Jun 23 2004 Brent Fox <bfox@redhat.com> - 1.2.12-1
- use popen instead of system (bug #112528)

* Tue Jun 22 2004 Brent Fox <bfox@redhat.com> - 1.2.11-1
- fix security and guest account defaults (bug #121745)

* Mon Jun 21 2004 Brent Fox <bfox@redhat.com> - 1.2.10-1
- write workgroup name explicitly (bug #126435)

* Mon Apr 12 2004 Brent Fox <bfox@redhat.com> 1.2.9-2
- fix icon path (bug #120181)

* Wed Mar 24 2004 Brent Fox <bfox@redhat.com> 1.2.9-1
- show all users (bug #118569)

* Tue Mar 23 2004 Brent Fox <bfox@redhat.com> 1.2.8-1
- add widgets for kerberos realm (bug #113094)

* Thu Mar 11 2004 Brent Fox <bfox@redhat.com> 1.2.7-1
- don't crash on ldap lines (bug #117812)

* Thu Mar 11 2004 Brent Fox <bfox@redhat.com> 1.2.6-1
- skip over blank lines in smbusers (bug #118017)

* Mon Mar  8 2004 Brent Fox <bfox@redhat.com> 1.2.5-1
- when using user level access, force the user to choose at least one user (bug #116566)

* Fri Mar  5 2004 Brent Fox <bfox@redhat.com> 1.2.4-1
- skip comments in smbpasswd file (bug #117604)

* Thu Mar  4 2004 Brent Fox <bfox@redhat.com> 1.2.3-1
- apply patch from bug #116564

* Mon Jan 12 2004 Brent Fox <bfox@redhat.com> 1.2.2-1
- fix glade file path problem
- wrap smbpasswd in quotes (bug #112528)
- don't call lower() on server string (bug #111758)

* Wed Jan  7 2004 Brent Fox <bfox@redhat.com> 1.2.1-1
- add a Requires for pygtk2-libglade

* Fri Nov 14 2003 Brent Fox <bfox@redhat.com> 1.2.0-1
- rename from redhat-config-samba to system-config-samba
- add Obsoletes for redhat-config-samba
- update for Python2.3

* Wed Oct 15 2003 Brent Fox <bfox@redhat.com> 1.1.4-1
- clarify error message (bug #105045)

* Wed Oct 15 2003 Brent Fox <bfox@redhat.com> 1.1.3-1
- don't allow whitespace in section headers (bug #106880)

* Mon Oct  6 2003 Brent Fox <bfox@redhat.com> 1.1.2-1
- add 'client plaintext auth' to sambaDefaults.py (bug #106072)

* Tue Sep 23 2003 Brent Fox <bfox@redhat.com> 1.1.1-1
- rebuild with the latest docs

* Wed Sep 10 2003 Brent Fox <bfox@redhat.com> 1.0.15-2
- bump relnum and rebuild

* Wed Sep 10 2003 Brent Fox <bfox@redhat.com> 1.0.15-1
- check for empty description before slicing (bug #103604)

* Wed Sep 10 2003 Brent Fox <bfox@redhat.com> 1.0.14-1
- rebuild for latest docs

* Tue Sep  9 2003 Brent Fox <bfox@redhat.com> 1.0.13-4
- bump relnum and rebuld

* Fri Sep  5 2003 Brent Fox <bfox@redhat.com> 1.0.13-3
- bump relnum and rebuild

* Fri Sep  5 2003 Brent Fox <bfox@redhat.com> 1.0.13-2
- bump relnum and rebuild

* Fri Sep  5 2003 Brent Fox <bfox@redhat.com> 1.0.13-1
- apply patch from Nalin to handle Samba3 changes
- fix selection problem with security option menu for ADS

* Thu Sep  4 2003 Brent Fox <bfox@redhat.com> 1.0.12-2
- bump relnum and rebuild

* Thu Sep  4 2003 Brent Fox <bfox@redhat.com> 1.0.12-1
- sambaDefaults.py: encrypt password default is "Yes" (bug #103752)
- basicPreferencesWin.py: Make encrypt passwd menu default to "Yes" (bug #103752)

* Thu Aug 28 2003 Brent Fox <bfox@bfox.devel.redhat.com> 1.0.11-2
- bump relnum and rebuild

* Thu Aug 28 2003 Brent Fox <bfox@bfox.devel.redhat.com> 1.0.11-1
- hook up help toolbar button

* Thu Aug 14 2003 Brent Fox <bfox@redhat.com> 1.0.10-1
- tag on every build

* Thu Jul  3 2003 Brent Fox <bfox@redhat.com> 1.0.8-2
- bump relnum and rebuild

* Thu Jul  3 2003 Brent Fox <bfox@redhat.com> 1.0.8-1
- don't let comment field end in backslash or whitespace (bug #92165)

* Tue Jul  1 2003 Brent Fox <bfox@redhat.com> 1.0.7-2
- bump and rebuild

* Tue Jul  1 2003 Brent Fox <bfox@redhat.com> 1.0.7-1
- the word 'server' is redundant (bug #98026)

* Fri Jun 27 2003 Brent Fox <bfox@redhat.com> 1.0.6-2
- bump version num and rebuild

* Fri Jun 27 2003 Brent Fox <bfox@redhat.com> 1.0.6-1
- add a synonym for 'browsable' (bug #97357)

* Mon May 19 2003 Brent Fox <bfox@redhat.com> 1.0.5-2
- add the 'share modes' flag to sambaDefaults.py

* Mon May 19 2003 Brent Fox <bfox@redhat.com> 1.0.5-1
- rebuild with the latest translations

* Wed May  7 2003 Brent Fox <bfox@redhat.com> 1.0.4-4
- we were omitting 'pid directory' in sambaDefaults.py

* Fri Mar 21 2003 Brent Fox <bfox@redhat.com> 1.0.4-3
- make 'only guest' a synonym (bug #84272)

* Tue Mar 18 2003 Brent Fox <bfox@redhat.com> 1.0.4-2
- remove some french translations that were breaking the menu system

* Mon Feb 17 2003 Brent Fox <bfox@redhat.com> 1.0.4-1
- handle problems with valid/invalid users (bug #84271)
- handle 'public' as a synonym of 'guest ok' (bug #84272)

* Thu Feb  6 2003 Brent Fox <bfox@redhat.com> 1.0.3-1
- return if value == None (bug #83660)

* Tue Feb  4 2003 Brent Fox <bfox@redhat.com> 1.0.2-2
- print an error if we can't import gtk

* Thu Jan 30 2003 Brent Fox <bfox@redhat.com> 1.0.2-1
- bump and build

* Wed Jan 22 2003 Tammy Fox <tfox@redhat.com> 1.0.1-7
- added docs (#80762)

* Thu Jan 16 2003 Brent Fox <bfox@redhat.com> 1.0.1-6
- add 'authentication server' (bug #82049)
- remove 'update encrypted'
- force encrypted passwords with domain security (bug #82050)

* Tue Jan 14 2003 Brent Fox <bfox@redhat.com> 1.0.1-5
- enable username map when using 'user' security
- add accelerators to notebook tabs

* Mon Jan 13 2003 Brent Fox <bfox@redhat.com> 1.0.1-4
- fix up the windows username problems

* Fri Jan 10 2003 Brent Fox <bfox@redhat.com> 1.0.1-3
- replace guest user GtkEntry widget with an OptionMenu (bug #81414)

* Fri Jan 10 2003 Tammy Fox <tfox@redhat.com> 1.0.1-2
- forgot to import string in addUserWin.py

* Thu Jan 9 2003 Tammy Fox <tfox@redhat.com> 1.0.1-1
- make popup windows transient (bug #81402)
- require a workgroup name
- strip strings before comparing to empty

* Wed Jan 8 2003 Tammy Fox <tfox@redhat.com>
- remove netbios
- GUI spacing tweaks
- make strings more user-friendly
- bug fixes

* Tue Jan  7 2003 Brent Fox <bfox@redhat.com> 1.0.0-5
- handle window destroys correctly (bug #81101)
- manually destroy about box

* Sat Jan  4 2003 Brent Fox <bfox@redhat.com> 1.0.0-4
- convert basicPreferences from combos to menu (bug #81035)

* Mon Dec 16 2002 Brent Fox <bfox@redhat.com> 1.0.0-3
- Don't allow a user to be added more than once.
- Fix strings for bug #79382

* Tue Dec 10 2002 Brent Fox <bfox@redhat.com> 1.0.0-1
- Clean up add directory dialog
- handle missing smbpasswd and smbusers files better

* Tue Nov 12 2002 Brent Fox <bfox@redhat.com> 0.9.9-3
- Pull in latest translations

* Wed Aug 14 2002 Tammy Fox <tfox@redhat.com>
- new icon

* Tue Aug 06 2002 Brent Fox <bfox@redhat.com> 0.9.9-1
- make sharing the root dir possible
- set defaults in UI for basic preferences (bug 70805)

* Fri Aug 02 2002 Brent Fox <bfox@redhat.com> 0.9.8-1
- Use new pam timestamp rules

* Thu Aug 01 2002 Tammy Fox <tfox@redhat.com>
- use stock icons for menu items
- add about box
- center popup windows
- set modal to true for popup windows

* Thu Aug 01 2002 Brent Fox <bfox@redhat.com> 0.9.7-1
- replace line for the console.apps  in spec file

* Wed Jul 24 2002 Brent Fox <bfox@redhat.com> 0.9.6-2
- update spec file for public beta 2

* Tue Jul 16 2002 Brent Fox <bfox@redhat.com> 0.9.4-3
- Fixed bug #68740

* Tue Jul 16 2002 Brent Fox <bfox@redhat.com> 0.9.4-2
- Fixed a few bugs with adding users
- Removed placeholder widgets

* Wed Jun 26 2002 Brent Fox <bfox@redhat.com> 0.9.1-1
- Fixed description

* Thu May 30 2002 Brent Fox <bfox@redhat.com> 0.1.0-3
- Fixed Requires 

* Tue Apr 30 2002 Brent Fox <bfox@redhat.com>
- Added lots of code.  App has basic functionality at this point.

* Mon Mar 10 2002 Brent Fox <bfox@redhat.com>
- initial coding and packaging
