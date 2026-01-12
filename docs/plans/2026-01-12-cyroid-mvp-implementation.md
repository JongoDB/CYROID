# CYROID MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a fully functional cyber range orchestrator with visual network builder, Docker VM management, artifact placement, and snapshot support.

**Architecture:** Monolithic FastAPI backend with plugin extension points, React SPA frontend with React Flow for visual building, Dramatiq for async task processing, PostgreSQL for persistence, MinIO for artifact storage.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Dramatiq, PostgreSQL, Redis, MinIO, React 18, TypeScript, Vite, TailwindCSS, React Flow, Playwright

---

## Phase 1: Foundation

### Task 1: Project Structure Setup

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/requirements.txt`
- Create: `backend/cyroid/__init__.py`
- Create: `backend/cyroid/main.py`
- Create: `backend/cyroid/config.py`
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.gitignore`

**Step 1: Create backend directory structure**

```bash
mkdir -p backend/cyroid/{api,models,schemas,services,plugins,tasks,utils}
mkdir -p backend/cyroid/plugins/builtin/{auth_local,vm_docker,storage_minio}
mkdir -p backend/tests/{unit,integration}
mkdir -p backend/alembic/versions
```

**Step 2: Create backend requirements.txt**

```
# backend/requirements.txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
sqlalchemy==2.0.25
alembic==1.13.1
psycopg2-binary==2.9.9
pydantic==2.5.3
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
dramatiq[redis]==1.15.0
redis==5.0.1
minio==7.2.3
docker==7.0.0
websockets==12.0
httpx==0.26.0
pytest==7.4.4
pytest-asyncio==0.23.3
testcontainers==3.7.1
```

**Step 3: Create backend Dockerfile**

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "cyroid.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

**Step 4: Create backend config.py**

```python
# backend/cyroid/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://cyroid:cyroid@db:5432/cyroid"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "cyroid"
    minio_secret_key: str = "cyroid123"
    minio_bucket: str = "cyroid-artifacts"
    minio_secure: bool = False

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # App
    app_name: str = "CYROID"
    debug: bool = True

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**Step 5: Create backend main.py**

```python
# backend/cyroid/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cyroid.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Cyber Range Orchestrator In Docker",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "app": settings.app_name}
```

**Step 6: Create backend __init__.py files**

```python
# backend/cyroid/__init__.py
# backend/cyroid/api/__init__.py
# backend/cyroid/models/__init__.py
# backend/cyroid/schemas/__init__.py
# backend/cyroid/services/__init__.py
# backend/cyroid/plugins/__init__.py
# backend/cyroid/tasks/__init__.py
# backend/cyroid/utils/__init__.py
```

**Step 7: Create frontend directory structure**

```bash
mkdir -p frontend/src/{components,pages,hooks,services,stores,types,utils}
mkdir -p frontend/src/components/{common,layout,range-builder,console,dashboard}
mkdir -p frontend/public
mkdir -p e2e/tests
```

**Step 8: Create frontend package.json**

```json
{
  "name": "cyroid-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest",
    "lint": "eslint . --ext ts,tsx"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.21.3",
    "@xyflow/react": "^12.0.0",
    "@xterm/xterm": "^5.3.0",
    "@xterm/addon-fit": "^0.8.0",
    "zustand": "^4.5.0",
    "axios": "^1.6.5",
    "clsx": "^2.1.0",
    "lucide-react": "^0.312.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.48",
    "@types/react-dom": "^18.2.18",
    "@typescript-eslint/eslint-plugin": "^6.19.1",
    "@typescript-eslint/parser": "^6.19.1",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.17",
    "eslint": "^8.56.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "postcss": "^8.4.33",
    "tailwindcss": "^3.4.1",
    "typescript": "^5.3.3",
    "vite": "^5.0.12",
    "vitest": "^1.2.2"
  }
}
```

**Step 9: Create frontend vite.config.ts**

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
```

**Step 10: Create frontend tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

**Step 11: Create frontend tsconfig.node.json**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

**Step 12: Create frontend tailwind.config.js**

```javascript
// frontend/tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
      },
    },
  },
  plugins: [],
}
```

**Step 13: Create frontend postcss.config.js**

```javascript
// frontend/postcss.config.js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

**Step 14: Create frontend index.html**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>CYROID - Cyber Range Orchestrator</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

**Step 15: Create frontend src/main.tsx**

```tsx
// frontend/src/main.tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
```

**Step 16: Create frontend src/index.css**

```css
/* frontend/src/index.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  @apply bg-gray-50 text-gray-900;
}
```

**Step 17: Create frontend src/App.tsx**

```tsx
// frontend/src/App.tsx
import { Routes, Route } from 'react-router-dom'

function App() {
  return (
    <div className="min-h-screen">
      <Routes>
        <Route path="/" element={
          <div className="flex items-center justify-center min-h-screen">
            <div className="text-center">
              <h1 className="text-4xl font-bold text-primary-600">CYROID</h1>
              <p className="mt-2 text-gray-600">Cyber Range Orchestrator In Docker</p>
            </div>
          </div>
        } />
      </Routes>
    </div>
  )
}

export default App
```

**Step 18: Create frontend Dockerfile**

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
```

**Step 19: Create docker-compose.yml**

```yaml
# docker-compose.yml
version: '3.8'

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: cyroid
      POSTGRES_PASSWORD: cyroid
      POSTGRES_DB: cyroid
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U cyroid"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:latest
    environment:
      MINIO_ROOT_USER: cyroid
      MINIO_ROOT_PASSWORD: cyroid123
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"
      - "9001:9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 5s
      timeout: 5s
      retries: 5

  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql://cyroid:cyroid@db:5432/cyroid
      REDIS_URL: redis://redis:6379/0
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: cyroid
      MINIO_SECRET_KEY: cyroid123
    volumes:
      - ./backend:/app
      - /var/run/docker.sock:/var/run/docker.sock
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn cyroid.main:app --host 0.0.0.0 --port 8000 --reload

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql://cyroid:cyroid@db:5432/cyroid
      REDIS_URL: redis://redis:6379/0
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: cyroid
      MINIO_SECRET_KEY: cyroid123
    volumes:
      - ./backend:/app
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: dramatiq cyroid.tasks --processes 2 --threads 4

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "5173:5173"
    environment:
      - CHOKIDAR_USEPOLLING=true

  traefik:
    image: traefik:v3.0
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
    ports:
      - "80:80"
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro

volumes:
  postgres_data:
  minio_data:
```

**Step 20: Create .env.example**

```bash
# .env.example
# Database
DATABASE_URL=postgresql://cyroid:cyroid@db:5432/cyroid

# Redis
REDIS_URL=redis://redis:6379/0

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=cyroid
MINIO_SECRET_KEY=cyroid123
MINIO_BUCKET=cyroid-artifacts

# JWT
JWT_SECRET_KEY=change-me-in-production-use-openssl-rand-hex-32
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# App
DEBUG=true
```

**Step 21: Create .gitignore**

```
# .gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
.venv/
ENV/
.eggs/
*.egg-info/
.pytest_cache/

# Node
node_modules/
dist/
.npm
.pnpm-store/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Environment
.env
.env.local
*.local

# Docker
docker-compose.override.yml

# OS
.DS_Store
Thumbs.db

# Test
coverage/
htmlcov/
.coverage

# Build
build/
*.log
```

**Step 22: Verify backend structure**

Run: `ls -la backend/cyroid/`
Expected: api/, models/, schemas/, services/, plugins/, tasks/, utils/, __init__.py, main.py, config.py

**Step 23: Commit project structure**

```bash
git add -A
git commit -m "feat: initialize project structure

- Add backend with FastAPI setup
- Add frontend with Vite/React/TypeScript
- Add docker-compose with all services
- Configure Tailwind CSS
- Set up Dramatiq worker

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 2: Database Models and Migrations

**Files:**
- Create: `backend/cyroid/models/base.py`
- Create: `backend/cyroid/models/user.py`
- Create: `backend/cyroid/models/template.py`
- Create: `backend/cyroid/models/range.py`
- Create: `backend/cyroid/models/vm.py`
- Create: `backend/cyroid/models/network.py`
- Create: `backend/cyroid/models/artifact.py`
- Create: `backend/cyroid/models/snapshot.py`
- Create: `backend/cyroid/database.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`

**Step 1: Create database.py**

```python
# backend/cyroid/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from cyroid.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Step 2: Create models/base.py**

```python
# backend/cyroid/models/base.py
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from uuid import UUID, uuid4


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UUIDMixin:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
```

**Step 3: Create models/user.py**

```python
# backend/cyroid/models/user.py
from enum import Enum
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class UserRole(str, Enum):
    ADMIN = "admin"
    ENGINEER = "engineer"
    FACILITATOR = "facilitator"
    EVALUATOR = "evaluator"


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(default=UserRole.ENGINEER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    templates = relationship("VMTemplate", back_populates="created_by_user")
    ranges = relationship("Range", back_populates="created_by_user")
    artifacts = relationship("Artifact", back_populates="uploaded_by_user")
```

**Step 4: Create models/template.py**

```python
# backend/cyroid/models/template.py
from enum import Enum
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, Integer, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class OSType(str, Enum):
    WINDOWS = "windows"
    LINUX = "linux"


class VMTemplate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "vm_templates"

    name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    os_type: Mapped[OSType]
    os_variant: Mapped[str] = mapped_column(String(100))  # e.g., "Ubuntu 22.04", "Windows Server 2022"
    base_image: Mapped[str] = mapped_column(String(255))  # Docker image or dockur config

    # Default specs
    default_cpu: Mapped[int] = mapped_column(Integer, default=2)
    default_ram_mb: Mapped[int] = mapped_column(Integer, default=4096)
    default_disk_gb: Mapped[int] = mapped_column(Integer, default=40)

    # Configuration
    config_script: Mapped[Optional[str]] = mapped_column(Text)  # bash or PowerShell
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Ownership
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_by_user = relationship("User", back_populates="templates")

    # Relationships
    vms = relationship("VM", back_populates="template")
```

**Step 5: Create models/range.py**

```python
# backend/cyroid/models/range.py
from enum import Enum
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class RangeStatus(str, Enum):
    DRAFT = "draft"
    DEPLOYING = "deploying"
    RUNNING = "running"
    STOPPED = "stopped"
    ARCHIVED = "archived"
    ERROR = "error"


class Range(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ranges"

    name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[RangeStatus] = mapped_column(default=RangeStatus.DRAFT)

    # Ownership
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_by_user = relationship("User", back_populates="ranges")

    # Relationships
    networks: Mapped[List["Network"]] = relationship(
        "Network", back_populates="range", cascade="all, delete-orphan"
    )
    vms: Mapped[List["VM"]] = relationship(
        "VM", back_populates="range", cascade="all, delete-orphan"
    )
```

**Step 6: Create models/network.py**

```python
# backend/cyroid/models/network.py
from enum import Enum
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class IsolationLevel(str, Enum):
    COMPLETE = "complete"
    CONTROLLED = "controlled"
    OPEN = "open"


class Network(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "networks"

    range_id: Mapped[UUID] = mapped_column(ForeignKey("ranges.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    subnet: Mapped[str] = mapped_column(String(18))  # CIDR notation
    gateway: Mapped[str] = mapped_column(String(15))
    dns_servers: Mapped[Optional[str]] = mapped_column(String(255))  # Comma-separated
    isolation_level: Mapped[IsolationLevel] = mapped_column(default=IsolationLevel.COMPLETE)

    # Docker network ID (set after creation)
    docker_network_id: Mapped[Optional[str]] = mapped_column(String(64))

    # Relationships
    range = relationship("Range", back_populates="networks")
    vms: Mapped[List["VM"]] = relationship("VM", back_populates="network")
```

**Step 7: Create models/vm.py**

```python
# backend/cyroid/models/vm.py
from enum import Enum
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class VMStatus(str, Enum):
    PENDING = "pending"
    CREATING = "creating"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class VM(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "vms"

    range_id: Mapped[UUID] = mapped_column(ForeignKey("ranges.id", ondelete="CASCADE"))
    network_id: Mapped[UUID] = mapped_column(ForeignKey("networks.id"))
    template_id: Mapped[UUID] = mapped_column(ForeignKey("vm_templates.id"))

    hostname: Mapped[str] = mapped_column(String(63))
    ip_address: Mapped[str] = mapped_column(String(15))

    # Specs (can override template defaults)
    cpu: Mapped[int] = mapped_column(Integer)
    ram_mb: Mapped[int] = mapped_column(Integer)
    disk_gb: Mapped[int] = mapped_column(Integer)

    status: Mapped[VMStatus] = mapped_column(default=VMStatus.PENDING)

    # Docker container ID (set after creation)
    container_id: Mapped[Optional[str]] = mapped_column(String(64))

    # Position in visual builder (for UI)
    position_x: Mapped[int] = mapped_column(Integer, default=0)
    position_y: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    range = relationship("Range", back_populates="vms")
    network = relationship("Network", back_populates="vms")
    template = relationship("VMTemplate", back_populates="vms")
    snapshots: Mapped[List["Snapshot"]] = relationship(
        "Snapshot", back_populates="vm", cascade="all, delete-orphan"
    )
    artifact_placements: Mapped[List["ArtifactPlacement"]] = relationship(
        "ArtifactPlacement", back_populates="vm", cascade="all, delete-orphan"
    )
```

**Step 8: Create models/artifact.py**

```python
# backend/cyroid/models/artifact.py
from enum import Enum
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, Integer, Text, ForeignKey, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class ArtifactType(str, Enum):
    EXECUTABLE = "executable"
    SCRIPT = "script"
    DOCUMENT = "document"
    ARCHIVE = "archive"
    CONFIG = "config"
    OTHER = "other"


class MaliciousIndicator(str, Enum):
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"


class PlacementStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PLACED = "placed"
    VERIFIED = "verified"
    FAILED = "failed"


class Artifact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "artifacts"

    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    file_path: Mapped[str] = mapped_column(String(500))  # Path in MinIO
    sha256_hash: Mapped[str] = mapped_column(String(64), index=True)
    file_size: Mapped[int] = mapped_column(Integer)

    artifact_type: Mapped[ArtifactType] = mapped_column(default=ArtifactType.OTHER)
    malicious_indicator: Mapped[MaliciousIndicator] = mapped_column(default=MaliciousIndicator.SAFE)
    ttps: Mapped[List[str]] = mapped_column(JSON, default=list)  # MITRE ATT&CK IDs
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Ownership
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    uploaded_by_user = relationship("User", back_populates="artifacts")

    # Relationships
    placements: Mapped[List["ArtifactPlacement"]] = relationship(
        "ArtifactPlacement", back_populates="artifact"
    )


class ArtifactPlacement(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "artifact_placements"

    artifact_id: Mapped[UUID] = mapped_column(ForeignKey("artifacts.id"))
    vm_id: Mapped[UUID] = mapped_column(ForeignKey("vms.id", ondelete="CASCADE"))

    target_path: Mapped[str] = mapped_column(String(500))
    placement_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[PlacementStatus] = mapped_column(default=PlacementStatus.PENDING)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    artifact = relationship("Artifact", back_populates="placements")
    vm = relationship("VM", back_populates="artifact_placements")
```

**Step 9: Create models/snapshot.py**

```python
# backend/cyroid/models/snapshot.py
from typing import Optional
from uuid import UUID
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class Snapshot(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "snapshots"

    vm_id: Mapped[UUID] = mapped_column(ForeignKey("vms.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Docker image ID (snapshot stored as image)
    docker_image_id: Mapped[Optional[str]] = mapped_column(String(64))

    # Relationships
    vm = relationship("VM", back_populates="snapshots")
```

**Step 10: Update models/__init__.py**

```python
# backend/cyroid/models/__init__.py
from cyroid.models.base import Base
from cyroid.models.user import User, UserRole
from cyroid.models.template import VMTemplate, OSType
from cyroid.models.range import Range, RangeStatus
from cyroid.models.network import Network, IsolationLevel
from cyroid.models.vm import VM, VMStatus
from cyroid.models.artifact import Artifact, ArtifactPlacement, ArtifactType, MaliciousIndicator, PlacementStatus
from cyroid.models.snapshot import Snapshot

__all__ = [
    "Base",
    "User", "UserRole",
    "VMTemplate", "OSType",
    "Range", "RangeStatus",
    "Network", "IsolationLevel",
    "VM", "VMStatus",
    "Artifact", "ArtifactPlacement", "ArtifactType", "MaliciousIndicator", "PlacementStatus",
    "Snapshot",
]
```

**Step 11: Create alembic.ini**

```ini
# backend/alembic.ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

**Step 12: Create alembic/env.py**

```python
# backend/alembic/env.py
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cyroid.models import Base
from cyroid.config import get_settings

config = context.config
settings = get_settings()

config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Step 13: Create alembic/script.py.mako**

```mako
# backend/alembic/script.py.mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

**Step 14: Commit database models**

```bash
git add -A
git commit -m "feat: add database models

- User model with roles (admin, engineer, facilitator, evaluator)
- VMTemplate model with OS type, specs, config script
- Range model with status enum
- Network model with CIDR, gateway, isolation level
- VM model with specs, status, container tracking
- Artifact and ArtifactPlacement models
- Snapshot model
- Alembic configuration for migrations

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 3: Authentication System

**Files:**
- Create: `backend/cyroid/utils/security.py`
- Create: `backend/cyroid/schemas/auth.py`
- Create: `backend/cyroid/schemas/user.py`
- Create: `backend/cyroid/api/deps.py`
- Create: `backend/cyroid/api/auth.py`
- Modify: `backend/cyroid/main.py`
- Create: `backend/tests/unit/test_security.py`
- Create: `backend/tests/integration/test_auth.py`

**Step 1: Create utils/security.py**

```python
# backend/cyroid/utils/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from cyroid.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(user_id: UUID, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)

    to_encode = {
        "sub": str(user_id),
        "exp": expire,
    }
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[UUID]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return UUID(user_id)
    except JWTError:
        return None
```

**Step 2: Create schemas/user.py**

```python
# backend/cyroid/schemas/user.py
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr

from cyroid.models.user import UserRole


class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: UUID
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
```

**Step 3: Create schemas/auth.py**

```python
# backend/cyroid/schemas/auth.py
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

**Step 4: Update schemas/__init__.py**

```python
# backend/cyroid/schemas/__init__.py
from cyroid.schemas.user import UserBase, UserCreate, UserUpdate, UserResponse
from cyroid.schemas.auth import LoginRequest, TokenResponse

__all__ = [
    "UserBase", "UserCreate", "UserUpdate", "UserResponse",
    "LoginRequest", "TokenResponse",
]
```

**Step 5: Create api/deps.py**

```python
# backend/cyroid/api/deps.py
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from cyroid.database import get_db
from cyroid.models.user import User, UserRole
from cyroid.utils.security import decode_access_token

security = HTTPBearer()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    token = credentials.credentials
    user_id = decode_access_token(token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


def require_role(*roles: UserRole):
    def role_checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {', '.join(r.value for r in roles)}",
            )
        return current_user
    return role_checker


# Type aliases for common dependencies
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]
DBSession = Annotated[Session, Depends(get_db)]
```

**Step 6: Create api/auth.py**

```python
# backend/cyroid/api/auth.py
from fastapi import APIRouter, HTTPException, status

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models.user import User
from cyroid.schemas.auth import LoginRequest, TokenResponse
from cyroid.schemas.user import UserCreate, UserResponse
from cyroid.utils.security import verify_password, get_password_hash, create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: DBSession):
    # Check if username exists
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check if email exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create user
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: DBSession):
    user = db.query(User).filter(User.username == credentials.username).first()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    access_token = create_access_token(user.id)
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: CurrentUser):
    return current_user
```

**Step 7: Update main.py to include auth router**

```python
# backend/cyroid/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cyroid.config import get_settings
from cyroid.api.auth import router as auth_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Cyber Range Orchestrator In Docker",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "app": settings.app_name}
```

**Step 8: Create test for security utilities**

```python
# backend/tests/unit/test_security.py
import pytest
from uuid import uuid4

from cyroid.utils.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
)


def test_password_hashing():
    password = "testpassword123"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_access_token_creation_and_decoding():
    user_id = uuid4()
    token = create_access_token(user_id)

    decoded_id = decode_access_token(token)
    assert decoded_id == user_id


def test_invalid_token_returns_none():
    result = decode_access_token("invalid.token.here")
    assert result is None
```

**Step 9: Create conftest.py for tests**

```python
# backend/tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from cyroid.main import app
from cyroid.database import get_db
from cyroid.models import Base


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
```

**Step 10: Create integration test for auth**

```python
# backend/tests/integration/test_auth.py
import pytest


def test_register_user(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpassword123",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert "id" in data
    assert "password" not in data
    assert "hashed_password" not in data


def test_register_duplicate_username(client):
    # Register first user
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test1@example.com",
            "password": "testpassword123",
        },
    )

    # Try to register with same username
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test2@example.com",
            "password": "testpassword123",
        },
    )

    assert response.status_code == 400
    assert "Username already registered" in response.json()["detail"]


def test_login_success(client):
    # Register user first
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpassword123",
        },
    )

    # Login
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "testuser",
            "password": "testpassword123",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    # Register user first
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpassword123",
        },
    )

    # Login with wrong password
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "testuser",
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 401


def test_get_current_user(client):
    # Register and login
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpassword123",
        },
    )

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "testuser",
            "password": "testpassword123",
        },
    )
    token = login_response.json()["access_token"]

    # Get current user
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"


def test_get_current_user_no_token(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 403  # No credentials provided
```

**Step 11: Run unit tests**

Run: `cd /home/ubuntu/cyro/backend && python -m pytest tests/unit/test_security.py -v`
Expected: All tests pass

**Step 12: Run integration tests**

Run: `cd /home/ubuntu/cyro/backend && python -m pytest tests/integration/test_auth.py -v`
Expected: All tests pass

**Step 13: Commit authentication system**

```bash
git add -A
git commit -m "feat: implement authentication system

- Add password hashing with bcrypt
- Add JWT token creation and validation
- Add /auth/register endpoint
- Add /auth/login endpoint
- Add /auth/me endpoint with token validation
- Add role-based access control utilities
- Add unit tests for security utilities
- Add integration tests for auth endpoints

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 4: VM Template API

**Files:**
- Create: `backend/cyroid/schemas/template.py`
- Create: `backend/cyroid/api/templates.py`
- Modify: `backend/cyroid/main.py`
- Create: `backend/tests/integration/test_templates.py`

**Step 1: Create schemas/template.py**

```python
# backend/cyroid/schemas/template.py
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field

from cyroid.models.template import OSType


class VMTemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    os_type: OSType
    os_variant: str = Field(..., min_length=1, max_length=100)
    base_image: str = Field(..., min_length=1, max_length=255)
    default_cpu: int = Field(default=2, ge=1, le=32)
    default_ram_mb: int = Field(default=4096, ge=512, le=131072)
    default_disk_gb: int = Field(default=40, ge=10, le=1000)
    config_script: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class VMTemplateCreate(VMTemplateBase):
    pass


class VMTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    os_variant: Optional[str] = Field(None, min_length=1, max_length=100)
    base_image: Optional[str] = Field(None, min_length=1, max_length=255)
    default_cpu: Optional[int] = Field(None, ge=1, le=32)
    default_ram_mb: Optional[int] = Field(None, ge=512, le=131072)
    default_disk_gb: Optional[int] = Field(None, ge=10, le=1000)
    config_script: Optional[str] = None
    tags: Optional[List[str]] = None


class VMTemplateResponse(VMTemplateBase):
    id: UUID
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

**Step 2: Update schemas/__init__.py**

```python
# backend/cyroid/schemas/__init__.py
from cyroid.schemas.user import UserBase, UserCreate, UserUpdate, UserResponse
from cyroid.schemas.auth import LoginRequest, TokenResponse
from cyroid.schemas.template import VMTemplateBase, VMTemplateCreate, VMTemplateUpdate, VMTemplateResponse

__all__ = [
    "UserBase", "UserCreate", "UserUpdate", "UserResponse",
    "LoginRequest", "TokenResponse",
    "VMTemplateBase", "VMTemplateCreate", "VMTemplateUpdate", "VMTemplateResponse",
]
```

**Step 3: Create api/templates.py**

```python
# backend/cyroid/api/templates.py
from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models.template import VMTemplate
from cyroid.schemas.template import VMTemplateCreate, VMTemplateUpdate, VMTemplateResponse

router = APIRouter(prefix="/templates", tags=["VM Templates"])


@router.get("", response_model=List[VMTemplateResponse])
def list_templates(db: DBSession, current_user: CurrentUser):
    templates = db.query(VMTemplate).all()
    return templates


@router.post("", response_model=VMTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(template_data: VMTemplateCreate, db: DBSession, current_user: CurrentUser):
    template = VMTemplate(
        **template_data.model_dump(),
        created_by=current_user.id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/{template_id}", response_model=VMTemplateResponse)
def get_template(template_id: UUID, db: DBSession, current_user: CurrentUser):
    template = db.query(VMTemplate).filter(VMTemplate.id == template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
    return template


@router.put("/{template_id}", response_model=VMTemplateResponse)
def update_template(
    template_id: UUID,
    template_data: VMTemplateUpdate,
    db: DBSession,
    current_user: CurrentUser,
):
    template = db.query(VMTemplate).filter(VMTemplate.id == template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    update_data = template_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    db.commit()
    db.refresh(template)
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(template_id: UUID, db: DBSession, current_user: CurrentUser):
    template = db.query(VMTemplate).filter(VMTemplate.id == template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    db.delete(template)
    db.commit()


@router.post("/{template_id}/clone", response_model=VMTemplateResponse, status_code=status.HTTP_201_CREATED)
def clone_template(template_id: UUID, db: DBSession, current_user: CurrentUser):
    template = db.query(VMTemplate).filter(VMTemplate.id == template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    cloned = VMTemplate(
        name=f"{template.name} (Copy)",
        description=template.description,
        os_type=template.os_type,
        os_variant=template.os_variant,
        base_image=template.base_image,
        default_cpu=template.default_cpu,
        default_ram_mb=template.default_ram_mb,
        default_disk_gb=template.default_disk_gb,
        config_script=template.config_script,
        tags=template.tags.copy() if template.tags else [],
        created_by=current_user.id,
    )
    db.add(cloned)
    db.commit()
    db.refresh(cloned)
    return cloned
```

**Step 4: Update main.py to include templates router**

```python
# backend/cyroid/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cyroid.config import get_settings
from cyroid.api.auth import router as auth_router
from cyroid.api.templates import router as templates_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Cyber Range Orchestrator In Docker",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(templates_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "app": settings.app_name}
```

**Step 5: Create integration test for templates**

```python
# backend/tests/integration/test_templates.py
import pytest


@pytest.fixture
def auth_headers(client):
    # Register and login
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpassword123",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpassword123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_template(client, auth_headers):
    response = client.post(
        "/api/v1/templates",
        headers=auth_headers,
        json={
            "name": "Ubuntu Server",
            "description": "Ubuntu 22.04 LTS Server",
            "os_type": "linux",
            "os_variant": "Ubuntu 22.04",
            "base_image": "ubuntu:22.04",
            "default_cpu": 2,
            "default_ram_mb": 4096,
            "default_disk_gb": 40,
            "tags": ["linux", "server", "ubuntu"],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Ubuntu Server"
    assert data["os_type"] == "linux"
    assert "id" in data


def test_list_templates(client, auth_headers):
    # Create a template first
    client.post(
        "/api/v1/templates",
        headers=auth_headers,
        json={
            "name": "Test Template",
            "os_type": "linux",
            "os_variant": "Ubuntu 22.04",
            "base_image": "ubuntu:22.04",
        },
    )

    response = client.get("/api/v1/templates", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_get_template(client, auth_headers):
    # Create a template
    create_response = client.post(
        "/api/v1/templates",
        headers=auth_headers,
        json={
            "name": "Test Template",
            "os_type": "linux",
            "os_variant": "Ubuntu 22.04",
            "base_image": "ubuntu:22.04",
        },
    )
    template_id = create_response.json()["id"]

    response = client.get(f"/api/v1/templates/{template_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == template_id


def test_update_template(client, auth_headers):
    # Create a template
    create_response = client.post(
        "/api/v1/templates",
        headers=auth_headers,
        json={
            "name": "Test Template",
            "os_type": "linux",
            "os_variant": "Ubuntu 22.04",
            "base_image": "ubuntu:22.04",
        },
    )
    template_id = create_response.json()["id"]

    # Update it
    response = client.put(
        f"/api/v1/templates/{template_id}",
        headers=auth_headers,
        json={"name": "Updated Template", "default_cpu": 4},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Template"
    assert response.json()["default_cpu"] == 4


def test_delete_template(client, auth_headers):
    # Create a template
    create_response = client.post(
        "/api/v1/templates",
        headers=auth_headers,
        json={
            "name": "Test Template",
            "os_type": "linux",
            "os_variant": "Ubuntu 22.04",
            "base_image": "ubuntu:22.04",
        },
    )
    template_id = create_response.json()["id"]

    # Delete it
    response = client.delete(f"/api/v1/templates/{template_id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify it's gone
    get_response = client.get(f"/api/v1/templates/{template_id}", headers=auth_headers)
    assert get_response.status_code == 404


def test_clone_template(client, auth_headers):
    # Create a template
    create_response = client.post(
        "/api/v1/templates",
        headers=auth_headers,
        json={
            "name": "Original Template",
            "os_type": "windows",
            "os_variant": "Windows Server 2022",
            "base_image": "dockurr/windows:server2022",
            "tags": ["windows", "server"],
        },
    )
    template_id = create_response.json()["id"]

    # Clone it
    response = client.post(f"/api/v1/templates/{template_id}/clone", headers=auth_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Original Template (Copy)"
    assert data["id"] != template_id
    assert data["tags"] == ["windows", "server"]
```

**Step 6: Run template tests**

Run: `cd /home/ubuntu/cyro/backend && python -m pytest tests/integration/test_templates.py -v`
Expected: All tests pass

**Step 7: Commit VM template API**

```bash
git add -A
git commit -m "feat: implement VM template API

- Add VMTemplate schemas (create, update, response)
- Add CRUD endpoints for templates
- Add template cloning endpoint
- Add integration tests for all template operations

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## [CONTINUED IN NEXT TASKS...]

The implementation plan continues with:

### Remaining Phase 1 Tasks:
- Task 5: Range API (CRUD, deploy, teardown)
- Task 6: Network API
- Task 7: VM API
- Task 8: Frontend Authentication UI
- Task 9: Frontend Dashboard
- Task 10: Frontend Template Library UI

### Phase 2 Tasks:
- Task 11: Docker Orchestration Service
- Task 12: VM Lifecycle Management
- Task 13: Multi-segment Networking
- Task 14: Visual Network Builder (React Flow)
- Task 15: WebSocket Console
- Task 16: Deployment Engine with Dramatiq

### Phase 3 Tasks:
- Task 17: Artifact Repository API
- Task 18: Artifact Upload/Download with MinIO
- Task 19: Artifact Placement System
- Task 20: Snapshot Management
- Task 21: Range Templates (save/clone/import)
- Task 22: E2E Tests with Playwright

---

**Note:** This plan is being delivered incrementally. The first 4 tasks provide a solid foundation. Continue with subsequent tasks once these are complete.
