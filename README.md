<!--
SPDX-FileCopyrightText: 2017-2025 Univention GmbH
SPDX-License-Identifier: AGPL-3.0-only
-->
# Univention Domain Join

This is an assistant for joining [Ubuntu](https://ubuntu.com/about/release-cycle), [Linux Mint](https://www.linuxmint.com/download_all.php), and [Rocky Linux](https://rockylinux.org/) computers into Univention Corporate
Server (UCS) domains. It will perform the following steps for you:

- Create an LDAP object for your Ubuntu computer on UCS
- Configure DNS
- Configure Kerberos
- Configure the login manager, if necessary
- Configure PAM
- Configure SSSD

Univention Domain Join supports the following Linux distributions:

- `ubuntu24.04`
  - Ubuntu 24.04 LTS ("Noble Numbat")
- `ubuntu22.04`
  - Ubuntu 22.04 LTS („Jammy Jellyfish“)
  - Linux Mint 21 („Vanessa“)
- `ubuntu20.04`
  - Ubuntu 20.04 LTS („Focal Fossa“)
  - Linux Mint 20 („Ulyana“)
- `ubuntu18.04`
  - Ubuntu 18.04 LTS („Bionic Beaver“)
  - Linux Mint 19.2 („Tara“)
- `ubuntu17.10`
  - Ubuntu 17.10 („Artful Aardvark“)
- `ubuntu16.04`
  - Ubuntu 16.04 LTS („Xenial Xerus“)
- `ubuntu14.04`
  - Ubuntu 14.04 LTS („Trusty Tahr")
- `rockylinux8`
  - Rocky Linux 8 ("Green Obsidian")

The actual source code for the different Ubuntu releases can be found in
the corresponding git branches.

Univention Domain Join supports the Gnome and Unity desktop environments on Ubuntu/Linux Mint, and GDM, SDDM, LightDM, and XDM on Rocky Linux. The
configuration of the login manager of other desktop environments may not work,
but can be skipped using the `--skip-login-manager` parameter of the
`univention-domain-join-cli` tool.

# Download and Installation

## Ubuntu/Linux Mint

You can install Univention Domain Join assistant on Ubuntu via the [PPA of
Univention](https://launchpad.net/~univention-dev/ppa) using
these commands:

```shell
sudo add-apt-repository ppa:univention-dev/ppa
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install univention-domain-join
```

Run the assistant using the start menu.

There is also a command line tool `univention-domain-join-cli`, which can be installed separately
with the package `univention-domain-join-cli`.
Run `sudo univention-domain-join-cli --help` for more details.

## Rocky Linux 8

On Rocky Linux 8, you need to install the required dependencies and run from source:

1. Install required packages:
```shell
sudo dnf install -y python3 python3-pip sssd sssd-ldap sssd-krb5 krb5-workstation authselect
```

2. Clone and run the domain join tool:
```shell
git clone https://github.com/univention/univention-domain-join.git
cd univention-domain-join
sudo python3 scripts/cli.py --help
```

The Rocky Linux implementation includes:
- SSSD configuration for LDAP authentication
- Automatic group membership (wheel, audio, video, cdrom, dialout, plugdev)
- Support for GDM, SDDM, LightDM, and XDM display managers
- DNS entry creation in UCS domain
- Machine account creation in LDAP

# Doc

Documentation on how to build and release this package to launchpad can be found [here](doc/dev.md)

# License

Univention Domain Join is built on top of many existing open source projects
which use their own licenses. The source code of all parts written by
Univention is licensed under the AGPLv3 . Please see the
[license file](./LICENSE) for more information.
