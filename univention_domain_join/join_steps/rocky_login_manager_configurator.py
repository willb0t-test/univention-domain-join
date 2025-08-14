#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import os
import subprocess
from shutil import copyfile

from univention_domain_join.utils.general import execute_as_root

userinfo_logger = logging.getLogger('userinfo')


class ConflictChecker(object):
    def configuration_conflicts(self) -> bool:
        login_manager = self.determine_used_login_manager()
        if login_manager in ['gdm', 'sddm', 'lightdm', 'xdm']:
            return False
        else:
            userinfo_logger.error('Error: Can\'t enable login with the login manager of your system.')
            userinfo_logger.error('       Please use GDM, SDDM, LightDM, or XDM for full compatibility with UCS.')
            userinfo_logger.error('       This error can be avoided by using the --skip-login-manager parameter.')
        return True

    def determine_used_login_manager(self) -> str:
        """Determine which display manager is active on Rocky Linux"""
        
        # Check systemctl for active display manager services
        display_managers = ['gdm', 'sddm', 'lightdm', 'xdm']
        
        for dm in display_managers:
            try:
                result = subprocess.run(['systemctl', 'is-active', dm], 
                                      capture_output=True, text=True)
                if result.returncode == 0 and 'active' in result.stdout:
                    userinfo_logger.info(f'Detected active display manager: {dm}')
                    return dm
            except FileNotFoundError:
                continue
        
        # Fallback: check if display manager services are enabled
        for dm in display_managers:
            try:
                result = subprocess.run(['systemctl', 'is-enabled', dm], 
                                      capture_output=True, text=True)
                if result.returncode == 0 and 'enabled' in result.stdout:
                    userinfo_logger.info(f'Detected enabled display manager: {dm}')
                    return dm
            except FileNotFoundError:
                continue
        
        # Default fallback
        userinfo_logger.warn('Could not determine display manager, assuming gdm')
        return 'gdm'

    def gdm_config_file_exists(self) -> bool:
        if os.path.isfile('/etc/gdm/custom.conf'):
            return True
        return False

    def lightdm_config_file_exists(self) -> bool:
        if os.path.isfile('/etc/lightdm/lightdm.conf.d/99-show-manual-userlogin.conf'):
            userinfo_logger.warn('Warning: /etc/lightdm/lightdm.conf.d/99-show-manual-userlogin.conf already exists.')
            return True
        return False


class RockyLoginManagerConfigurator(ConflictChecker):

    @execute_as_root
    def backup(self, backup_dir: str) -> None:
        # Backup GDM config
        if self.gdm_config_file_exists():
            os.makedirs(os.path.join(backup_dir, 'etc/gdm'), exist_ok=True)
            copyfile('/etc/gdm/custom.conf', 
                    os.path.join(backup_dir, 'etc/gdm/custom.conf'))

        # Backup LightDM config if exists
        if self.lightdm_config_file_exists():
            os.makedirs(os.path.join(backup_dir, 'etc/lightdm/lightdm.conf.d'), exist_ok=True)
            copyfile('/etc/lightdm/lightdm.conf.d/99-show-manual-userlogin.conf',
                    os.path.join(backup_dir, 'etc/lightdm/lightdm.conf.d/99-show-manual-userlogin.conf'))

    def enable_login_with_foreign_usernames(self) -> None:
        login_manager = self.determine_used_login_manager()
        
        if login_manager == 'gdm':
            self.enable_login_with_foreign_usernames_for_gdm()
        elif login_manager == 'lightdm':
            self.enable_login_with_foreign_usernames_for_lightdm()
        elif login_manager == 'sddm':
            self.enable_login_with_foreign_usernames_for_sddm()
        else:
            userinfo_logger.info(f'Login manager {login_manager} configuration not implemented, skipping...')

    @execute_as_root
    def enable_login_with_foreign_usernames_for_gdm(self) -> None:
        userinfo_logger.info('Configuring GDM for manual login with domain users')

        gdm_config = """[daemon]
# Enable manual login
TimedLoginEnable=false

[security]
# Allow manual typing of usernames
DisallowTCP=false

[xdmcp]
Enable=false

[chooser]

[debug]
# Enable debug for LDAP issues
Enable=false
"""

        # Create or modify GDM custom configuration
        os.makedirs('/etc/gdm', exist_ok=True)
        
        # If custom.conf exists, we need to modify it carefully
        if os.path.exists('/etc/gdm/custom.conf'):
            self.modify_existing_gdm_config()
        else:
            with open('/etc/gdm/custom.conf', 'w') as conf_file:
                conf_file.write(gdm_config)

    def modify_existing_gdm_config(self) -> None:
        """Modify existing GDM configuration to enable manual login"""
        
        with open('/etc/gdm/custom.conf', 'r') as f:
            content = f.read()
        
        # Ensure [daemon] section exists and has required settings
        if '[daemon]' not in content:
            content += '\n[daemon]\n'
        
        # Add manual login settings if not present
        if 'TimedLoginEnable' not in content:
            content = content.replace('[daemon]', '[daemon]\nTimedLoginEnable=false')
        
        with open('/etc/gdm/custom.conf', 'w') as f:
            f.write(content)

    @execute_as_root
    def enable_login_with_foreign_usernames_for_lightdm(self) -> None:
        userinfo_logger.info('Configuring LightDM for manual login with domain users')

        lightdm_config = \
            '[SeatDefaults]\n' \
            'greeter-show-manual-login=true\n' \
            'greeter-hide-users=true\n' \
            'allow-guest=false\n'

        os.makedirs('/etc/lightdm/lightdm.conf.d', exist_ok=True)
        with open('/etc/lightdm/lightdm.conf.d/99-show-manual-userlogin.conf', 'w') as conf_file:
            conf_file.write(lightdm_config)

    @execute_as_root
    def enable_login_with_foreign_usernames_for_sddm(self) -> None:
        userinfo_logger.info('Configuring SDDM for manual login with domain users')

        sddm_config = """[General]
# Enable manual username entry
HaltCommand=/usr/bin/systemctl poweroff
RebootCommand=/usr/bin/systemctl reboot

[Theme]
# Current theme

[Users]
# Hide user list to force manual entry
MaximumUid=65000
MinimumUid=500
HideUsers=
HideShells=/sbin/nologin,/bin/false
"""

        os.makedirs('/etc/sddm.conf.d', exist_ok=True)
        with open('/etc/sddm.conf.d/99-ucs-manual-login.conf', 'w') as conf_file:
            conf_file.write(sddm_config)
