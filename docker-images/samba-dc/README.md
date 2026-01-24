# CYROID Samba Active Directory Domain Controller

Provides Active Directory Domain Controller functionality using Samba. This is primarily for ARM64 hosts where Windows Server isn't available via dockur/windows.

## Overview

This image creates a fully functional Active Directory Domain Controller that can:
- Authenticate Windows and Linux clients
- Provide DNS for the domain
- Support Kerberos authentication
- Allow LDAP queries
- Join Windows machines to the domain

## Quick Start

```bash
# Build the image
docker build -t cyroid/samba-dc:latest .

# Run with default settings
docker run -d \
  --hostname dc01 \
  --name samba-dc \
  -e SAMBA_REALM=CYROID.LOCAL \
  -e SAMBA_DOMAIN=CYROID \
  -e SAMBA_ADMIN_PASS=YourSecurePassword123! \
  --privileged \
  cyroid/samba-dc:latest
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| SAMBA_REALM | CYROID.LOCAL | Kerberos realm (uppercase) |
| SAMBA_DOMAIN | CYROID | NetBIOS domain name |
| SAMBA_ADMIN_PASS | CyroidAdmin123! | Administrator password |
| SAMBA_DNS_FORWARDER | 8.8.8.8 | DNS forwarder for external queries |
| CREATE_TEST_USERS | false | Set to "true" to create test users |

## Ports

| Port | Protocol | Service |
|------|----------|---------|
| 53 | TCP/UDP | DNS |
| 88 | TCP/UDP | Kerberos |
| 135 | TCP | RPC Endpoint Mapper |
| 139 | TCP | NetBIOS Session |
| 389 | TCP/UDP | LDAP |
| 445 | TCP | SMB |
| 464 | TCP/UDP | Kerberos Password Change |
| 636 | TCP | LDAPS |
| 3268 | TCP | Global Catalog |
| 3269 | TCP | Global Catalog SSL |

## Default Credentials

- **Administrator**: Administrator@CYROID.LOCAL
- **Password**: Value of SAMBA_ADMIN_PASS

## Test Users (if CREATE_TEST_USERS=true)

| Username | Password | Description |
|----------|----------|-------------|
| john.doe | Password123! | Standard user |
| jane.smith | Password123! | Standard user |
| svc.backup | SvcPassword123! | Service account |

## In CYROID

When deployed in a range:
1. Set the DC as the DNS server for other VMs
2. Windows VMs can join the domain
3. Use for AD attack scenarios

### Example Range Setup

```yaml
networks:
  - name: corporate
    subnet: 10.100.1.0/24
    gateway: 10.100.1.1

vms:
  - hostname: dc01
    template: Samba AD DC (ARM)
    ip_address: 10.100.1.10
    environment:
      SAMBA_REALM: CORP.LOCAL
      SAMBA_DOMAIN: CORP
      SAMBA_ADMIN_PASS: SecurePass123!
      CREATE_TEST_USERS: "true"

  - hostname: workstation01
    template: Ubuntu Desktop
    ip_address: 10.100.1.50
    dns_servers: 10.100.1.10
```

## Joining Windows to Domain

On a Windows VM:

```powershell
# Set DNS to point to the DC
Set-DnsClientServerAddress -InterfaceIndex (Get-NetAdapter).InterfaceIndex -ServerAddresses "10.100.1.10"

# Join domain
Add-Computer -DomainName "CORP.LOCAL" -Credential (Get-Credential)
Restart-Computer
```

## Architecture Support

This image supports both `linux/amd64` and `linux/arm64` architectures, making it ideal for Apple Silicon Macs and other ARM64 hosts.

## Persistent Data

Mount volumes for persistent domain data:

```bash
docker run -d \
  --hostname dc01 \
  --name samba-dc \
  -v samba-data:/var/lib/samba \
  -v samba-logs:/var/log/samba \
  -e SAMBA_REALM=CYROID.LOCAL \
  -e SAMBA_DOMAIN=CYROID \
  -e SAMBA_ADMIN_PASS=SecurePass! \
  cyroid/samba-dc:latest
```

## Troubleshooting

### Check domain status
```bash
docker exec samba-dc samba-tool domain level show
```

### List users
```bash
docker exec samba-dc samba-tool user list
```

### Test LDAP
```bash
docker exec samba-dc ldapsearch -H ldap://localhost -x -b "dc=cyroid,dc=local" "(objectClass=user)"
```

### View logs
```bash
docker logs samba-dc
docker exec samba-dc cat /var/log/samba/samba.log
```
