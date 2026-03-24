ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install Python and dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-aiohttp \
    py3-yaml \
    && pip3 install --no-cache-dir --break-system-packages \
       websockets==13.1 \
       aiohttp==3.10.11

# Copy addon files
COPY rootfs /

# Ensure run script is executable
RUN chmod a+x /run.sh

WORKDIR /app
COPY app/ /app/

CMD ["/run.sh"]
