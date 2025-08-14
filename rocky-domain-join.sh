#!/bin/bash
# SPDX-FileCopyrightText: 2025 Univention GmbH
# SPDX-License-Identifier: AGPL-3.0-only

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI_SCRIPT="${SCRIPT_DIR}/scripts/cli.py"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        echo "Please run: sudo $0 $*"
        exit 1
    fi
}

check_rocky_linux() {
    if ! command -v lsb_release &> /dev/null; then
        log_error "lsb_release not found. Installing redhat-lsb-core..."
        dnf install -y redhat-lsb-core
    fi
    
    local distro=$(lsb_release -is 2>/dev/null | tr '[:upper:]' '[:lower:]')
    local version=$(lsb_release -rs 2>/dev/null)
    
    if [[ "$distro" != "rocky" && "$distro" != "rockylinux" ]]; then
        log_error "This script is designed for Rocky Linux. Detected: $distro"
        log_warning "Continuing anyway, but some features may not work correctly..."
    else
        log_info "Detected Rocky Linux $version"
    fi
}

install_dependencies() {
    log_info "Installing comprehensive dependencies for Rocky Linux domain join..."
    
    # Detect Python version
    local python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    local python_pkg="python${python_version//.}"
    
    log_info "Detected Python version: $python_version"
    
    # Core system packages
    local packages_to_install=()
    local required_packages=(
        # Core Python and development tools - use correct version
        "python3" "python3-pip" 
        "${python_pkg}" "${python_pkg}-devel"
        "gcc" "gcc-c++" "make"
        
        # SSSD and authentication
        "sssd" "sssd-ldap" "sssd-krb5" "sssd-tools"
        "authselect" "authselect-libs"
        
        # Kerberos
        "krb5-workstation" "krb5-libs" "krb5-devel"
        
        # LDAP - prioritize system package
        "openldap-clients" "openldap-devel" "python3-ldap"
        
        # SSL/TLS and security
        "openssl-devel" "ca-certificates" "nss-tools"
        "cyrus-sasl-devel" "libffi-devel"
        
        # System utilities
        "redhat-lsb-core" "bind-utils" "net-tools"
        "which" "wget" "curl" "sshpass"
        
        # PAM
        "pam" "pam-devel"
        
        # Python system packages - install directly
        "python3-dns" "python3-cryptography"
    )
    
    log_info "Checking system packages..."
    for package in "${required_packages[@]}"; do
        if ! rpm -q "$package" &> /dev/null; then
            packages_to_install+=("$package")
        fi
    done
    
    if [[ ${#packages_to_install[@]} -gt 0 ]]; then
        log_info "Installing ${#packages_to_install[@]} system packages..."
        log_info "Packages: ${packages_to_install[*]}"
        dnf install -y "${packages_to_install[@]}" || {
            log_error "Failed to install required system packages"
            exit 1
        }
    else
        log_success "All required system packages are already installed"
    fi
    
    # Install Python dependencies - prioritize system packages heavily
    log_info "Installing Python dependencies..."
    
    # Define system packages and their import names
    declare -A python_sys_packages=(
        ["python3-dns"]="dns.resolver"
        ["python3-ldap"]="ldap"
        ["python3-cryptography"]="cryptography"
        ["python3-pyasn1"]="pyasn1"
    )
    
    # Install missing system Python packages
    local sys_packages_to_install=()
    for sys_pkg in "${!python_sys_packages[@]}"; do
        local import_name="${python_sys_packages[$sys_pkg]}"
        if ! python3 -c "import $import_name" 2>/dev/null; then
            sys_packages_to_install+=("$sys_pkg")
        fi
    done
    
    if [[ ${#sys_packages_to_install[@]} -gt 0 ]]; then
        log_info "Installing system Python packages: ${sys_packages_to_install[*]}"
        dnf install -y "${sys_packages_to_install[@]}" || {
            log_warning "Some system Python packages failed to install"
        }
    fi
    
    # Only install critical packages via pip that don't have system equivalents
    local pip_only_packages=("IPy" "netifaces")
    local pip_packages_to_install=()
    
    for pkg in "${pip_only_packages[@]}"; do
        local import_name="$pkg"
        if ! python3 -c "import $import_name" 2>/dev/null; then
            pip_packages_to_install+=("$pkg")
        fi
    done
    
    # Install pip packages one by one with error handling
    for pkg in "${pip_packages_to_install[@]}"; do
        log_info "Installing $pkg via pip..."
        if ! pip3 install "$pkg"; then
            log_warning "Failed to install $pkg via pip, trying alternatives..."
            
            # Try alternative system packages
            case "$pkg" in
                "IPy")
                    dnf install -y python3-ipy 2>/dev/null || log_warning "Could not install IPy"
                    ;;
                "netifaces")
                    dnf install -y python3-netifaces 2>/dev/null || log_warning "Could not install netifaces"
                    ;;
            esac
        fi
    done
    
    # Verify critical imports
    log_info "Verifying Python dependencies..."
    local critical_imports=("dns.resolver" "IPy" "netifaces" "ldap")
    local missing_imports=()
    
    for import_name in "${critical_imports[@]}"; do
        if ! python3 -c "import $import_name" 2>/dev/null; then
            missing_imports+=("$import_name")
        fi
    done
    
    if [[ ${#missing_imports[@]} -gt 0 ]]; then
        log_warning "Some critical Python modules could not be imported: ${missing_imports[*]}"
        log_warning "Domain join may fail, but continuing anyway..."
    else
        log_success "All Python dependencies verified successfully"
    fi
}

print_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Rocky Linux Domain Join Script for Univention Corporate Server (UCS)

This script joins a Rocky Linux 8 machine to a UCS domain with the following features:
- LDAP machine account creation
- DNS entry creation in UCS domain  
- SSSD configuration for LDAP authentication
- Automatic group membership (wheel, audio, video, etc.)
- Display manager configuration (GDM, SDDM, LightDM, XDM)

OPTIONS:
    --domain DOMAIN         UCS domain name (e.g., company.local)
    --dc-ip IP             IP address of UCS domain controller
    --username USER        Domain administrator username
    --password PASS        Domain administrator password
    --password-file FILE   File containing domain administrator password
    --skip-login-manager   Do not configure display manager
    --force-ucs-dns        Use UCS server as DNS (changes network config)
    --logfile FILE         Path to log file (default: /var/log/univention/domain-join-cli.log)
    --install-deps         Only install dependencies and exit
    --help                 Show this help message

EXAMPLES:
    # Interactive domain join (will prompt for credentials)
    sudo $0 --domain company.local
    
    # Join with specific DC IP and credentials
    sudo $0 --dc-ip 192.168.1.10 --username administrator --password mypass
    
    # Install dependencies only
    sudo $0 --install-deps

EOF
}

main() {
    local install_deps_only=false
    local cli_args=()
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                print_usage
                exit 0
                ;;
            --install-deps)
                install_deps_only=true
                shift
                ;;
            *)
                cli_args+=("$1")
                shift
                ;;
        esac
    done
    
    log_info "Starting Rocky Linux Domain Join Script"
    echo "============================================"
    
    check_root
    check_rocky_linux
    install_dependencies
    
    if [[ "$install_deps_only" == true ]]; then
        log_success "Dependencies installed successfully"
        exit 0
    fi
    
    # Check if CLI script exists
    if [[ ! -f "$CLI_SCRIPT" ]]; then
        log_error "CLI script not found at: $CLI_SCRIPT"
        log_error "Make sure you're running this from the univention-domain-join directory"
        exit 1
    fi
    
    # Run the domain join CLI
    log_info "Starting domain join process..."
    echo "============================================"
    
    if ! python3 "$CLI_SCRIPT" "${cli_args[@]}"; then
        log_error "Domain join failed. Check the log file for details."
        exit 1
    fi
    
    echo "============================================"
    log_success "Rocky Linux domain join completed successfully!"
    log_info "Please reboot the system to complete the setup."
    echo ""
    log_info "After reboot, you should be able to:"
    log_info "- Login with domain users at the display manager"
    log_info "- Access domain resources"
    log_info "- Use 'getent passwd' to see domain users"
    log_info "- Use 'getent group' to see domain groups"
}

# Run main function with all arguments
main "$@"
