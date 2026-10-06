# The community base supplies Bashio, S6 Overlay v3 and Tempio.
ARG BUILD_ARCH=amd64
ARG BUILD_FROM=ghcr.io/hassio-addons/base/${BUILD_ARCH}:21.0.7
FROM ${BUILD_FROM}
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ARG BUILD_ARCH=amd64
ARG BUILD_VERSION=2.0.0
ARG TAILSCALE_VERSION=1.102.4
# Same networking dependencies as the attributed upstream implementation.
RUN apk add --no-cache \
      bind-tools=9.20.29-r0 dnsmasq=2.92_p2-r0 ethtool=7.0-r0 \
      ipcalc=1.0.3-r1 iproute2=7.0.0-r0 iptables=1.8.13-r0 \
      nginx=1.30.4-r1 coreutils=9.11-r0 networkmanager=1.52.2-r0 \
      python3 jq ca-certificates \
    && ln -sf /sbin/xtables-nft-multi /sbin/ip6tables \
    && ln -sf /sbin/xtables-nft-multi /sbin/iptables \
    && rm -rf /usr/lib/NetworkManager/dispatcher.d
# Verify the pinned official Tailscale archive against its published SHA256.
RUN case "${BUILD_ARCH}" in aarch64) TS_ARCH=arm64 ;; amd64) TS_ARCH=amd64 ;; *) exit 1 ;; esac \
    && TS_ARCHIVE="tailscale_${TAILSCALE_VERSION}_${TS_ARCH}.tgz" \
    && curl --fail --show-error --silent --location --retry 3 \
         "https://pkgs.tailscale.com/stable/${TS_ARCHIVE}" -o "/tmp/${TS_ARCHIVE}" \
    && curl --fail --show-error --silent --location --retry 3 \
         "https://pkgs.tailscale.com/stable/${TS_ARCHIVE}.sha256" -o /tmp/tailscale.sha256 \
    && TS_SHA="$(awk '{print $1}' /tmp/tailscale.sha256)" \
    && [[ "${TS_SHA}" =~ ^[a-f0-9]{64}$ ]] \
    && printf '%s  %s\n' "${TS_SHA}" "/tmp/${TS_ARCHIVE}" | sha256sum -c - \
    && tar -xzf "/tmp/${TS_ARCHIVE}" -C /opt --strip-components=1 \
    && rm -rf /opt/systemd "/tmp/${TS_ARCHIVE}" /tmp/tailscale.sha256
COPY rootfs/ /
COPY defaults.json /opt/professional/defaults.json
COPY LICENSE /usr/share/licenses/tailscale-professional/LICENSE
RUN find /etc/s6-overlay -type f \( -name run -o -name finish -o -name '*.sh' \) -exec chmod 0755 {} + \
    && chmod 0755 /usr/bin/professional-options /usr/bin/healthcheck \
    && python3 -m compileall -q /opt/professional
ENV S6_STAGE2_HOOK=/etc/s6-overlay/scripts/stage2_hook.sh
HEALTHCHECK --interval=30s --timeout=15s --start-period=90s CMD ["/usr/bin/healthcheck"]
LABEL io.hass.name="Tailscale Professional" \
      io.hass.description="Securely connect your Home Assistant instance to your Tailscale network." \
      io.hass.type="addon" io.hass.arch="${BUILD_ARCH}" io.hass.version="${BUILD_VERSION}" \
      org.opencontainers.image.title="Tailscale Professional" \
      org.opencontainers.image.version="${BUILD_VERSION}" \
      org.opencontainers.image.authors="Vinoth Sakthivel" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/KANDIYARR/Tailscale"
# /init is inherited. S6 manages every service; no shell CMD or ENTRYPOINT.
