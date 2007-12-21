%define namesuffix      wn
%define license		Freeware
%define summary_prefix	WordNet
%define descr_prefix	%{summary_prefix} (r) 1.7a
%define src		ftp://ftp.dict.org/pub/dict/pre/dict-wn_1.7a.tar.gz
%define dict_filename	%{namesuffix}
%define conf_file	%{_sysconfdir}/dictd.conf.d/%{name}

%define summ_desc_suf	for dictd

%define summary		%{summary_prefix} %{summ_desc_suf}
%define descr		%{descr_prefix} %{summ_desc_suf}
%define name		dictd-dicts-%{namesuffix}
%define version         0.1.0
%define release         %mkrel 11
%define group           Databases

%define __dictzip       %(which dictzip)
%define dictd_name      dictd
%define dictd_version   1.10.1-4

Summary:	%{summary}
Name:		%{name}
Version:	%{version}
Release:	%{release}
License:	%{license}
Group:		%{group}
Source:		%{src}
BuildRoot:	%{_tmppath}/%{name}-%{version}-%{release}-buildroot
BuildArch:	noarch
BuildRequires:	%{dictd_name}-utils >= %{dictd_version}
Provides:	dictd-dictionary = %version-%release, dictd-dictionaries = %version-%release
Requires:	%{dictd_name}-server >= %{dictd_version}
Requires(post):	%{dictd_name}-server >= %dictd_version
Requires(postun):	%{dictd_name}-server >= %dictd_version

%description
%{descr}

%prep
%setup -c -q

%build
# dictzip the dict dictionary file, if it's not yet zipped
if ls *.dict >/dev/null 2>&1; then
	dictzip *.dict
fi

%install
%{__rm} -rf %{buildroot}

%{__mkdir_p} %{buildroot}%{_datadir}/dict
cp %{dict_filename}*dict* %{buildroot}%{_datadir}/dict
cp %{dict_filename}*index* %{buildroot}%{_datadir}/dict
%{__mkdir_p} %{buildroot}%{_sysconfdir}/dictd.conf.d
printf "database %%-10s\t{ data \"%{_datadir}/dict/%{dict_filename}.dict.dz\"\n" %{dict_filename} >> %{buildroot}%{conf_file}
printf "\t\t\t  index \"%{_datadir}/dict/%{dict_filename}.index\" }\n" >> %{buildroot}%{conf_file}

%clean
%{__rm} -rf %{buildroot}

%post
%{_sbindir}/update-dictd.conf
echo "Restarting dictd-server, because configuration has been changed..."
service dictd-server reload

%postun
# XXX: control of package erasure ordering is only in rpm >= 4.4.8,
# this is a hack to not fail removal if dictd-server disappeared under our feet
if [ -x %{_sbindir}/update-dictd.conf ]; then
  %{_sbindir}/update-dictd.conf
  echo "Restarting dictd-server, because configuration has been changed..."
  service dictd-server reload
fi

%files
%defattr(644, root, root)
%{_datadir}/dict/%{dict_filename}*dict*
%{_datadir}/dict/%{dict_filename}*index*
%config		%conf_file


