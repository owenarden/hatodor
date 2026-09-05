#!/bin/sh
set -eu

HA_CONFIG="${HA_CONFIG:-/homeassistant}"
MANAGED_ROOT="${MANAGED_ROOT:-/managed}"
OPTIONS_FILE="${OPTIONS_FILE:-/data/options.json}"

if [ ! -d "$HA_CONFIG" ]; then
    echo "ERROR: Home Assistant configuration directory is not mounted at $HA_CONFIG" >&2
    exit 1
fi

mkdir -p \
    "$HA_CONFIG/packages" \
    "$HA_CONFIG/esphome" \
    "$HA_CONFIG/hatodor" \
    "$HA_CONFIG/www/hatodor/motd-cache"

cp "$MANAGED_ROOT/packages/morning_dashboard.yaml" \
    "$HA_CONFIG/packages/morning_dashboard.yaml"
cp "$MANAGED_ROOT/packages/school_dashboard.yaml" \
    "$HA_CONFIG/packages/school_dashboard.yaml"
cp "$MANAGED_ROOT/esphome/reterminal-e1001-morning.yaml" \
    "$HA_CONFIG/esphome/reterminal-e1001-morning.yaml"
cp "$MANAGED_ROOT/hatodor/render_cat_motd.py" \
    "$HA_CONFIG/hatodor/render_cat_motd.py"
cp "$MANAGED_ROOT/hatodor/fetch_zenquote.py" \
    "$HA_CONFIG/hatodor/fetch_zenquote.py"

# This is deliberately user-owned after its first installation. Config Sync
# updates the renderer but preserves any sayings the household has edited.
if [ ! -f "$HA_CONFIG/hatodor/cat_sayings.json" ]; then
    cp "$MANAGED_ROOT/hatodor/cat_sayings.json" \
        "$HA_CONFIG/hatodor/cat_sayings.json"
    echo "Installed editable Hatodor cat sayings: hatodor/cat_sayings.json"
else
    echo "Preserved editable Hatodor cat sayings: hatodor/cat_sayings.json"
fi

chmod 0644 \
    "$HA_CONFIG/packages/morning_dashboard.yaml" \
    "$HA_CONFIG/packages/school_dashboard.yaml" \
    "$HA_CONFIG/esphome/reterminal-e1001-morning.yaml" \
    "$HA_CONFIG/hatodor/cat_sayings.json"
chmod 0755 \
    "$HA_CONFIG/hatodor/render_cat_motd.py" \
    "$HA_CONFIG/hatodor/fetch_zenquote.py"

# Keep the photo-service credential in a private file read by the renderer.
# It is never placed in a Home Assistant entity or passed on the command line.
CAT_API_KEY_FILE="$HA_CONFIG/hatodor/thecatapi_key"
thecatapi_key=""
if [ -f "$OPTIONS_FILE" ]; then
    thecatapi_key="$(jq -r '.thecatapi_key // empty' "$OPTIONS_FILE")"
fi
if [ -n "$thecatapi_key" ]; then
    umask 077
    printf '%s\n' "$thecatapi_key" > "$CAT_API_KEY_FILE"
    chmod 0600 "$CAT_API_KEY_FILE"
    echo "Installed private The Cat API credential"
elif [ -s "$CAT_API_KEY_FILE" ]; then
    echo "Preserved private The Cat API credential"
else
    echo "WARNING: The Cat API key is not configured; use a CATAAS source until it is set" >&2
fi
unset thecatapi_key

echo "Installed Hatodor-managed Home Assistant package: packages/morning_dashboard.yaml"
echo "Installed Hatodor-managed Home Assistant package: packages/school_dashboard.yaml"
echo "Installed Hatodor-managed ESPHome config: esphome/reterminal-e1001-morning.yaml"
echo "Installed Hatodor cat MOTD renderer: hatodor/render_cat_motd.py"
echo "Installed Hatodor ZenQuote fetcher: hatodor/fetch_zenquote.py"

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

# Home Assistant has one generic TodoItem `due` field, while Super Productivity
# distinguishes planned/scheduled time (dueWithTime/dueDay) from an actual
# deadline (deadlineWithTime/deadlineDay). Hatodor uses SP deadlines. Patch the
# integration's TodoItem mapping so HA's generic `due` field reads/writes the SP
# deadline fields, leaving SP scheduling untouched.
SP_TODO="$HA_CONFIG/custom_components/super_productivity/todo.py"
if [ -f "$SP_TODO" ]; then
    if grep -Fq '"deadlineWithTime"' "$SP_TODO" && \
       grep -Fq '"deadlineDay"' "$SP_TODO" && \
       ! grep -Fq '"dueWithTime"' "$SP_TODO" && \
       ! grep -Fq '"dueDay"' "$SP_TODO"; then
        echo "Super Productivity todo mapping already uses deadline fields"
    elif grep -Fq '"dueWithTime"' "$SP_TODO" && \
         grep -Fq '"dueDay"' "$SP_TODO"; then
        sed -i \
            -e 's/"dueWithTime"/"deadlineWithTime"/g' \
            -e 's/"dueDay"/"deadlineDay"/g' \
            "$SP_TODO"
        echo "Patched Super Productivity TodoItem due mapping to use SP deadlines"
    else
        echo "WARNING: Super Productivity todo deadline mapping was not recognized; deadline patch not applied" >&2
    fi
else
    echo "WARNING: Super Productivity todo platform not found at $SP_TODO; deadline patch not applied" >&2
fi
