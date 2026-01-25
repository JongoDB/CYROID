# Samba file server with sensitive data for Red Team Training Lab
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    samba \
    samba-common \
    smbclient \
    iproute2 \
    iputils-ping \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /srv/samba/public /srv/samba/sensitive /srv/samba/accounting

COPY smb.conf /etc/samba/smb.conf
COPY entrypoint.sh /entrypoint.sh
COPY sensitive-data/ /srv/samba/sensitive/

RUN chmod +x /entrypoint.sh && \
    chmod -R 777 /srv/samba

EXPOSE 139 445

ENTRYPOINT ["/entrypoint.sh"]
