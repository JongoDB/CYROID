# CYROID Samba Active Directory Domain Controller
# Provides AD DC functionality for ARM64 hosts where Windows Server isn't available
#
# Build: docker build -t cyroid/samba-dc:latest .
# Run:
#   docker run -d \
#     --hostname dc01 \
#     --name samba-dc \
#     -e SAMBA_REALM=CYROID.LOCAL \
#     -e SAMBA_DOMAIN=CYROID \
#     -e SAMBA_ADMIN_PASS=YourSecurePassword123! \
#     -p 53:53/udp -p 53:53/tcp \
#     -p 88:88/udp -p 88:88/tcp \
#     -p 135:135/tcp \
#     -p 139:139/tcp \
#     -p 389:389/tcp -p 389:389/udp \
#     -p 445:445/tcp \
#     -p 464:464/udp -p 464:464/tcp \
#     -p 636:636/tcp \
#     -p 3268:3268/tcp \
#     -p 3269:3269/tcp \
#     cyroid/samba-dc:latest

FROM ubuntu:22.04

LABEL maintainer="CYROID <https://github.com/cyroid>"
LABEL description="Samba Active Directory Domain Controller"
LABEL version="1.0.0"

ENV DEBIAN_FRONTEND=noninteractive

# Default configuration (override with environment variables)
ENV SAMBA_REALM=CYROID.LOCAL
ENV SAMBA_DOMAIN=CYROID
ENV SAMBA_ADMIN_PASS=CyroidAdmin123!
ENV SAMBA_DNS_FORWARDER=8.8.8.8

# Install Samba and dependencies
RUN apt-get update && apt-get install -y \
    samba \
    samba-dsdb-modules \
    samba-vfs-modules \
    krb5-config \
    krb5-user \
    winbind \
    libnss-winbind \
    libpam-winbind \
    smbclient \
    ldb-tools \
    dnsutils \
    ldap-utils \
    acl \
    attr \
    supervisor \
    net-tools \
    iproute2 \
    iputils-ping \
    vim \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy configuration files
COPY entrypoint.sh /entrypoint.sh
COPY supervisord.conf /etc/supervisor/conf.d/samba.conf
COPY smb.conf.template /etc/samba/smb.conf.template

RUN chmod +x /entrypoint.sh

# Create necessary directories
RUN mkdir -p /var/lib/samba/private \
    && mkdir -p /var/log/samba \
    && mkdir -p /run/samba

# Expose AD DC ports
# DNS
EXPOSE 53/tcp 53/udp
# Kerberos
EXPOSE 88/tcp 88/udp
# RPC
EXPOSE 135/tcp
# NetBIOS
EXPOSE 139/tcp
# LDAP
EXPOSE 389/tcp 389/udp
# SMB
EXPOSE 445/tcp
# Kerberos password change
EXPOSE 464/tcp 464/udp
# LDAPS
EXPOSE 636/tcp
# Global Catalog
EXPOSE 3268/tcp 3269/tcp

# Volume for persistent data
VOLUME ["/var/lib/samba", "/var/log/samba"]

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/samba.conf"]
