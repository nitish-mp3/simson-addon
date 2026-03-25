ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install Python and required packages (base:3.19 is plain Alpine)
RUN apk add --no-cache python3 py3-pip py3-aiohttp

# Install websockets (not in Alpine repos at the required version)
RUN pip3 install --no-cache-dir --break-system-packages websockets==13.1

# Copy entrypoint and app
COPY rootfs/run.sh /run.sh
RUN chmod a+x /run.sh
COPY app/ /app/

# Bypass s6-overlay: run our script directly as PID 1
ENTRYPOINT ["/run.sh"]
