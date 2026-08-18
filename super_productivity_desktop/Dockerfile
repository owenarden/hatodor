FROM jlesage/baseimage-gui:ubuntu-24.04-v4

ARG BUILD_VERSION
ARG BUILD_ARCH

LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}"

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8

RUN set -eux; \
    test "$(dpkg --print-architecture)" = "amd64"; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        python3 \
        libgbm1; \
    curl -fL \
      "https://github.com/johannesjo/super-productivity/releases/latest/download/superProductivity-amd64.deb" \
      -o /tmp/super-productivity.deb; \
    \
    # jlesage intentionally makes /var/log a symlink to /config/log. \
    # Ubuntu systemd's package postinst expects /var/log to be a real \
    # directory, so temporarily restore the conventional layout while \
    # apt configures Super Productivity and its dependencies. \
    rm -f /var/log; \
    mkdir -p /var/log; \
    apt-get install -y --no-install-recommends /tmp/super-productivity.deb; \
    rm -rf /var/log; \
    ln -s /config/log /var/log; \
    \
    # Fail the image build immediately if Electron still has an unresolved \
    # ELF shared-library dependency.  (Runtime dlopen() dependencies can still \
    # only be discovered by actually starting the application.) \
    ldd "/opt/Super Productivity/superproductivity-bin" | tee /tmp/sp-ldd.txt; \
    ! grep -q "not found" /tmp/sp-ldd.txt; \
    \
    rm -f /tmp/sp-ldd.txt /tmp/super-productivity.deb; \
    rm -rf /var/lib/apt/lists/*

COPY startapp.sh /startapp.sh
COPY sp_proxy.py /opt/sp_proxy.py

RUN chmod 0755 /startapp.sh /opt/sp_proxy.py && \
    set-cont-env APP_NAME "Super Productivity"

LABEL \
    org.opencontainers.image.title="Super Productivity Desktop for HAOS" \
    org.opencontainers.image.description="Electron Super Productivity desktop app with noVNC and HA REST proxy"
