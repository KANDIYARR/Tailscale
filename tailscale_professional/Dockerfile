# BUILD_ARCH is supplied by Supervisor; amd64 supports standalone builds.
ARG BUILD_ARCH=amd64
ARG BUILD_FROM=ghcr.io/home-assistant/${BUILD_ARCH}-base:3.22
FROM $BUILD_FROM

ARG BUILD_ARCH
ARG BUILD_VERSION=1.0.0

# Use signed packages from the base image's Alpine repositories.
RUN apk add --no-cache tailscale iptables iproute2 jq

COPY rootfs/ /
RUN chmod 0755 /etc/services.d/tailscale/run

LABEL \
    io.hass.name="Tailscale Professional" \
    io.hass.description="Securely connect your Home Assistant instance to your Tailscale network." \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="addon" \
    io.hass.arch="${BUILD_ARCH}" \
    org.opencontainers.image.title="Tailscale Professional" \
    org.opencontainers.image.version="${BUILD_VERSION}" \
    org.opencontainers.image.authors="Vinoth Sakthivel"

# Inherit the Home Assistant base image's /init entrypoint.
