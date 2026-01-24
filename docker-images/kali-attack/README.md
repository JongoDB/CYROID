# CYROID Kali Attack Box

Full offensive security toolkit with KasmVNC desktop access.

## Overview

This image provides a complete penetration testing environment based on Kali Linux with a VNC-accessible desktop. It includes all major tools for network reconnaissance, Active Directory attacks, password cracking, web application testing, and post-exploitation.

## Quick Start

```bash
# Build the image
docker build -t cyroid/kali-attack:latest .

# Run with VNC access
docker run -d \
  --name kali \
  -p 6901:6901 \
  -e VNC_PW=changeme \
  cyroid/kali-attack:latest

# Access via browser: https://localhost:6901
# Default password: changeme
```

## Included Tools

### Network Reconnaissance
- nmap, masscan, rustscan
- enum4linux, enum4linux-ng
- dnsrecon, dnsenum, fierce
- wireshark, tcpdump

### Exploitation Frameworks
- Metasploit Framework
- SearchSploit (ExploitDB)

### Active Directory
- Impacket suite (secretsdump, psexec, wmiexec, etc.)
- CrackMapExec / NetExec
- Evil-WinRM
- BloodHound + bloodhound.py
- Kerbrute

### Password Attacks
- Hashcat, John the Ripper
- Hydra, Medusa
- Responder

### Web Testing
- nikto, gobuster, feroxbuster, ffuf
- sqlmap, wfuzz, whatweb

### Tunneling & Pivoting
- Chisel
- Ligolo-ng agent
- Proxychains4, socat, sshuttle

### Post-Exploitation
- LinPEAS, WinPEAS
- Various scripts in /opt/tools/

### Wordlists
- rockyou.txt
- SecLists (full collection)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| VNC_PW | (required) | VNC access password |
| VNC_RESOLUTION | 1920x1080 | Desktop resolution |

## File Locations

- **Tools**: `/opt/tools/`
- **PEAS scripts**: `/opt/tools/peas/`
- **Wordlists**: `/usr/share/wordlists/`, `/usr/share/seclists/`
- **Cheatsheet**: `/home/kasm-user/TOOLS_CHEATSHEET.md`

## Architecture Support

This image supports both `linux/amd64` and `linux/arm64` architectures.

## In CYROID

This image is used by the "Kali Attack Box" template. When deployed in a range:
- VNC console is automatically proxied through Traefik
- Shared folders can be mounted for file transfer
- Network interfaces are automatically configured

## Building Multi-Arch

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t cyroid/kali-attack:latest \
  --push .
```

## Customization

To add additional tools, create a new Dockerfile based on this one:

```dockerfile
FROM cyroid/kali-attack:latest
USER root
RUN apt-get update && apt-get install -y <your-tool>
USER 1000
```

Then save as a snapshot in CYROID for reuse.
