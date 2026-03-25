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

# Copy s6-overlay service directory and rootfs files
COPY rootfs /

# Make s6 service script executable
RUN chmod a+x /etc/services.d/simson/run

# Copy application code
WORKDIR /app
COPY app/ /app/
