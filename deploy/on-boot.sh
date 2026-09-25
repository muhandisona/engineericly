#!/bin/sh
# Re-publish the web port after a reboot.
#
#   crontab: @reboot /path/to/engineericly/deploy/on-boot.sh >> ~/backups/engineericly/on-boot.log 2>&1
#
# The port is published on one address (BIND_ADDRESS in .env, the VM's LAN address) so it
# stays off other interfaces. At boot Docker restarts the container before DHCP has given
# the VM that address, cannot publish on it, and starts the container with no port at
# all - the site is down until someone recreates it. This waits for the address, then
# recreates the container only if its port is missing, so it does nothing on a healthy
# boot. A root fix is net.ipv4.ip_nonlocal_bind=1 or making Docker wait for the address
# (both need sudo); this needs neither.
set -eu
cd "$(dirname "$0")/.."
env_value() { sed -n "s/^$1=//p" .env | tail -n 1; }
BIND="$(env_value BIND_ADDRESS)"; BIND="${BIND:-127.0.0.1}"
PORT="$(env_value PORT)"; PORT="${PORT:-9192}"
if [ "$BIND" != "0.0.0.0" ]; then
    echo "$(date -Is) on-boot: waiting for $BIND"
    i=0
    until ip -4 -o addr show | grep -q " $BIND/"; do
        i=$((i + 1)); [ "$i" -ge 300 ] && { echo "$(date -Is) on-boot: $BIND never appeared, giving up"; exit 1; }
        sleep 1
    done
fi
# Docker itself may still be starting.
i=0
until docker info >/dev/null 2>&1; do
    i=$((i + 1)); [ "$i" -ge 120 ] && { echo "$(date -Is) on-boot: docker not running, giving up"; exit 1; }
    sleep 1
done
container=$(docker compose ps -q web 2>/dev/null || true)
if [ -n "$container" ] && docker port "$container" 8000 2>/dev/null | grep -q "$BIND:$PORT"; then
    echo "$(date -Is) on-boot: port already published, nothing to do"
    exit 0
fi
# Reuse the image the last `make deploy` built instead of rebuilding at boot.
echo "$(date -Is) on-boot: port missing, recreating the web container"
docker compose up -d --force-recreate --no-build web
