#!/bin/bash

# Configure network routing (VyOS router is gateway at .1)
configure_routing() {
    local ip=$(hostname -I | awk '{print $1}')
    if [ -n "$ip" ]; then
        local gateway=$(echo "$ip" | sed 's/\.[0-9]*$/.1/')
        if ! ip route show default | grep -q "via $gateway"; then
            ip route del default 2>/dev/null || true
            ip route add default via "$gateway" 2>/dev/null || true
        fi
    fi
}
configure_routing

create_smb_user() {
    local user=$1
    local pass=$2
    # Create Unix user if not exists
    useradd -M -s /sbin/nologin "$user" 2>/dev/null || true
    # Add to smbpasswd database - use printf for portability
    # The -s flag reads password from stdin, -a adds new user
    printf '%s\n%s\n' "$pass" "$pass" | smbpasswd -a -s "$user"
    # Enable the user in case it was disabled
    smbpasswd -e "$user" 2>/dev/null || true
    echo "Created SMB user: $user"
}

# Create users matching AD credentials
create_smb_user "admin" "Acme2024!"
create_smb_user "jsmith" "Summer2024"
create_smb_user "mwilliams" "Welcome123"
create_smb_user "svc_backup" "Backup2024"

exec smbd --foreground --no-process-group
