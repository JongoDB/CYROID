# Cyber Range Orchestrator - Configuration & Quick Start

## Configuration Answers (Default Values)

Based on BIB-H Phase 1 requirements and best practices:

### 1. Default VM Specs by OS Type

```yaml
Windows Server:
  CPU: 4 cores
  RAM: 8 GB
  Disk: 80 GB
  Notes: Domain controllers, file servers need resources for services

Windows Workstation:
  CPU: 2 cores
  RAM: 4 GB
  Disk: 60 GB
  Notes: Finance workstations, analyst jump boxes

Linux Server (RHEL-based):
  CPU: 2 cores
  RAM: 4 GB
  Disk: 40 GB
  Notes: Web servers, SIEM, logging infrastructure

Linux Workstation (Debian-based):
  CPU: 2 cores
  RAM: 2 GB
  Disk: 30 GB
  Notes: Analyst tools, lightweight services
```

**Rationale**: Based on BIB-H Phase 1 topology which has domain controller, file server, 4 workstations, and jump box. These are overprovisioned slightly to handle training scenarios with multiple services.

---

### 2. Default Network CIDR Ranges

```yaml
Auto-Generated Subnets:
  Pattern: 172.16.{segment_id}.0/24
  
  Examples:
    - 172.16.1.0/24  # Blue Team Internal (Finance/Admin)
    - 172.16.2.0/24  # Blue Team Infrastructure (DC, File Server)
    - 172.16.10.0/24 # Evaluation Network (Jump boxes, SIEM)
    - 172.16.20.0/24 # Red Team C2 Infrastructure
    - 172.16.99.0/24 # Management Network (orchestrator access)

Reserved Ranges:
  - 172.16.0.0/24   # Reserved for orchestrator services
  - 172.16.255.0/24 # Reserved for future expansion

Gateway IP: Always .1 (e.g., 172.16.1.1)
DNS: 172.16.2.10 (typically the DC) or 8.8.8.8 fallback
```

**Rationale**: Private RFC 1918 range, non-overlapping with common corporate networks (10.0.0.0/8, 192.168.0.0/16). Matches BIB-H Phase 1 design.

---

### 3. Maximum Concurrent VMs per Range

```yaml
Soft Limit (Warning): 25 VMs
Hard Limit (Enforced): 50 VMs

Rationale:
  - BIB-H P1 uses ~7 VMs (DC, File Server, 4 workstations, jump box)
  - BIB-H P2-P4 likely add complexity: 15-25 VMs
  - 50 VM limit prevents single range from monopolizing host resources
  - Supports advanced scenarios (red team + blue team + eval infrastructure)
  
Resource Calculation:
  - Average VM: 2 CPU, 4 GB RAM, 50 GB disk
  - 50 VMs: 100 cores, 200 GB RAM, 2.5 TB disk
  - Requires appropriately sized host
```

**Override**: Range engineer can request limit increase with justification (admin approval).

---

### 4. Retention Period for Archived Ranges and Evidence

```yaml
Archived Ranges:
  Retention: 90 days
  After 90 days: Soft-delete (mark as deleted, retain config)
  After 180 days: Hard-delete (remove all data)
  
  Exemptions:
    - "Template" ranges: Retained indefinitely
    - "Reference" ranges (marked by admin): Retained 1 year
    
Evidence Packages:
  Retention: 2 years (regulatory compliance for training records)
  After 2 years: Archive to cold storage or delete (configurable)
  
  Required metadata retained indefinitely:
    - Student ID, range ID, submission date, final score
    - Aggregate metrics (no raw evidence)

Snapshots:
  Retention: 30 days for archived ranges
  After 30 days: Delete (expensive storage)
  Exception: Gold snapshots (pre-artifact, post-artifact) retained with template
```

**Rationale**: 
- 90 days allows review for multiple cohorts and AAR preparation
- 2 years for evidence aligns with typical training record retention policies
- Snapshots are storage-intensive, short retention unless explicitly marked

---

### 5. VM Naming Convention

```yaml
Format: {range_name}-{hostname}-{short_uuid}

Examples:
  - bibh-p1-alpha-WIN-DC01-a3f2
  - bibh-p1-alpha-WIN-FIN01-b7c4
  - bibh-p2-bravo-JUMP-ANALYST-9d2e
  - redteam-gamma-C2-SERVER-1f8a

Components:
  range_name: Sanitized (lowercase, alphanumeric + hyphen)
  hostname: As specified by user (uppercase preserved)
  short_uuid: Last 4 chars of UUID (collision prevention)

Docker Container Name: Same as VM name
Docker Network Name: {range_name}-{network_name}-{short_uuid}
  Example: bibh-p1-alpha-internal-a3f2

Rationale:
  - Clearly identifies which range a VM belongs to
  - Preserves user-friendly hostname
  - UUID suffix prevents collisions when cloning ranges
  - Easy to parse and filter in Docker CLI
```

---

### 6. Docker Orchestration: Swarm vs. Standalone

```yaml
Phase 1 Decision: Standalone Docker

Rationale:
  - Simpler deployment and debugging
  - Sufficient for single-host deployments
  - Lower complexity for initial development
  - Docker Compose is familiar to most users
  
Architecture Preparation for Future Swarm Migration:
  - Design API to be orchestration-agnostic
  - Use Docker SDK abstractions that support both modes
  - Label containers with metadata for discovery
  - Network design compatible with overlay networks
  
Migration Trigger to Swarm (Phase 6+):
  - When multi-host deployment needed
  - When high availability required for orchestrator services
  - When scaling beyond 100 concurrent VMs

Docker Swarm Benefits (Future):
  - Built-in load balancing
  - Service discovery
  - Rolling updates
  - Health checks and auto-restart
  - Overlay networking for cross-host VM communication
```

**Phase 1 Implementation**: Use `docker-compose.yml` for orchestrator services, `docker` SDK for VM management.

---

## Quick Start for Claude Code

### Pre-Development Checklist

Before starting development, ensure:
- [ ] Docker installed (version 24.0+)
- [ ] Docker Compose installed (version 2.20+)
- [ ] KVM support enabled (for dockur/windows): `lsmod | grep kvm`
- [ ] Sufficient host resources: 16+ CPU, 32+ GB RAM, 500+ GB disk
- [ ] Git repository initialized
- [ ] Code editor with Docker extension (VS Code recommended)

### Initial Project Setup Commands

```bash
# Create project structure
mkdir -p cyber-range-orchestrator/{backend,frontend,nginx,database,scripts,docs}
cd cyber-range-orchestrator

# Initialize Git
git init
echo "venv/" >> .gitignore
echo "node_modules/" >> .gitignore
echo ".env" >> .gitignore
echo "**/__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore
echo ".DS_Store" >> .gitignore

# Create Python virtual environment
cd backend
python3 -m venv venv
source venv/bin/activate

# Install core dependencies
pip install fastapi uvicorn sqlalchemy psycopg2-binary alembic python-dotenv pydantic pyjwt passlib docker redis celery minio boto3

# Create requirements.txt
pip freeze > requirements.txt

# Create initial backend structure
mkdir -p api models services tasks utils
touch main.py config.py
touch api/__init__.py api/auth.py api/ranges.py api/vms.py api/templates.py
touch models/__init__.py models/user.py models/range.py models/vm.py models/template.py
touch services/__init__.py services/docker_orchestrator.py
touch utils/__init__.py utils/hashing.py

# Create frontend structure
cd ../frontend
npx create-react-app . --template typescript
npm install tailwindcss @headlessui/react react-router-dom react-flow-renderer xterm @xterm/addon-fit recharts axios

# Initialize Tailwind
npx tailwindcss init

# Create .env template
cd ..
cat > .env.example << 'EOF'
# Database
POSTGRES_USER=rangeadmin
POSTGRES_PASSWORD=ChangeMeInProduction
POSTGRES_DB=cyberrange
DATABASE_URL=postgresql://rangeadmin:ChangeMeInProduction@db:5432/cyberrange

# Redis
REDIS_URL=redis://redis:6379/0

# MinIO
MINIO_ROOT_USER=rangeadmin
MINIO_ROOT_PASSWORD=ChangeMeInProduction
MINIO_ENDPOINT=minio:9000
MINIO_BUCKET=cyberrange-artifacts

# JWT
JWT_SECRET_KEY=your-secret-key-generate-with-openssl-rand-hex-32
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# Docker
DOCKER_HOST=unix:///var/run/docker.sock

# App
API_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000
EOF

# Copy to .env
cp .env.example .env

# Generate secure JWT secret
openssl rand -hex 32

echo "Update .env with the generated JWT secret above"
```

### Docker Compose Initial Setup

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    networks:
      - orchestrator-net

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    networks:
      - orchestrator-net

  minio:
    image: minio/minio:latest
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"
      - "9001:9001"
    networks:
      - orchestrator-net

  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: ${REDIS_URL}
      MINIO_ENDPOINT: ${MINIO_ENDPOINT}
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
    volumes:
      - ./backend:/app
      - /var/run/docker.sock:/var/run/docker.sock  # Docker control
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
      - minio
    networks:
      - orchestrator-net
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  celery:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: ${REDIS_URL}
      DOCKER_HOST: ${DOCKER_HOST}
    volumes:
      - ./backend:/app
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      - db
      - redis
    networks:
      - orchestrator-net
    command: celery -A tasks.celery_app worker --loglevel=info

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      REACT_APP_API_URL: ${API_URL}
    volumes:
      - ./frontend/src:/app/src
      - ./frontend/public:/app/public
    ports:
      - "3000:3000"
    networks:
      - orchestrator-net
    command: npm start

  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api
      - frontend
    networks:
      - orchestrator-net

volumes:
  postgres_data:
  minio_data:

networks:
  orchestrator-net:
    driver: bridge
```

### Backend Dockerfile

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Default command (overridden in docker-compose)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend Dockerfile

Create `frontend/Dockerfile`:

```dockerfile
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Expose port
EXPOSE 3000

# Start development server
CMD ["npm", "start"]
```

### Database Initialization

Create `database/init.sql`:

```sql
-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Initial schema will be managed by Alembic migrations
-- This file can contain seed data or initial setup

-- Example: Create initial admin user (hashed password: "admin123")
-- You'll replace this with proper user creation via API

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
```

### First Run

```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f api

# Verify services
curl http://localhost:8000/health
curl http://localhost:3000

# Access MinIO console
# Navigate to http://localhost:9001
# Login with MINIO_ROOT_USER and MINIO_ROOT_PASSWORD from .env

# Create initial bucket
# In MinIO console, create bucket named "cyberrange-artifacts"

# Run database migrations (once backend is ready)
docker-compose exec api alembic revision --autogenerate -m "Initial schema"
docker-compose exec api alembic upgrade head
```

---

## Development Workflow

### Daily Development Loop

```bash
# Start services
docker-compose up -d

# Tail logs
docker-compose logs -f api frontend

# Make code changes (hot reload enabled)
# API: Edit backend/*.py
# Frontend: Edit frontend/src/**/*.tsx

# Run tests (once implemented)
docker-compose exec api pytest
docker-compose exec frontend npm test

# Stop services
docker-compose down
```

### Database Migrations

```bash
# Create new migration after model changes
docker-compose exec api alembic revision --autogenerate -m "Description"

# Apply migration
docker-compose exec api alembic upgrade head

# Rollback
docker-compose exec api alembic downgrade -1
```

### Testing VM Creation

```bash
# SSH into API container
docker-compose exec api bash

# Test Docker SDK
python
>>> import docker
>>> client = docker.from_env()
>>> client.containers.list()
>>> # Test Ubuntu container creation
>>> container = client.containers.run("ubuntu:22.04", "echo 'Hello'", detach=True)
>>> print(container.logs())
>>> container.remove()
```

### Testing dockur/windows

```bash
# Pull dockur/windows image (large download ~10GB)
docker pull dockurr/windows

# Test Windows VM creation (takes 5-10 minutes first time)
docker run -d \
  --name test-windows \
  --device=/dev/kvm \
  -p 8006:8006 \
  -p 3389:3389 \
  -v /var/test-windows:/storage \
  -e VERSION="win11" \
  dockurr/windows

# Monitor logs
docker logs -f test-windows

# Once ready, access via VNC: http://localhost:8006
# Or RDP: localhost:3389

# Cleanup
docker stop test-windows
docker rm test-windows
rm -rf /var/test-windows
```

---

## Phase 1 Development Checklist (Week 1)

### Day 1: Project Setup
- [ ] Create project structure
- [ ] Initialize Git repository
- [ ] Set up Docker Compose with all services
- [ ] Verify all services start successfully
- [ ] Create `.env` with secure secrets

### Day 2: Database & Models
- [ ] Set up Alembic for migrations
- [ ] Create User model (username, email, hashed_password, role)
- [ ] Create initial migration
- [ ] Test database connection from API

### Day 3: Authentication API
- [ ] Implement password hashing (passlib + bcrypt)
- [ ] Create JWT utilities (encode, decode, verify)
- [ ] Build `/auth/register` endpoint
- [ ] Build `/auth/login` endpoint (returns JWT)
- [ ] Build `/auth/me` endpoint (returns current user)
- [ ] Test with curl or Postman

### Day 4: Frontend Auth
- [ ] Create login page component
- [ ] Create register page component
- [ ] Implement auth context (store JWT in localStorage)
- [ ] Create protected route wrapper
- [ ] Test: Register → Login → See dashboard

### Day 5: Dashboard UI
- [ ] Create dashboard layout component
- [ ] Create empty state (no ranges yet)
- [ ] Add navigation (sidebar or top nav)
- [ ] Add logout button
- [ ] Test: Full auth flow + dashboard access

---

## Phase 1 Completion Criteria

Before proceeding to Week 2, verify:
- ✅ All Docker services running without errors
- ✅ User can register a new account
- ✅ User can log in and receive JWT
- ✅ JWT is validated on protected endpoints
- ✅ Dashboard is accessible after login
- ✅ User can log out
- ✅ Database persists data across restarts
- ✅ No console errors in browser or API logs

**If all checked**, proceed to Week 2: VM Foundation.

---

## Troubleshooting Common Issues

### Issue: Docker Compose fails to start services

```bash
# Check Docker daemon
sudo systemctl status docker

# Check Docker Compose version
docker-compose --version

# View detailed error
docker-compose up

# Check port conflicts
sudo lsof -i :5432  # PostgreSQL
sudo lsof -i :8000  # API
sudo lsof -i :3000  # Frontend
```

### Issue: Cannot create Windows VMs (KVM error)

```bash
# Check KVM support
lsmod | grep kvm

# Enable KVM (if needed)
sudo modprobe kvm
sudo modprobe kvm_intel  # or kvm_amd

# Add user to kvm group
sudo usermod -aG kvm $USER
# Logout and login again

# Test KVM
kvm-ok
```

### Issue: Database migrations fail

```bash
# Drop all tables and recreate
docker-compose exec db psql -U rangeadmin -d cyberrange -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# Recreate migrations
docker-compose exec api alembic revision --autogenerate -m "Initial schema"
docker-compose exec api alembic upgrade head
```

### Issue: Frontend can't connect to API

```bash
# Check API is running
curl http://localhost:8000/health

# Check CORS settings in backend/main.py
# Ensure frontend URL is in allowed origins

# Check .env file has correct API_URL
cat .env | grep API_URL
```

---

## Next Steps

Once Phase 1 (Week 1) is complete:
1. Review code with Jon for feedback
2. Tag commit as `v0.1.0-week1`
3. Update roadmap with any adjustments
4. Begin Week 2: VM Foundation

**Estimated Total Development Time**: 21 weeks (5 months with 1-week buffer)

**First Usable Version**: End of Week 6 (Phase 2 complete)

**Production-Ready**: End of Week 21 (Phase 7 complete)
