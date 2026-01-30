# Multi-NIC Range Builder Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable users to configure multiple network interfaces per VM during range building, with auto-IP assignment.

**Architecture:** New `vm_networks` junction table stores VM-to-network relationships. API accepts array of network configs. Frontend provides multi-interface editor. Deployment attaches all interfaces before container start.

**Tech Stack:** SQLAlchemy 2.0, Alembic migrations, Pydantic schemas, FastAPI, React/TypeScript, Tailwind CSS

---

## Task 1: Create VMNetwork Model

**Files:**
- Create: `backend/cyroid/models/vm_network.py`
- Modify: `backend/cyroid/models/__init__.py`
- Modify: `backend/cyroid/models/vm.py`

**Step 1: Create the VMNetwork model file**

```python
# backend/cyroid/models/vm_network.py
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID
from sqlalchemy import String, ForeignKey, Boolean, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from cyroid.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from cyroid.models.vm import VM
    from cyroid.models.network import Network


class VMNetwork(Base, UUIDMixin):
    """Junction table for VM-to-Network many-to-many relationship.

    Each row represents a network interface on a VM, with its IP address
    in that network's subnet. One interface per VM is marked as primary.
    """
    __tablename__ = "vm_networks"

    vm_id: Mapped[UUID] = mapped_column(
        ForeignKey("vms.id", ondelete="CASCADE"),
        nullable=False
    )
    network_id: Mapped[UUID] = mapped_column(
        ForeignKey("networks.id", ondelete="CASCADE"),
        nullable=False
    )
    ip_address: Mapped[str] = mapped_column(String(15), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    vm: Mapped["VM"] = relationship("VM", back_populates="network_interfaces")
    network: Mapped["Network"] = relationship("Network", back_populates="vm_interfaces")

    __table_args__ = (
        # VM can only connect to a network once
        UniqueConstraint('vm_id', 'network_id', name='uq_vm_network'),
        # No duplicate IPs in the same network
        UniqueConstraint('network_id', 'ip_address', name='uq_network_ip'),
    )
```

**Step 2: Update VM model to add relationship**

In `backend/cyroid/models/vm.py`, add at the top with other imports:
```python
if TYPE_CHECKING:
    from cyroid.models.vm_network import VMNetwork
```

Add after line 151 (after `incoming_connections` relationship):
```python
    # Multi-NIC support: all network interfaces for this VM
    network_interfaces: Mapped[List["VMNetwork"]] = relationship(
        "VMNetwork", back_populates="vm", cascade="all, delete-orphan"
    )
```

**Step 3: Update Network model to add relationship**

In `backend/cyroid/models/network.py`, add the TYPE_CHECKING import and relationship.

**Step 4: Update models/__init__.py**

Add to imports:
```python
from cyroid.models.vm_network import VMNetwork
```

Add to `__all__`:
```python
"VMNetwork",
```

**Step 5: Commit**

```bash
git add backend/cyroid/models/vm_network.py backend/cyroid/models/vm.py backend/cyroid/models/network.py backend/cyroid/models/__init__.py
git commit -m "feat: add VMNetwork junction table model for multi-NIC support"
```

---

## Task 2: Create Database Migration

**Files:**
- Create: `backend/alembic/versions/xxxx_add_vm_networks_table.py`

**Step 1: Generate migration**

```bash
cd /Users/steven/programming/CYROID/.worktrees/multi-nic-range-builder/backend
alembic revision --autogenerate -m "add vm_networks table for multi-NIC support"
```

**Step 2: Edit migration to add data migration**

The auto-generated migration will create the table. Add data migration logic to copy existing VM network assignments:

```python
def upgrade() -> None:
    # Create vm_networks table (auto-generated)
    op.create_table('vm_networks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('vm_id', sa.UUID(), nullable=False),
        sa.Column('network_id', sa.UUID(), nullable=False),
        sa.Column('ip_address', sa.String(15), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['vm_id'], ['vms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['network_id'], ['networks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('vm_id', 'network_id', name='uq_vm_network'),
        sa.UniqueConstraint('network_id', 'ip_address', name='uq_network_ip')
    )

    # Migrate existing VM network assignments
    op.execute("""
        INSERT INTO vm_networks (id, vm_id, network_id, ip_address, is_primary, created_at)
        SELECT gen_random_uuid(), id, network_id, ip_address, true, created_at
        FROM vms
        WHERE network_id IS NOT NULL AND ip_address IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_table('vm_networks')
```

**Step 3: Apply migration locally (test)**

```bash
alembic upgrade head
```

**Step 4: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat: add migration for vm_networks table with data migration"
```

---

## Task 3: Update Pydantic Schemas

**Files:**
- Modify: `backend/cyroid/schemas/vm.py`

**Step 1: Add NetworkInterface schema**

Add after the imports, before VMBase:

```python
class NetworkInterfaceCreate(BaseModel):
    """Schema for specifying a network interface during VM creation."""
    network_id: UUID
    ip_address: Optional[str] = Field(
        None,
        pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",
        description="IP address in the network's subnet. Auto-assigned if not provided."
    )


class NetworkInterfaceResponse(BaseModel):
    """Schema for network interface in API responses."""
    network_id: UUID
    network_name: str
    ip_address: str
    subnet: str
    is_primary: bool

    class Config:
        from_attributes = True
```

**Step 2: Update VMCreate to accept networks array**

Replace `network_id` field with `networks` array. Keep `network_id` for backwards compatibility:

```python
class VMCreate(BaseModel):
    """Schema for creating a new VM."""
    hostname: str = Field(..., min_length=1, max_length=63)
    cpu: int = Field(ge=1, le=32, default=2)
    ram_mb: int = Field(ge=512, le=131072, default=4096)
    disk_gb: int = Field(ge=10, le=1000, default=40)
    position_x: int = Field(default=0)
    position_y: int = Field(default=0)

    range_id: UUID

    # NEW: Multiple network interfaces (first is primary)
    networks: Optional[List[NetworkInterfaceCreate]] = Field(
        None,
        description="Network interfaces for the VM. First interface is primary. At least one required."
    )

    # DEPRECATED: Single network (kept for backwards compatibility)
    network_id: Optional[UUID] = Field(None, description="Deprecated: Use 'networks' array instead")
    ip_address: Optional[str] = Field(None, pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")

    # ... rest of fields unchanged ...

    @model_validator(mode='after')
    def normalize_networks(self) -> 'VMCreate':
        """Convert legacy network_id to networks array if provided."""
        if self.networks is None and self.network_id is not None:
            # Legacy format: convert to new format
            self.networks = [NetworkInterfaceCreate(
                network_id=self.network_id,
                ip_address=self.ip_address
            )]
        elif self.networks is None:
            raise ValueError("At least one network interface is required (provide 'networks' array)")
        elif len(self.networks) == 0:
            raise ValueError("At least one network interface is required")

        # Validate no duplicate networks
        network_ids = [n.network_id for n in self.networks]
        if len(network_ids) != len(set(network_ids)):
            raise ValueError("Cannot connect to the same network multiple times")

        return self
```

**Step 3: Update VMResponse to include networks array**

Add after existing fields:

```python
class VMResponse(VMBase):
    # ... existing fields ...

    # Multi-NIC: All network interfaces
    networks: List[NetworkInterfaceResponse] = Field(default_factory=list)

    # Deprecated but kept for compatibility (primary network)
    network_id: UUID
    ip_address: str
```

**Step 4: Commit**

```bash
git add backend/cyroid/schemas/vm.py
git commit -m "feat: update VM schemas for multi-NIC support with backwards compatibility"
```

---

## Task 4: Update VM API Endpoints

**Files:**
- Modify: `backend/cyroid/api/vms.py`

**Step 1: Update get_next_available_ip to use vm_networks table**

Find the existing function and update to query VMNetwork table:

```python
def get_next_available_ip(network: Network, db: Session, exclude_ips: set[str] = None) -> Optional[str]:
    """Get the next available IP address in a network's subnet."""
    import ipaddress

    # Get all used IPs from vm_networks table
    used_query = db.query(VMNetwork.ip_address).filter(VMNetwork.network_id == network.id)
    used_ips = {row[0] for row in used_query.all()}

    # Also exclude any IPs passed in (for batch allocation)
    if exclude_ips:
        used_ips.update(exclude_ips)

    # Reserve gateway
    used_ips.add(network.gateway)

    # Find next available starting from .10
    try:
        subnet = ipaddress.ip_network(network.subnet, strict=False)
        for host in subnet.hosts():
            ip_str = str(host)
            # Skip first 9 addresses (reserved for infrastructure)
            if int(ip_str.split('.')[-1]) < 10:
                continue
            if ip_str not in used_ips:
                return ip_str
    except ValueError:
        pass

    return None
```

**Step 2: Update create_vm endpoint**

Update the VM creation logic to:
1. Auto-assign IPs for each network interface
2. Create VMNetwork records for each interface
3. Set first interface as primary
4. Keep legacy fields populated for compatibility

```python
@router.post("", response_model=VMResponse, status_code=status.HTTP_201_CREATED)
async def create_vm(
    vm_create: VMCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # ... existing validation ...

    # Auto-assign IPs for each network interface
    allocated_ips: dict[UUID, set[str]] = {}  # Track IPs per network
    processed_networks = []

    for i, net_config in enumerate(vm_create.networks):
        network = db.query(Network).filter(Network.id == net_config.network_id).first()
        if not network:
            raise HTTPException(404, f"Network {net_config.network_id} not found")
        if network.range_id != vm_create.range_id:
            raise HTTPException(400, f"Network {net_config.network_id} does not belong to this range")

        # Get or auto-assign IP
        if net_config.ip_address:
            ip = net_config.ip_address
            # Validate IP is available
            existing = db.query(VMNetwork).filter(
                VMNetwork.network_id == network.id,
                VMNetwork.ip_address == ip
            ).first()
            if existing:
                raise HTTPException(400, f"IP {ip} is already in use in network {network.name}")
        else:
            # Auto-assign
            exclude = allocated_ips.get(network.id, set())
            ip = get_next_available_ip(network, db, exclude)
            if not ip:
                raise HTTPException(400, f"No available IPs in network {network.name}")

        # Track allocation
        if network.id not in allocated_ips:
            allocated_ips[network.id] = set()
        allocated_ips[network.id].add(ip)

        processed_networks.append({
            'network': network,
            'ip_address': ip,
            'is_primary': (i == 0)
        })

    # Create VM with primary network info (for backwards compat)
    primary = processed_networks[0]
    vm = VM(
        range_id=vm_create.range_id,
        hostname=vm_create.hostname,
        network_id=primary['network'].id,  # Primary network (deprecated field)
        ip_address=primary['ip_address'],  # Primary IP (deprecated field)
        # ... other fields ...
    )
    db.add(vm)
    db.flush()  # Get VM ID

    # Create VMNetwork records for all interfaces
    for net_info in processed_networks:
        vm_network = VMNetwork(
            vm_id=vm.id,
            network_id=net_info['network'].id,
            ip_address=net_info['ip_address'],
            is_primary=net_info['is_primary']
        )
        db.add(vm_network)

    db.commit()
    db.refresh(vm)

    return vm
```

**Step 3: Update get_vm to include networks in response**

Add helper function and update response building:

```python
def build_vm_response(vm: VM, db: Session) -> VMResponse:
    """Build VMResponse with network interfaces."""
    # Get all network interfaces
    interfaces = db.query(VMNetwork).filter(VMNetwork.vm_id == vm.id).all()

    networks = []
    for iface in interfaces:
        network = db.query(Network).filter(Network.id == iface.network_id).first()
        if network:
            networks.append(NetworkInterfaceResponse(
                network_id=network.id,
                network_name=network.name,
                ip_address=iface.ip_address,
                subnet=network.subnet,
                is_primary=iface.is_primary
            ))

    return VMResponse(
        **vm.__dict__,
        networks=networks
    )
```

**Step 4: Update list_vms and get_vm endpoints to use helper**

**Step 5: Commit**

```bash
git add backend/cyroid/api/vms.py
git commit -m "feat: update VM API for multi-NIC creation with auto-IP assignment"
```

---

## Task 5: Update Deployment Service

**Files:**
- Modify: `backend/cyroid/services/range_deployment_service.py`

**Step 1: Update VM deployment to attach all networks**

Find the VM deployment section and update:

```python
async def deploy_vm(self, vm: VM, range_client: DockerClient, db: Session):
    """Deploy a VM with all its network interfaces."""
    from cyroid.models.vm_network import VMNetwork

    # Get all network interfaces
    interfaces = db.query(VMNetwork).filter(VMNetwork.vm_id == vm.id).order_by(
        VMNetwork.is_primary.desc()  # Primary first
    ).all()

    if not interfaces:
        # Fallback to legacy network_id
        primary_network = vm.network
        primary_ip = vm.ip_address
        secondary_interfaces = []
    else:
        primary_iface = interfaces[0]
        primary_network = db.query(Network).get(primary_iface.network_id)
        primary_ip = primary_iface.ip_address
        secondary_interfaces = interfaces[1:]

    # Create container with PRIMARY network
    container = await self.docker_service.create_range_container_dind(
        range_client=range_client,
        network_name=primary_network.name,
        ip_address=primary_ip,
        # ... other params ...
    )

    # Attach SECONDARY networks before starting
    for iface in secondary_interfaces:
        network = db.query(Network).get(iface.network_id)
        await self.docker_service.connect_container_to_network(
            container_id=container.id,
            network_name=network.name,
            ip_address=iface.ip_address
        )

    # Start container (now has all interfaces)
    container.start()

    return container
```

**Step 2: Commit**

```bash
git add backend/cyroid/services/range_deployment_service.py
git commit -m "feat: update deployment service to attach all VM networks before start"
```

---

## Task 6: Update Frontend API Types

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/services/api.ts`

**Step 1: Add NetworkInterface types**

In `frontend/src/types/index.ts`:

```typescript
export interface NetworkInterfaceCreate {
  network_id: string
  ip_address?: string | null
}

export interface NetworkInterfaceResponse {
  network_id: string
  network_name: string
  ip_address: string
  subnet: string
  is_primary: boolean
}

// Update VM type
export interface VM {
  // ... existing fields ...
  networks: NetworkInterfaceResponse[]
}

// Update VMCreate type
export interface VMCreate {
  hostname: string
  range_id: string
  networks: NetworkInterfaceCreate[]
  // ... other fields ...
  // Deprecated but kept for compatibility
  network_id?: string
  ip_address?: string
}
```

**Step 2: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/services/api.ts
git commit -m "feat: update frontend types for multi-NIC support"
```

---

## Task 7: Update Frontend Range Builder UI

**Files:**
- Modify: `frontend/src/pages/RangeDetail.tsx`

**Step 1: Update vmForm state to use networks array**

Replace single network_id with networks array:

```typescript
const [vmForm, setVmForm] = useState<Partial<VMCreate>>({
  hostname: '',
  networks: [{ network_id: '', ip_address: null }],  // Start with one interface
  // ... other fields ...
})
```

**Step 2: Create NetworkInterfaceEditor component**

Add inline or extract to separate file:

```typescript
interface NetworkInterfaceEditorProps {
  interfaces: { network_id: string; ip_address: string | null }[]
  onChange: (interfaces: { network_id: string; ip_address: string | null }[]) => void
  networks: Network[]
  rangeId: string
}

function NetworkInterfaceEditor({ interfaces, onChange, networks, rangeId }: NetworkInterfaceEditorProps) {
  const [availableIpsMap, setAvailableIpsMap] = useState<Record<string, string[]>>({})
  const [loadingIps, setLoadingIps] = useState<Record<string, boolean>>({})

  const fetchAvailableIps = async (networkId: string, index: number) => {
    if (!networkId) return
    setLoadingIps(prev => ({ ...prev, [index]: true }))
    try {
      const response = await vmsApi.getAvailableIps(networkId, 50)
      setAvailableIpsMap(prev => ({ ...prev, [networkId]: response.available_ips || [] }))
      // Auto-select first available IP
      if (response.available_ips?.length > 0) {
        const updated = [...interfaces]
        updated[index] = { ...updated[index], ip_address: response.available_ips[0] }
        onChange(updated)
      }
    } catch (err) {
      console.error('Failed to fetch IPs:', err)
    } finally {
      setLoadingIps(prev => ({ ...prev, [index]: false }))
    }
  }

  const handleNetworkChange = (index: number, networkId: string) => {
    const updated = [...interfaces]
    updated[index] = { network_id: networkId, ip_address: null }
    onChange(updated)
    fetchAvailableIps(networkId, index)
  }

  const handleIpChange = (index: number, ip: string) => {
    const updated = [...interfaces]
    updated[index] = { ...updated[index], ip_address: ip }
    onChange(updated)
  }

  const addInterface = () => {
    onChange([...interfaces, { network_id: '', ip_address: null }])
  }

  const removeInterface = (index: number) => {
    if (index === 0) return // Can't remove primary
    onChange(interfaces.filter((_, i) => i !== index))
  }

  // Get networks not already selected
  const getAvailableNetworks = (currentIndex: number) => {
    const usedNetworkIds = interfaces
      .filter((_, i) => i !== currentIndex)
      .map(iface => iface.network_id)
    return networks.filter(n => !usedNetworkIds.includes(n.id))
  }

  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium text-gray-700">Network Interfaces</label>

      {interfaces.map((iface, index) => (
        <div key={index} className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg">
          <span className="text-xs font-medium text-gray-500 w-16">
            {index === 0 ? 'Primary' : `NIC ${index + 1}`}
          </span>

          <select
            value={iface.network_id}
            onChange={(e) => handleNetworkChange(index, e.target.value)}
            className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
          >
            <option value="">Select network...</option>
            {getAvailableNetworks(index).map(network => (
              <option key={network.id} value={network.id}>
                {network.name} ({network.subnet})
              </option>
            ))}
          </select>

          <select
            value={iface.ip_address || ''}
            onChange={(e) => handleIpChange(index, e.target.value)}
            disabled={!iface.network_id || loadingIps[index]}
            className="w-40 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
          >
            <option value="">{loadingIps[index] ? 'Loading...' : 'Select IP...'}</option>
            {(availableIpsMap[iface.network_id] || []).map(ip => (
              <option key={ip} value={ip}>{ip}</option>
            ))}
          </select>

          {index > 0 && (
            <button
              type="button"
              onClick={() => removeInterface(index)}
              className="p-1 text-red-500 hover:text-red-700"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      ))}

      {interfaces.length < networks.length && (
        <button
          type="button"
          onClick={addInterface}
          className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800"
        >
          <Plus className="w-4 h-4" />
          Add Network Interface
        </button>
      )}
    </div>
  )
}
```

**Step 3: Replace single network dropdown with NetworkInterfaceEditor**

In the VM creation modal, replace the network dropdown with:

```tsx
<NetworkInterfaceEditor
  interfaces={vmForm.networks || [{ network_id: '', ip_address: null }]}
  onChange={(networks) => setVmForm(prev => ({ ...prev, networks }))}
  networks={networks}
  rangeId={id!}
/>
```

**Step 4: Update form submission**

Ensure the API call sends the networks array correctly.

**Step 5: Commit**

```bash
git add frontend/src/pages/RangeDetail.tsx
git commit -m "feat: add multi-NIC editor UI in range builder"
```

---

## Task 8: Integration Testing

**Files:**
- Manual testing via UI

**Step 1: Start the development environment**

```bash
cd /Users/steven/programming/CYROID/.worktrees/multi-nic-range-builder
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

**Step 2: Test VM creation with multiple networks**

1. Create a new range
2. Create two networks (e.g., "internal" 10.0.1.0/24, "dmz" 10.0.2.0/24)
3. Create a VM with both networks attached
4. Verify IP auto-assignment works for both
5. Deploy the range
6. Verify VM has both network interfaces in Docker

**Step 3: Test backwards compatibility**

1. Verify existing ranges still work
2. Test API with legacy `network_id` format

**Step 4: Commit any fixes**

---

## Task 9: Final Commit and PR

**Step 1: Verify all tests pass**

```bash
# Run any existing tests
cd backend && pytest
cd frontend && npm test
```

**Step 2: Create final commit with any remaining changes**

```bash
git add -A
git commit -m "feat: complete multi-NIC support for range builder (#172)"
```

**Step 3: Push and create PR**

```bash
git push -u origin feat/multi-nic-range-builder
gh pr create --title "feat: Multi-NIC support in range builder (#172)" --body "..."
```

---

## Summary

| Task | Description | Estimated Complexity |
|------|-------------|---------------------|
| 1 | Create VMNetwork model | Low |
| 2 | Database migration | Low |
| 3 | Update Pydantic schemas | Medium |
| 4 | Update VM API | Medium |
| 5 | Update deployment service | Medium |
| 6 | Update frontend types | Low |
| 7 | Frontend UI changes | High |
| 8 | Integration testing | Medium |
| 9 | Final PR | Low |
