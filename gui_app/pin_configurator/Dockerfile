# SPDX-License-Identifier: Apache-2.0
# Pyontrust Pin Configurator — Development Docker Image
#
# Inspired by swedishembedded/develop:latest pattern.
# Provides a reproducible environment with:
#   - Python 3.12 + all dependencies
#   - Zephyr SDK + west tool
#   - Renode simulator
#   - RobotFramework for automated testing
#
# Usage:
#   docker build -t pyontrust:latest .
#   docker run -ti -p 5100:5100 pyontrust:latest
#   docker run -ti --privileged -v /dev/bus/usb:/dev/bus/usb -p 5100:5100 pyontrust:latest
#

FROM python:3.12-slim AS base

LABEL maintainer="Pyontrust Contributors"
LABEL description="Zephyr Pin Configurator development environment"
LABEL license="Apache-2.0"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    cmake \
    ninja-build \
    gperf \
    ccache \
    dfu-util \
    device-tree-compiler \
    wget \
    xz-utils \
    file \
    make \
    gcc \
    gcc-multilib \
    g++-multilib \
    libsdl2-dev \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install west and Python tools
RUN pip install --no-cache-dir \
    west \
    flask \
    pdfplumber \
    requests \
    pytest \
    pytest-cov \
    robotframework \
    pyelftools \
    pyyaml \
    packaging

# Install Renode (latest stable)
ARG RENODE_VERSION=1.15.3
RUN wget -q https://github.com/renode/renode/releases/download/v${RENODE_VERSION}/renode-${RENODE_VERSION}.linux-portable.tar.gz \
    && mkdir -p /opt/renode \
    && tar xzf renode-${RENODE_VERSION}.linux-portable.tar.gz -C /opt/renode --strip-components=1 \
    && rm renode-${RENODE_VERSION}.linux-portable.tar.gz \
    && ln -s /opt/renode/renode /usr/local/bin/renode \
    && ln -s /opt/renode/renode-test /usr/local/bin/renode-test

# Install Zephyr SDK
ARG ZEPHYR_SDK_VERSION=0.17.0
RUN wget -q https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${ZEPHYR_SDK_VERSION}/zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-x86_64_minimal.tar.xz \
    && tar xf zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-x86_64_minimal.tar.xz -C /opt \
    && rm zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-x86_64_minimal.tar.xz \
    && /opt/zephyr-sdk-${ZEPHYR_SDK_VERSION}/setup.sh -t arm-zephyr-eabi

ENV ZEPHYR_SDK_INSTALL_DIR=/opt/zephyr-sdk-${ZEPHYR_SDK_VERSION}
ENV ZEPHYR_TOOLCHAIN_VARIANT=zephyr

# Copy the pin configurator
WORKDIR /app
COPY . /app/

# Expose the web UI port
EXPOSE 5100

# Default command: launch the configurator
CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "5100"]
