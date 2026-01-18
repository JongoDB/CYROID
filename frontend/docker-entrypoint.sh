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

if [ "$CURRENT_HASH" != "$STORED_HASH" ] || [ ! -d "/app/node_modules/react" ]; then
    echo "Package.json changed or node_modules incomplete - running npm install..."
    npm install
    echo "$CURRENT_HASH" > "$HASH_FILE"
else
    echo "Dependencies up to date"
fi

exec "$@"
