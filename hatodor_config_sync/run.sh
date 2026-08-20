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

# The upstream Super Productivity integration currently fetches its main task
# list with include_done=False (the API default). That makes a completed project
# task disappear from the HA todo entity immediately after the coordinator
# refreshes. Hatodor's dashboard semantics need completed tasks to remain in the
# project entity until the dashboard rollover resets/removes them.
#
# Keep this as a small, idempotent source patch rather than vendoring the whole
# integration. If HACS updates the integration later, rerunning Config Sync will
# reapply the patch as long as the upstream call site is still recognizable.
SP_COORDINATOR="$HA_CONFIG/custom_components/super_productivity/coordinator.py"
if [ -f "$SP_COORDINATOR" ]; then
    if grep -Fq 'self.api.async_get_tasks(include_done=True),' "$SP_COORDINATOR"; then
        echo "Super Productivity coordinator already includes completed tasks"
    elif grep -Fq 'self.api.async_get_tasks(),' "$SP_COORDINATOR"; then
        sed -i \
            's/self\.api\.async_get_tasks(),/self.api.async_get_tasks(include_done=True),/' \
            "$SP_COORDINATOR"
        echo "Patched Super Productivity coordinator to fetch completed project tasks"
    else
        echo "WARNING: Super Productivity coordinator call site was not recognized; include_done patch not applied" >&2
    fi
else
    echo "WARNING: Super Productivity custom integration not found at $SP_COORDINATOR; include_done patch not applied" >&2
fi
