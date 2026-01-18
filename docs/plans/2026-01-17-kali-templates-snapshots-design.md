# CYROID Infrastructure Enhancement Design

> **Covers:** Issue #28 (Kali Attack Box), Issue #29 (Domain Controllers), Template Repository, Snapshot UI

**Goal:** Ship CYROID with production-ready attack boxes, domain controllers, and an intuitive snapshot workflow.

**Architecture:** Three interconnected features: (1) Custom Docker images built from Kali/Samba, (2) Template seeding system that ships pre-configured templates with CYROID, (3) Enhanced snapshot UI allowing users to save customized VMs directly from the range view.

**Tech Stack:** Docker multi-stage builds, Alembic seed migrations, React components

---

## 1. CYROID Kali Docker Image

### Approach

Build a custom `cyroid/kali-attack:latest` image based on `kasmweb/core-kali-rolling` with all offensive security tools pre-installed. This image ships with CYROID and is referenced by a built-in template.

### Tools to Install (from Issue #28)

**Network Recon & Scanning:**
- nmap, masscan, rustscan
- enum4linux, enum4linux-ng, ldapsearch
- dnsrecon, dnsenum, fierce

**Exploitation Frameworks:**
- metasploit-framework
- searchsploit (exploitdb)

**Active Directory Tools:**
- impacket (full suite: secretsdump, psexec, wmiexec, etc.)
- crackmapexec (cme)
- evil-winrm
- bloodhound, bloodhound.py
- kerbrute
- rubeus (if available as package)

**Password Attacks:**
- hashcat, john
- hydra, medusa
- responder, ntlmrelayx

**Wordlists:**
- rockyou.txt (at /usr/share/wordlists/rockyou.txt)
- seclists

**Tunneling & Pivoting:**
- chisel
- ligolo-ng
- proxychains4, socat

**Post-Exploitation:**
- linpeas, winpeas (download scripts)
- mimikatz (Windows payloads)
- empire, sliver (optional C2)

**Web Application Testing:**
- burpsuite
- nikto, gobuster, feroxbuster, ffuf
- sqlmap
- wfuzz

### Dockerfile Structure

```dockerfile
# cyroid/images/kali-attack/Dockerfile
FROM kasmweb/core-kali-rolling:1.15.0

LABEL maintainer="CYROID"
LABEL description="CYROID Kali Attack Box with full offensive toolkit"

USER root

# Install core tool packages from Kali repos
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Recon
    nmap masscan rustscan enum4linux dnsrecon dnsenum fierce \
    # Exploitation
    metasploit-framework exploitdb \
    # AD Tools
    crackmapexec evil-winrm bloodhound impacket-scripts python3-impacket \
    # Password cracking
    hashcat john hydra medusa responder \
    # Wordlists
    wordlists seclists \
    # Tunneling
    chisel proxychains4 socat \
    # Web testing
    nikto gobuster feroxbuster ffuf sqlmap wfuzz \
    # Utilities
    curl wget git vim tmux \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Download additional tools not in repos
WORKDIR /opt/tools

# Kerbrute
RUN wget -q https://github.com/ropnop/kerbrute/releases/latest/download/kerbrute_linux_amd64 -O /usr/local/bin/kerbrute \
    && chmod +x /usr/local/bin/kerbrute

# Ligolo-ng
RUN LIGOLO_VERSION=$(curl -s https://api.github.com/repos/nicocha30/ligolo-ng/releases/latest | grep tag_name | cut -d'"' -f4) \
    && wget -q "https://github.com/nicocha30/ligolo-ng/releases/download/${LIGOLO_VERSION}/ligolo-ng_agent_${LIGOLO_VERSION#v}_linux_amd64.tar.gz" -O /tmp/ligolo-agent.tar.gz \
    && tar -xzf /tmp/ligolo-agent.tar.gz -C /usr/local/bin/ \
    && rm /tmp/ligolo-agent.tar.gz

# PEAS scripts
RUN mkdir -p /opt/tools/peas \
    && wget -q https://github.com/carlospolop/PEASS-ng/releases/latest/download/linpeas.sh -O /opt/tools/peas/linpeas.sh \
    && wget -q https://github.com/carlospolop/PEASS-ng/releases/latest/download/winPEASx64.exe -O /opt/tools/peas/winpeas.exe \
    && chmod +x /opt/tools/peas/linpeas.sh

# Bloodhound.py
RUN pip3 install --break-system-packages bloodhound

# Ensure rockyou is decompressed
RUN gunzip /usr/share/wordlists/rockyou.txt.gz 2>/dev/null || true

# Set environment
ENV PATH="/opt/tools:${PATH}"
WORKDIR /home/kasm-user

USER 1000
```

### Build Location

```
cyroid/
├── images/
│   ├── kali-attack/
│   │   ├── Dockerfile
│   │   └── README.md
│   └── samba-dc/
│       ├── Dockerfile
│       └── README.md
```

---

## 2. Samba AD DC for ARM (Issue #29)

For ARM64 hosts, Windows Server isn't available via dockur/windows. Use Samba AD DC instead.

### Dockerfile

```dockerfile
# cyroid/images/samba-dc/Dockerfile
FROM ubuntu:22.04

LABEL maintainer="CYROID"
LABEL description="Samba Active Directory Domain Controller"

ENV DEBIAN_FRONTEND=noninteractive
ENV SAMBA_DOMAIN=CYROID
ENV SAMBA_REALM=CYROID.LOCAL
ENV SAMBA_ADMIN_PASS=CyroidAdmin123!

RUN apt-get update && apt-get install -y \
    samba krb5-config krb5-user winbind smbclient \
    dnsutils ldap-utils acl attr \
    supervisor \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
COPY supervisord.conf /etc/supervisor/conf.d/samba.conf

RUN chmod +x /entrypoint.sh

EXPOSE 53 88 135 139 389 445 464 636 3268 3269

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/samba.conf"]
```

### entrypoint.sh

```bash
#!/bin/bash
# Provision DC if not already done
if [ ! -f /var/lib/samba/private/secrets.keytab ]; then
    samba-tool domain provision \
        --use-rfc2307 \
        --realm="${SAMBA_REALM}" \
        --domain="${SAMBA_DOMAIN}" \
        --server-role=dc \
        --dns-backend=SAMBA_INTERNAL \
        --adminpass="${SAMBA_ADMIN_PASS}"
fi
exec "$@"
```

---

## 3. Template Seeding System

### Design

Templates ship with CYROID in a `data/seed-templates/` directory. On first boot (or migration), templates are inserted into the database if they don't already exist.

### Seed Data Location

```
cyroid/
├── data/
│   └── seed-templates/
│       ├── manifest.yaml          # List of all seed templates
│       ├── kali-attack.yaml
│       ├── samba-dc.yaml
│       ├── windows-dc-2022.yaml
│       └── ubuntu-desktop.yaml
```

### manifest.yaml Format

```yaml
version: 1
templates:
  - name: "Kali Attack Box"
    slug: kali-attack
    file: kali-attack.yaml
    category: offensive

  - name: "Samba AD DC (ARM)"
    slug: samba-dc
    file: samba-dc.yaml
    category: infrastructure
    arch: arm64

  - name: "Windows Server 2022 DC"
    slug: windows-dc-2022
    file: windows-dc-2022.yaml
    category: infrastructure
    arch: x86_64
```

### Individual Template YAML

```yaml
# kali-attack.yaml
name: "Kali Attack Box"
description: "Full offensive security toolkit with KasmVNC desktop access"
os_type: linux
os_variant: kali
base_image: cyroid/kali-attack:latest
default_cpu: 2
default_ram_mb: 4096
default_disk_gb: 40
tags:
  - offensive
  - pentest
  - kali
is_seed: true
config:
  display: vnc
  vnc_port: 6901
```

### Seeding Implementation

Add an Alembic data migration that:
1. Reads manifest.yaml
2. Checks if template with `is_seed=True` and matching `name` exists
3. Inserts or updates the template

```python
# alembic/versions/xxxx_seed_builtin_templates.py
def upgrade():
    from cyroid.services.template_seeder import seed_builtin_templates
    seed_builtin_templates()

def downgrade():
    # Don't delete seed templates on downgrade - user may have customized them
    pass
```

### Template Model Addition

Add `is_seed` boolean field to Template model to distinguish built-in vs user-created templates.

---

## 4. Snapshot UI Enhancement

### Current State

- Backend: Complete (create, list, restore, delete)
- ImageCache page: Shows snapshots, can delete
- Missing: **Create snapshot from VM context**

### Solution

Add "Create Snapshot" button to VM actions in RangeDetail page. When clicked, opens a modal to name the snapshot.

### UI Flow

1. User clicks VM in range topology or VM list
2. VM action bar shows: Start | Stop | Restart | Console | **Snapshot**
3. Click "Snapshot" → Modal: "Create Snapshot"
   - Name field (auto-suggested: `{hostname}-{date}`)
   - Description field (optional)
   - Create button
4. On success: Toast notification with link to Snapshots tab

### Component: CreateSnapshotModal

```tsx
interface Props {
  vmId: string
  hostname: string
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

function CreateSnapshotModal({ vmId, hostname, isOpen, onClose, onSuccess }: Props) {
  const [name, setName] = useState(`${hostname}-${new Date().toISOString().split('T')[0]}`)
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(false)

  const handleCreate = async () => {
    setLoading(true)
    try {
      await snapshotsApi.create({ vm_id: vmId, name, description })
      toast.success('Snapshot created')
      onSuccess()
      onClose()
    } catch (e) {
      toast.error('Failed to create snapshot')
    } finally {
      setLoading(false)
    }
  }

  // Modal JSX...
}
```

### API Addition

Add `snapshotsApi` to frontend api.ts:

```typescript
export const snapshotsApi = {
  create: (data: { vm_id: string; name: string; description?: string }) =>
    api.post<SnapshotResponse>('/snapshots', data),
  list: (vmId?: string) =>
    api.get<SnapshotResponse[]>('/snapshots', { params: vmId ? { vm_id: vmId } : {} }),
  restore: (id: string) =>
    api.post<SnapshotResponse>(`/snapshots/${id}/restore`),
  delete: (id: string) =>
    api.delete(`/snapshots/${id}`),
}
```

---

## 5. Implementation Order

### Phase 1: Foundation (Can be parallel)

1. **Create Kali Attack Dockerfile** - `images/kali-attack/Dockerfile`
2. **Create Samba DC Dockerfile** - `images/samba-dc/Dockerfile`
3. **Add `is_seed` field to Template model** - Migration

### Phase 2: Template Seeding

4. **Create seed template YAML files** - `data/seed-templates/*.yaml`
5. **Implement template seeder service** - `services/template_seeder.py`
6. **Add seeder data migration** - Alembic

### Phase 3: Snapshot UI

7. **Add snapshotsApi to frontend** - `services/api.ts`
8. **Create CreateSnapshotModal component** - `components/range/CreateSnapshotModal.tsx`
9. **Add Snapshot button to VM actions** - `pages/RangeDetail.tsx`

### Phase 4: Testing & Integration

10. **Build and test Kali image locally**
11. **Build and test Samba DC image locally**
12. **Add templates to seed data**
13. **Test full workflow**: Create range → Add Kali VM → Start → Configure → Snapshot → Restore

---

## 6. Windows DC Template (x86_64)

For x86_64 hosts, use dockur/windows with Windows Server 2022:

```yaml
# windows-dc-2022.yaml
name: "Windows Server 2022 DC"
description: "Windows Server 2022 configured as Active Directory Domain Controller"
os_type: windows
os_variant: "Windows Server 2022"
base_image: dockurr/windows:latest
default_cpu: 4
default_ram_mb: 8192
default_disk_gb: 80
tags:
  - infrastructure
  - active-directory
  - domain-controller
is_seed: true
config:
  windows_version: "2022"
  display: vnc
notes: |
  After deployment:
  1. Install AD DS role via Server Manager
  2. Promote to Domain Controller
  3. Create golden image snapshot
```

---

## 7. File Structure After Implementation

```
cyroid/
├── backend/
│   └── cyroid/
│       ├── models/
│       │   └── template.py  (add is_seed field)
│       └── services/
│           └── template_seeder.py  (new)
├── data/
│   └── seed-templates/
│       ├── manifest.yaml
│       ├── kali-attack.yaml
│       ├── samba-dc.yaml
│       ├── windows-dc-2022.yaml
│       └── ubuntu-desktop.yaml
├── images/
│   ├── kali-attack/
│   │   ├── Dockerfile
│   │   └── README.md
│   └── samba-dc/
│       ├── Dockerfile
│       ├── entrypoint.sh
│       ├── supervisord.conf
│       └── README.md
└── frontend/
    └── src/
        ├── services/
        │   └── api.ts  (add snapshotsApi)
        └── components/
            └── range/
                └── CreateSnapshotModal.tsx  (new)
```

---

## 8. Version & Changelog

This feature set will be released as **v0.7.0** with:

- Custom Kali Attack Box image with full toolkit
- Samba AD DC for ARM support
- Built-in template seeding system
- Enhanced snapshot UI with create-from-VM capability
