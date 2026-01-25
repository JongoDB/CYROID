# CYROID Docker Image Projects

This directory contains Dockerfile projects for building custom Docker images used in CYROID ranges.

## Directory Structure

Each subdirectory is a complete Docker build context:

```
images/
├── kali-attack/          # Kali Linux attack platform
├── samba-dc/             # Samba Active Directory Domain Controller
├── redteam-lab-wordpress/    # Vulnerable WordPress server
├── redteam-lab-fileserver/   # SMB file server with sensitive data
└── redteam-lab-workstation/  # Linux workstation with browsing simulation
```

## Usage

### Building Images Manually

```bash
cd <project-directory>
docker build -t cyroid/<project-name>:latest .
```

### Via CYROID Image Cache

1. Navigate to **Image Cache** in the CYROID UI
2. Click **Build** next to the project name
3. The image will be built and registered in the Image Library

### Via Blueprint Import

When importing a blueprint that includes Dockerfiles:
1. Dockerfiles are automatically extracted to `/data/images/`
2. Images are built automatically (if `build_images=true`)
3. BaseImage records are created with proper references

## Image Details

### kali-attack
- **Base**: kalilinux/kali-rolling
- **Purpose**: Red team attack platform
- **Features**: Pre-installed penetration testing tools, desktop environment

### samba-dc
- **Base**: Ubuntu
- **Purpose**: Active Directory Domain Controller
- **Features**: Samba AD DC, DNS, user provisioning

### redteam-lab-wordpress
- **Base**: WordPress official image
- **Purpose**: Vulnerable web application target
- **Features**: Custom vulnerable plugin, MySQL integration

### redteam-lab-fileserver
- **Base**: Alpine Linux
- **Purpose**: SMB file server with exfiltration targets
- **Features**: Samba shares, planted sensitive data files

### redteam-lab-workstation
- **Base**: Ubuntu with desktop
- **Purpose**: Simulated employee workstation
- **Features**: Automated browsing behavior, realistic user simulation

## Adding New Projects

1. Create a new directory: `images/<project-name>/`
2. Add a `Dockerfile` and any required files
3. Build via CYROID Image Cache or manually
4. The `image_project_name` field links built images back to this source

## Blueprint Export/Import

When exporting a blueprint:
- Dockerfiles from referenced images are included in the ZIP
- All files in the project directory are packaged

When importing:
- Dockerfiles are extracted to `/data/images/<project-name>/`
- Images are built automatically
- BaseImage records are created with `image_project_name` set
