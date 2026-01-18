# NetworkPropertiesPanel Enhancement Design

> Enhance VM editing in Range Wizard's Network step to match RangeDetail capabilities.

**Goal:** Users can configure OS-specific VM settings (credentials, network, storage, locale) directly in the Network topology step via collapsible sections.

**Architecture:**
- Services step stays simple (template selection only)
- NetworkPropertiesPanel gets full VM editing with collapsible sections
- VMPlacement interface extended with OS-specific optional fields
- Deploy handler passes new fields to backend API

---

## Data Model

Extended `VMPlacement` interface:

```typescript
interface VMPlacement {
  // Existing
  id, hostname, templateId, templateName, networkId, ip, cpu, ramMb, diskGb, position

  // Credentials (all OS types)
  username?: string;
  password?: string;
  sudoEnabled?: boolean;

  // Network (Windows & Linux ISO)
  useDhcp?: boolean;
  gateway?: string;
  dnsServers?: string;

  // Storage (Windows & Linux ISO)
  disk2Gb?: number;
  disk3Gb?: number;

  // Shared folders (all OS types)
  enableSharedFolder?: boolean;
  enableGlobalShared?: boolean;

  // Display (Windows & Linux ISO)
  displayType?: 'desktop' | 'server';

  // Locale (Windows & Linux ISO)
  language?: string;
  keyboard?: string;
  region?: string;
}
```

## UI Design

NetworkPropertiesPanel collapsible sections:
1. **Basic** (always visible): Hostname, IP, CPU, RAM, Disk
2. **Credentials** (collapsed): Username, Password, Sudo toggle
3. **Network** (collapsed, Windows/Linux ISO only): DHCP, Gateway, DNS
4. **Storage** (collapsed, Windows/Linux ISO only): Disk 2, Disk 3
5. **Advanced** (collapsed, Windows/Linux ISO only): Display type, Locale settings, Shared folders

## Files Changed

1. `frontend/src/stores/wizardStore.ts` - Extend VMPlacement
2. `frontend/src/components/wizard-v2/panels/NetworkPropertiesPanel.tsx` - Add sections
3. `frontend/src/pages/RangeWizardPage.tsx` - Pass fields to API

## OS Detection Logic

```typescript
const isWindows = template?.os_type === 'windows';
const isLinuxISO = template?.os_type === 'linux' && template?.base_image?.startsWith('iso:');
const isContainer = !isWindows && !isLinuxISO;
```
