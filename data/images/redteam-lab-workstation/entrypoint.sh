#!/bin/bash

# Configure network routing (VyOS router is gateway at .1)
configure_routing() {
    local ip=$(hostname -I | awk '{print $1}')
    if [ -n "$ip" ]; then
        local gateway=$(echo "$ip" | sed 's/\.[0-9]*$/.1/')
        if ! ip route show default | grep -q "via $gateway"; then
            ip route del default 2>/dev/null || true
            ip route add default via "$gateway" 2>/dev/null || true
        fi
    fi
}
configure_routing

# Start virtual display
export DISPLAY=:99
Xvfb :99 -screen 0 1024x768x24 &
sleep 2

# Wait for WordPress
echo "[*] Waiting for WordPress..."
until curl -s "${WORDPRESS_URL:-http://wordpress}" > /dev/null 2>&1; do
    sleep 5
done
echo "[*] WordPress is up!"

exec python3 /browse-script.py
