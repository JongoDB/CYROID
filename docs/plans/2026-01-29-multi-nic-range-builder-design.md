# Multi-Network Interface Support in Range Builder

**Issue:** #172
**Date:** 2026-01-29
**Status:** Approved

## Overview

Enable users to configure multiple network interfaces per VM during the range building phase, rather than requiring them to add interfaces one-by-one after deployment via the Execution Console.

## Current State

- VMs have a single `network_id` and `ip_address` field
- Users can only attach one network during range build
- Multi-NIC is supported post-deployment via Execution Console
- IP auto-assignment works for single network only

## Design

### 1. Database Schema

#### New Junction Table: `vm_networks`

```python
# backend/cyroid/models/vm_network.py
class VMNetwork(Base):
    __tablename__ = "vm_networks"

    id: UUID = primary_key
    vm_id: UUID = FK("vms.id", ondelete="CASCADE")
    network_id: UUID = FK("networks.id", ondelete="CASCADE")
    ip_address: str  # IP in this network's subnet
    is_primary: bool = False  # Only one per VM
    created_at: datetime

    # Relationships
    vm = relationship("VM", back_populates="network_interfaces")
    network = relationship("Network", back_populates="vm_interfaces")

    # Constraints
    __table_args__ = (
        UniqueConstraint('vm_id', 'network_id'),  # VM connects to network once
        UniqueConstraint('network_id', 'ip_address'),  # No duplicate IPs
    )
```

#### Migration Strategy

1. Create `vm_networks` table
2. Migrate existing data: For each VM, insert row with `vm.network_id`, `vm.ip_address`, `is_primary=True`
3. Keep `VM.network_id` and `VM.ip_address` columns (deprecated but functional)
4. Update all code to read/write through `vm_networks`

### 2. API Schema Changes

#### NetworkInterface Schema

```python
class NetworkInterface(BaseModel):
    network_id: UUID
    ip_address: Optional[str] = None  # Auto-assign if null

class VMCreate(BaseModel):
    range_id: UUID
    hostname: str
    networks: List[NetworkInterface]  # First is primary
    # ... image source fields unchanged

    @validator('networks')
    def validate_networks(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one network interface required')
        return v
```

#### Backwards Compatibility

```python
# Support legacy single network_id format
if 'network_id' in payload and 'networks' not in payload:
    payload['networks'] = [{
        'network_id': payload['network_id'],
        'ip_address': payload.get('ip_address')
    }]
```

#### Response Schema

```python
class VMNetworkResponse(BaseModel):
    network_id: UUID
    network_name: str
    ip_address: str
    subnet: str
    is_primary: bool

class VMResponse(BaseModel):
    # ... existing fields ...
    networks: List[VMNetworkResponse]

    # Deprecated but included for compatibility
    network_id: UUID  # Primary network
    ip_address: str   # Primary IP
```

### 3. Frontend UI Changes

#### Multi-Interface Editor in Range Builder

```
┌─────────────────────────────────────────────────┐
│ VM: kali-attacker                               │
├─────────────────────────────────────────────────┤
│ Network Interfaces:                             │
│                                                 │
│ ┌─ Primary ─────────────────────────────────┐   │
│ │ Network: [internal ▼]  IP: [10.0.1.10 ▼]  │   │
│ └───────────────────────────────────────────┘   │
│                                                 │
│ ┌─ Secondary ───────────────────────────────┐   │
│ │ Network: [dmz ▼]       IP: [10.0.2.10 ▼] ✕│   │
│ └───────────────────────────────────────────┘   │
│                                                 │
│ [+ Add Network Interface]                       │
└─────────────────────────────────────────────────┘
```

#### Key Behaviors

1. First interface = Primary (cannot be removed)
2. Auto-IP: When network selected, populate next available IP
3. Validation: Prevent duplicate networks, validate IP in subnet
4. Network filtering: Only show networks in current range

### 4. Deployment Service Changes

```python
async def deploy_vm(vm: VM, range_client: DockerClient):
    # Get all interfaces
    interfaces = db.query(VMNetwork).filter(VMNetwork.vm_id == vm.id).all()
    primary = next(i for i in interfaces if i.is_primary)
    secondary = [i for i in interfaces if not i.is_primary]

    # Create container with primary network
    container = docker.create_range_container_dind(
        network_name=primary.network.name,
        ip_address=primary.ip_address,
        ...
    )

    # Attach secondary networks BEFORE starting
    for iface in secondary:
        docker.connect_container_to_network(
            container_id=container.id,
            network_name=iface.network.name,
            ip_address=iface.ip_address
        )

    # Start container with all interfaces ready
    container.start()
```

### 5. IP Allocation

Update `get_next_available_ip()` to query `vm_networks` table:

```python
def get_next_available_ip(network_id: UUID, db: Session) -> Optional[str]:
    network = db.query(Network).get(network_id)

    # Get all used IPs from vm_networks table
    used_ips = db.query(VMNetwork.ip_address).filter(
        VMNetwork.network_id == network_id
    ).all()
    used_set = {ip[0] for ip in used_ips}
    used_set.add(network.gateway)

    # Find next available starting from .10
    for host in ipaddress.ip_network(network.subnet).hosts():
        if str(host) not in used_set and int(str(host).split('.')[-1]) >= 10:
            return str(host)

    return None
```

## Implementation Plan

### Files to Modify

| Layer | File | Changes |
|-------|------|---------|
| Model | `backend/cyroid/models/vm_network.py` | New junction table |
| Model | `backend/cyroid/models/vm.py` | Add relationship |
| Model | `backend/cyroid/models/__init__.py` | Export VMNetwork |
| Migration | `alembic/versions/xxx_add_vm_networks.py` | Create + migrate |
| Schema | `backend/cyroid/schemas/vm.py` | NetworkInterface, VMCreate, VMResponse |
| API | `backend/cyroid/api/vms.py` | Create/get endpoints, IP allocation |
| Service | `backend/cyroid/services/range_deployment_service.py` | Multi-NIC deploy |
| Frontend | `frontend/src/pages/RangeDetail.tsx` | Multi-interface editor |
| Frontend | `frontend/src/services/api.ts` | Update VM payload |

### Implementation Order

1. **Database layer** - Model + migration with data migration
2. **Backend schemas** - NetworkInterface, updated VMCreate/VMResponse
3. **Backend API** - Update VM creation, IP allocation
4. **Deployment service** - Multi-NIC container creation
5. **Frontend** - Multi-interface editor UI
6. **Testing** - E2E validation

### Acceptance Criteria

- [ ] User can add 2+ network interfaces per VM during range build
- [ ] IPs auto-default to next available in subnet
- [ ] Visual feedback shows allocated IPs per network
- [ ] Validation prevents duplicate IP assignments
- [ ] Existing single-NIC ranges continue to work
- [ ] Post-deployment NIC management still works

## Risk Mitigation

- **Backwards compatibility**: Deprecated fields remain functional
- **Data migration**: Existing VMs get interface record automatically
- **Rollback**: Migration is reversible
