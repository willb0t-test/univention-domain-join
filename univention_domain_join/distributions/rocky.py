#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only

# Alias for Rocky Linux distribution
# This handles the case where lsb_release returns "Rocky" instead of "RockyLinux"

from univention_domain_join.distributions.rockylinux import RockyLinuxJoiner

# Alias for backward compatibility with the module loading system
Joiner = RockyLinuxJoiner
