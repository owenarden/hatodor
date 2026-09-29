FROM ghcr.io/home-assistant/base:3.24

ARG BUILD_VERSION
ARG BUILD_ARCH

LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache python3 py3-yaml tzdata

COPY clarifier /app/clarifier
COPY courses.example.yaml /app/courses.example.yaml

WORKDIR /app
ENV PYTHONUNBUFFERED=1

CMD ["python3", "-m", "clarifier"]
