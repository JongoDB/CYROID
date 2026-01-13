#!/bin/bash
# CYROID Windows ISO Management Script
#
# This script helps you manage Windows ISOs for offline VM deployment.

set -e

ISO_CACHE_DIR="/var/lib/docker/volumes/cyro_cyroid_iso_cache/_data"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

show_help() {
    echo "CYROID Windows ISO Management"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  list              List all cached ISOs"
    echo "  add <file> <ver>  Add an ISO file to the cache"
    echo "  download <ver>    Download an ISO (limited options)"
    echo "  remove <ver>      Remove an ISO from the cache"
    echo "  info              Show cache directory info"
    echo ""
    echo "Versions:"
    echo "  win10             Windows 10"
    echo "  win11             Windows 11"
    echo "  win2019           Windows Server 2019"
    echo "  win2022           Windows Server 2022"
    echo "  tiny11            Tiny11 (lightweight Windows 11)"
    echo ""
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 add ~/Downloads/Win10.iso win10"
    echo "  $0 download tiny11"
    echo ""
    echo "Manual Download URLs:"
    echo "  Windows 10:     https://www.microsoft.com/software-download/windows10ISO"
    echo "  Windows 11:     https://www.microsoft.com/software-download/windows11"
    echo "  Windows Server: https://www.microsoft.com/evalcenter/"
}

ensure_cache_dir() {
    if [ ! -d "$ISO_CACHE_DIR" ]; then
        echo -e "${YELLOW}Creating ISO cache directory...${NC}"
        sudo mkdir -p "$ISO_CACHE_DIR"
        sudo chmod 755 "$ISO_CACHE_DIR"
    fi
}

list_isos() {
    echo -e "${GREEN}Cached Windows ISOs:${NC}"
    echo "Location: $ISO_CACHE_DIR"
    echo ""

    if [ -d "$ISO_CACHE_DIR" ]; then
        if ls "$ISO_CACHE_DIR"/*.iso 1> /dev/null 2>&1; then
            for iso in "$ISO_CACHE_DIR"/*.iso; do
                filename=$(basename "$iso")
                size=$(du -h "$iso" | cut -f1)
                echo "  - $filename ($size)"
            done
        else
            echo "  No ISOs found in cache."
        fi
    else
        echo "  Cache directory does not exist yet."
    fi
}

add_iso() {
    local source_file="$1"
    local version="$2"

    if [ -z "$source_file" ] || [ -z "$version" ]; then
        echo -e "${RED}Error: Please specify source file and version${NC}"
        echo "Usage: $0 add <file> <version>"
        exit 1
    fi

    if [ ! -f "$source_file" ]; then
        echo -e "${RED}Error: Source file not found: $source_file${NC}"
        exit 1
    fi

    ensure_cache_dir

    dest_file="$ISO_CACHE_DIR/windows-${version}.iso"

    echo -e "${YELLOW}Copying ISO to cache...${NC}"
    echo "Source: $source_file"
    echo "Destination: $dest_file"

    sudo cp "$source_file" "$dest_file"
    sudo chmod 644 "$dest_file"

    size=$(du -h "$dest_file" | cut -f1)
    echo -e "${GREEN}ISO cached successfully! ($size)${NC}"
}

download_iso() {
    local version="$1"

    case "$version" in
        "tiny11")
            url="https://archive.org/download/tiny-11-NTDEV/tiny11%20b2.iso"
            ;;
        *)
            echo -e "${RED}Auto-download not available for '$version'${NC}"
            echo ""
            echo "Please download manually from Microsoft:"
            echo "  Windows 10:     https://www.microsoft.com/software-download/windows10ISO"
            echo "  Windows 11:     https://www.microsoft.com/software-download/windows11"
            echo "  Windows Server: https://www.microsoft.com/evalcenter/"
            echo ""
            echo "Then run: $0 add <downloaded-file> $version"
            exit 1
            ;;
    esac

    ensure_cache_dir
    dest_file="$ISO_CACHE_DIR/windows-${version}.iso"

    if [ -f "$dest_file" ]; then
        echo -e "${YELLOW}ISO already exists: $dest_file${NC}"
        exit 0
    fi

    echo -e "${YELLOW}Downloading $version ISO...${NC}"
    echo "URL: $url"
    echo "Destination: $dest_file"
    echo ""
    echo "This may take a while depending on your connection speed..."

    sudo wget -O "$dest_file" "$url"
    sudo chmod 644 "$dest_file"

    size=$(du -h "$dest_file" | cut -f1)
    echo -e "${GREEN}ISO downloaded successfully! ($size)${NC}"
}

remove_iso() {
    local version="$1"

    if [ -z "$version" ]; then
        echo -e "${RED}Error: Please specify version to remove${NC}"
        exit 1
    fi

    iso_file="$ISO_CACHE_DIR/windows-${version}.iso"

    if [ ! -f "$iso_file" ]; then
        echo -e "${RED}ISO not found: $iso_file${NC}"
        exit 1
    fi

    echo -e "${YELLOW}Removing: $iso_file${NC}"
    sudo rm "$iso_file"
    echo -e "${GREEN}ISO removed successfully!${NC}"
}

show_info() {
    echo -e "${GREEN}ISO Cache Information:${NC}"
    echo "Cache Directory: $ISO_CACHE_DIR"
    echo ""

    if [ -d "$ISO_CACHE_DIR" ]; then
        total_size=$(du -sh "$ISO_CACHE_DIR" 2>/dev/null | cut -f1)
        echo "Total Cache Size: $total_size"
        echo ""

        # Show disk space
        df -h "$ISO_CACHE_DIR" | tail -1 | awk '{print "Disk Space Available: " $4 " / " $2}'
    else
        echo "Cache directory does not exist yet."
        echo "Run '$0 add' or '$0 download' to create it."
    fi
}

# Main command handler
case "${1:-help}" in
    list)
        list_isos
        ;;
    add)
        add_iso "$2" "$3"
        ;;
    download)
        download_iso "$2"
        ;;
    remove)
        remove_iso "$2"
        ;;
    info)
        show_info
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        show_help
        exit 1
        ;;
esac
