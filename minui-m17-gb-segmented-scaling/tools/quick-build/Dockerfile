# Lightweight fallback toolchain for building minarch.elf on this machine.
# Debian buster = glibc 2.28 (the official m17 buildroot uses glibc 2.26).
# The produced ELF is checked with readelf -V before shipping; only GLIBC_2.4
# symbols are acceptable on the M17 device.
FROM debian/eol:buster-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN dpkg --add-architecture armhf && \
    apt-get -o Acquire::Check-Valid-Until=false update && \
    apt-get install -y --no-install-recommends \
      make \
      gcc-arm-linux-gnueabihf \
      libc6-dev-armhf-cross \
      libsdl2-dev:armhf \
      libsdl2-image-dev:armhf \
      libsdl2-ttf-dev:armhf \
      zlib1g-dev:armhf && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /root/workspace
