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
    def authselect_profile_exists(self) -> bool:
        try:
            result = subprocess.run(['authselect', 'current'], capture_output=True, text=True)
            if result.returncode == 0:
                userinfo_logger.info(f'Current authselect profile: {result.stdout.strip()}')
                return True
        except FileNotFoundError:
            userinfo_logger.warn('Warning: authselect command not found. PAM configuration may fail.')
        return False

    def sssd_profile_active(self) -> bool:
        try:
            result = subprocess.run(['authselect', 'current'], capture_output=True, text=True)
            if result.returncode == 0 and 'sssd' in result.stdout.lower():
                return True
        except FileNotFoundError:
            pass
        return False


class RockyPamConfigurator(ConflictChecker):

    @execute_as_root
    def backup(self, backup_dir: str) -> None:
        # Backup current authselect configuration
        os.makedirs(os.path.join(backup_dir, 'etc/authselect'), exist_ok=True)
        
        # Backup authselect current state
        try:
            result = subprocess.run(['authselect', 'current'], capture_output=True, text=True)
            if result.returncode == 0:
                with open(os.path.join(backup_dir, 'etc/authselect/current-profile.txt'), 'w') as f:
                    f.write(result.stdout)
        except Exception as e:
            userinfo_logger.warn(f'Could not backup authselect state: {e}')

        # Backup nsswitch.conf
        if os.path.exists('/etc/nsswitch.conf'):
            copyfile('/etc/nsswitch.conf', os.path.join(backup_dir, 'etc/nsswitch.conf'))

    def setup_pam(self) -> None:
        self.configure_authselect_sssd_profile()
        self.add_users_to_required_system_groups()

    @execute_as_root
    def configure_authselect_sssd_profile(self) -> None:
        userinfo_logger.info('Configuring authselect with SSSD profile for Rocky Linux')
        
        # Install SSSD profile with home directory creation
        try:
            subprocess.check_output([
                'authselect', 'select', 'sssd', 'with-mkhomedir', 'with-sudo', '--force'
            ], stderr=subprocess.STDOUT)
            userinfo_logger.info('Successfully configured authselect SSSD profile')
        except subprocess.CalledProcessError as e:
            userinfo_logger.error(f'Failed to configure authselect: {e.output.decode()}')
            raise

    @execute_as_root
    def add_users_to_required_system_groups(self) -> None:
        userinfo_logger.info('Configuring automatic group membership for LDAP users')
        
        # Rocky Linux system groups that LDAP users should be added to
        rocky_groups = "wheel,audio,video,cdrom,dialout,plugdev"
        
        # Create a custom authselect profile for group management
        # This is more complex than Ubuntu's pam_group approach
        self.configure_group_membership(rocky_groups)

    @execute_as_root
    def configure_group_membership(self, groups: str) -> None:
        """Configure automatic group membership for LDAP users on Rocky Linux"""
        
        # Create a custom authselect feature for group membership
        custom_profile_dir = "/etc/authselect/custom/ucs-sssd"
        
        try:
            # Create custom profile based on sssd profile
            subprocess.check_output([
                'authselect', 'create-profile', 'ucs-sssd', '-b', 'sssd'
            ], stderr=subprocess.STDOUT)
            
            # Modify the system-auth file to include pam_group
            system_auth_file = os.path.join(custom_profile_dir, "system-auth")
            if os.path.exists(system_auth_file):
                self.add_pam_group_to_system_auth(system_auth_file, groups)
            
            # Apply the custom profile
            subprocess.check_output([
                'authselect', 'select', 'custom/ucs-sssd', 'with-mkhomedir', 'with-sudo', '--force'
            ], stderr=subprocess.STDOUT)
            
            userinfo_logger.info(f'Configured automatic group membership: {groups}')
            
        except subprocess.CalledProcessError as e:
            userinfo_logger.warn(f'Could not create custom authselect profile: {e.output.decode()}')
            # Fallback: modify /etc/security/group.conf directly
            self.configure_group_conf_fallback(groups)

    def add_pam_group_to_system_auth(self, system_auth_file: str, groups: str) -> None:
        """Add pam_group configuration to system-auth file"""
        
        # Read current system-auth content
        with open(system_auth_file, 'r') as f:
            content = f.read()
        
        # Add pam_group line after pam_unix for auth
        auth_section = "auth        sufficient    pam_unix.so try_first_pass nullok"
        group_line = f"auth        optional      pam_group.so use_first_pass"
        
        if auth_section in content and group_line not in content:
            content = content.replace(auth_section, f"{auth_section}\n{group_line}")
        
        # Write back modified content
        with open(system_auth_file, 'w') as f:
            f.write(content)
        
        # Create /etc/security/group.conf with group assignments
        self.create_group_conf(groups)

    @execute_as_root
    def create_group_conf(self, groups: str) -> None:
        """Create /etc/security/group.conf for automatic group assignment"""
        
        group_conf_content = f"# Automatic group assignment for LDAP users\n"
        group_conf_content += f"*;*;*;Al0000-2400;{groups}\n"
        
        os.makedirs('/etc/security', exist_ok=True)
        
        # Check if group.conf already has our configuration
        if os.path.exists('/etc/security/group.conf'):
            with open('/etc/security/group.conf', 'r') as f:
                existing_content = f.read()
            if groups in existing_content:
                userinfo_logger.info('Group configuration already present in /etc/security/group.conf')
                return
        
        # Append our configuration
        with open('/etc/security/group.conf', 'a') as f:
            f.write(group_conf_content)
        
        userinfo_logger.info(f'Added group assignment configuration to /etc/security/group.conf: {groups}')

    @execute_as_root
    def configure_group_conf_fallback(self, groups: str) -> None:
        """Fallback method if custom authselect profile fails"""
        userinfo_logger.info('Using fallback method for group configuration')
        self.create_group_conf(groups)
        
        # Try to manually add pam_group to existing PAM configuration
        pam_files = ['/etc/pam.d/system-auth', '/etc/pam.d/password-auth']
        
        for pam_file in pam_files:
            if os.path.exists(pam_file):
                try:
                    with open(pam_file, 'r') as f:
                        content = f.read()
                    
                    # Add pam_group if not present
                    group_line = "auth        optional      pam_group.so use_first_pass"
                    if "pam_group.so" not in content:
                        # Find the auth section and add pam_group
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if "auth" in line and "pam_unix.so" in line and "sufficient" in line:
                                lines.insert(i + 1, group_line)
                                break
                        
                        # Write back modified content
                        with open(pam_file, 'w') as f:
                            f.write('\n'.join(lines))
                        
                        userinfo_logger.info(f'Added pam_group to {pam_file}')
                
                except Exception as e:
                    userinfo_logger.warn(f'Could not modify {pam_file}: {e}')
