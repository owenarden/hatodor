FROM jlesage/baseimage-gui:ubuntu-24.04-v4

ARG BUILD_VERSION
ARG BUILD_ARCH

LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}"

RUN set -eux; \
    test "$(dpkg --print-architecture)" = "amd64"; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        python3; \
    curl -fL \
      "https://github.com/johannesjo/super-productivity/releases/latest/download/superProductivity-amd64.deb" \
      -o /tmp/super-productivity.deb; \
    apt-get install -y --no-install-recommends /tmp/super-productivity.deb; \
    rm -f /tmp/super-productivity.deb; \
    rm -rf /var/lib/apt/lists/*

COPY startapp.sh /startapp.sh
COPY sp_proxy.py /opt/sp_proxy.py

RUN chmod 0755 /startapp.sh /opt/sp_proxy.py && \
    set-cont-env APP_NAME "Super Productivity"

LABEL \
    org.opencontainers.image.title="Super Productivity Desktop for HAOS" \
    org.opencontainers.image.description="Electron Super Productivity desktop app with noVNC and HA REST proxy"
