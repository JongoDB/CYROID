#!/bin/sh
# Ensure node_modules are in sync with package.json
# This handles the case where a persistent volume has stale dependencies

HASH_FILE="/app/node_modules/.package-json-hash"
CURRENT_HASH=$(md5sum /app/package.json | cut -d' ' -f1)

if [ -f "$HASH_FILE" ]; then
    STORED_HASH=$(cat "$HASH_FILE")
else
    STORED_HASH=""
fi

# Check for platform-specific rollup module (detects cross-platform issues)
ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    ROLLUP_MODULE="/app/node_modules/@rollup/rollup-linux-arm64-musl"
else
    ROLLUP_MODULE="/app/node_modules/@rollup/rollup-linux-x64-musl"
fi

if [ "$CURRENT_HASH" != "$STORED_HASH" ] || [ ! -d "/app/node_modules/react" ] || [ ! -d "$ROLLUP_MODULE" ]; then
    echo "Package.json changed or dependencies incomplete - reinstalling..."
    # Remove potentially corrupted/cross-platform deps
    rm -rf /app/node_modules /app/package-lock.json
    npm install
    echo "$CURRENT_HASH" > "$HASH_FILE"
else
    echo "Dependencies up to date"
fi

exec "$@"
