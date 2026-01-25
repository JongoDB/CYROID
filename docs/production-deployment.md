# CYROID Production Deployment Guide

This guide covers deploying CYROID for production use on any server - cloud VMs, VPS providers, on-premises servers, or home labs.

## Prerequisites

### System Requirements

- **OS**: Linux (Ubuntu 22.04+ recommended, Debian, RHEL/CentOS 8+)
- **CPU**: 4+ cores recommended
- **RAM**: 8GB minimum, 16GB+ recommended
- **Storage**: 50GB+ for system, additional for VM images
- **Network**: Static IP or domain name

### Software Requirements

1. **Docker Engine** (v24.0+)
   ```bash
   # Ubuntu/Debian
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER
   # Log out and back in
   ```

2. **Docker Compose** (v2.0+)
   ```bash
   # Usually included with Docker Engine
   docker compose version
   ```

3. **OpenSSL** (for certificate generation)
   ```bash
   # Usually pre-installed
   openssl version
   ```

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/jongodb/cyroid.git
cd cyroid
```

### 2. Run the Deployment Script

**Interactive mode (recommended for first-time):**
```bash
./scripts/deploy.sh
```

**With domain and Let's Encrypt:**
```bash
./scripts/deploy.sh --domain cyroid.example.com --email admin@example.com
```

**With IP address (self-signed certificate):**
```bash
./scripts/deploy.sh --ip 192.168.1.100
```

### 3. Access CYROID

Open your browser to `https://your-domain-or-ip`

The first user to register becomes the administrator.

## Deployment Options

### SSL Configuration

| Mode | Use Case | Requirements |
|------|----------|--------------|
| `letsencrypt` | Production with domain | Domain pointing to server, ports 80/443 open |
| `selfsigned` | Internal/IP-only | None (browser will show warning) |
| `manual` | Bring your own certs | Place certs in `./certs/` |

### Command Line Options

```bash
./scripts/deploy.sh [OPTIONS]

Options:
  --domain DOMAIN    Domain name for the server
  --ip IP            IP address for the server
  --email EMAIL      Email for Let's Encrypt notifications
  --ssl MODE         SSL mode: letsencrypt, selfsigned, manual
  --version VER      CYROID version (default: latest)
  --data-dir DIR     Data directory (default: /data/cyroid)
  --update           Update existing deployment
  --stop             Stop all services
  --status           Show service status
```

## Network Configuration

### Required Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 80 | TCP | HTTP (redirects to HTTPS) |
| 443 | TCP | HTTPS (main access) |

### Firewall Configuration

**UFW (Ubuntu):**
```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

**firewalld (RHEL/CentOS):**
```bash
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### Cloud Provider Security Groups

For AWS, Azure, GCP, etc., ensure your security group/firewall rules allow:
- Inbound TCP 80 from 0.0.0.0/0
- Inbound TCP 443 from 0.0.0.0/0

## Data Directories

CYROID stores data in the following locations:

```
/data/cyroid/                 # Default data directory
├── iso-cache/                # Downloaded ISO images
├── template-storage/         # VM templates and golden images
├── vm-storage/               # Running VM data
└── shared/                   # Shared files between VMs
```

To use a different location:
```bash
./scripts/deploy.sh --data-dir /path/to/data
```

## Managing the Deployment

### View Logs

```bash
# All services
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api
```

### Update to Latest Version

```bash
./scripts/deploy.sh --update
```

### Update to Specific Version

```bash
./scripts/deploy.sh --version 0.27.0 --update
```

### Stop Services

```bash
./scripts/deploy.sh --stop
```

### Check Status

```bash
./scripts/deploy.sh --status
```

### Restart Services

```bash
./scripts/deploy.sh --stop
./scripts/deploy.sh --update
```

## Security Hardening

### 1. Secure SSH Access

```bash
# Disable password authentication
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart sshd
```

### 2. Automatic Security Updates

```bash
# Ubuntu
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 3. Secrets

The deployment script automatically generates:
- JWT secret key (64 characters)
- PostgreSQL password
- MinIO password

These are stored in `.env.prod` with restricted permissions.

### 4. Database Security

PostgreSQL is not exposed externally - it's only accessible within the Docker network.

## Backup and Recovery

### Backup Data

```bash
# Stop services first for consistency
./scripts/deploy.sh --stop

# Backup data directory
sudo tar -czf cyroid-backup-$(date +%Y%m%d).tar.gz /data/cyroid

# Backup configuration
cp .env.prod .env.prod.backup
cp -r certs certs.backup

# Restart services
./scripts/deploy.sh --update
```

### Backup Database

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec db \
  pg_dump -U cyroid cyroid > cyroid-db-backup-$(date +%Y%m%d).sql
```

### Restore Database

```bash
# Stop services
./scripts/deploy.sh --stop

# Start only database
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d db

# Restore
cat cyroid-db-backup.sql | docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db psql -U cyroid cyroid

# Start all services
./scripts/deploy.sh --update
```

## Troubleshooting

### Services Not Starting

1. Check Docker status:
   ```bash
   sudo systemctl status docker
   ```

2. Check for port conflicts:
   ```bash
   sudo netstat -tlnp | grep -E ':(80|443)'
   ```

3. View service logs:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml logs
   ```

### Let's Encrypt Certificate Issues

1. Ensure domain points to server IP
2. Ensure ports 80/443 are open externally
3. Check Traefik logs:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml logs traefik
   ```

### Self-Signed Certificate Regeneration

```bash
./scripts/generate-certs.sh your-domain-or-ip
./scripts/deploy.sh --update
```

### Database Connection Issues

```bash
# Check database health
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec db pg_isready -U cyroid

# View database logs
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs db
```

### Reset Everything

**Warning: This deletes all data!**

```bash
./scripts/deploy.sh --stop
docker volume rm $(docker volume ls -q | grep cyroid)
rm .env.prod
./scripts/deploy.sh
```

## Architecture Overview

```
                    Internet
                        |
                    [Firewall]
                        |
                    ┌───────┐
                    │Traefik│ :80, :443
                    │(Proxy)│
                    └───┬───┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   ┌─────────┐    ┌─────────┐    ┌─────────┐
   │Frontend │    │   API   │    │  VNC    │
   │ (React) │    │(FastAPI)│    │ Proxy   │
   └─────────┘    └─────────┘    └─────────┘
                        │
                   ┌────┴────┐
                   ▼         ▼
              ┌────────┐ ┌───────┐
              │ Worker │ │ DinD  │
              │(Tasks) │ │(Ranges)│
              └────────┘ └───────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   ┌─────────┐ ┌───────┐ ┌───────┐
   │PostgreSQL│ │ Redis │ │ MinIO │
   └─────────┘ └───────┘ └───────┘
```

## Support

- **Issues**: https://github.com/jongodb/cyroid/issues
- **Documentation**: https://github.com/jongodb/cyroid/docs
