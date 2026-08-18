FROM jlesage/baseimage-gui:ubuntu-24.04-v4.13.2

ARG SP_VERSION="18.19.0"
ENV SP_VERSION="${SP_VERSION}"

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl python3; \
    arch="$(dpkg --print-architecture)"; \
    test "${arch}" = "amd64"; \
    curl -fL \
      "https://github.com/super-productivity/super-productivity/releases/download/v${SP_VERSION}/superProductivity-amd64.deb" \
      -o /tmp/super-productivity.deb; \
    apt-get install -y --no-install-recommends /tmp/super-productivity.deb; \
    rm -f /tmp/super-productivity.deb; \
    rm -rf /var/lib/apt/lists/*

COPY startapp.sh /startapp.sh
COPY sp_proxy.py /opt/sp_proxy.py

RUN chmod 0755 /startapp.sh /opt/sp_proxy.py && \
    set-cont-env APP_NAME "Super Productivity" && \
    set-cont-env APP_VERSION "${SP_VERSION}"

LABEL org.opencontainers.image.title="Super Productivity Desktop for HAOS" \
      org.opencontainers.image.description="Electron Super Productivity desktop app with noVNC and authenticated HA REST proxy"
