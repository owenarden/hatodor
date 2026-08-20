#!/bin/sh
set -eu

HA_CONFIG="${HA_CONFIG:-/homeassistant}"

if [ ! -d "$HA_CONFIG" ]; then
    echo "ERROR: Home Assistant configuration directory is not mounted at $HA_CONFIG" >&2
    exit 1
fi

mkdir -p \
    "$HA_CONFIG/packages" \
    "$HA_CONFIG/esphome"

cp /managed/packages/morning_dashboard.yaml \
    "$HA_CONFIG/packages/morning_dashboard.yaml"
cp /managed/esphome/reterminal-e1001-morning.yaml \
    "$HA_CONFIG/esphome/reterminal-e1001-morning.yaml"

chmod 0644 \
    "$HA_CONFIG/packages/morning_dashboard.yaml" \
    "$HA_CONFIG/esphome/reterminal-e1001-morning.yaml"

echo "Installed Hatodor-managed Home Assistant package: packages/morning_dashboard.yaml"
echo "Installed Hatodor-managed ESPHome config: esphome/reterminal-e1001-morning.yaml"
