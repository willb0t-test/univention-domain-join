#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only

# Alias for Rocky Linux distribution
# This handles the case where lsb_release returns "Rocky" instead of "RockyLinux"

try:
    from univention_domain_join.distributions.rockylinux import RockyLinuxJoiner
    # Alias for backward compatibility with the module loading system
    Joiner = RockyLinuxJoiner
except ImportError as e:
    # If there are missing dependencies, create a minimal error handler
    import logging
    import os
    import time
    from typing import Dict
    
    from univention_domain_join.distributions import AbstractJoiner
    
    userinfo_logger = logging.getLogger('userinfo')
    
    class RockyLinuxJoiner(AbstractJoiner):
        def __init__(self, ucr_variables: Dict[str, str], admin_username: str, admin_pw: str, dc_ip: str, skip_login_manager: bool, force_ucs_dns: bool) -> None:
            userinfo_logger.critical(f'Rocky Linux support is not available due to missing dependencies: {e}')
            userinfo_logger.critical('Please install required Python packages: dnspython, IPy, netifaces, python-ldap')
            raise ImportError(f'Rocky Linux joiner dependencies missing: {e}')
        
        def check_if_join_is_possible_without_problems(self) -> None:
            pass
            
        def create_backup_of_config_files(self) -> None:
            pass
            
        def join_domain(self) -> None:
            pass
    
    Joiner = RockyLinuxJoiner
