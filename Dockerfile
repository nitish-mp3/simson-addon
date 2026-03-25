ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install extra Python dependencies not in the addon-base image
RUN pip3 install --no-cache-dir --break-system-packages \
       websockets==13.1

# Copy rootfs (run.sh goes to /run.sh — addon-base calls it automatically via s6)
COPY rootfs /
RUN chmod a+x /run.sh

# Copy application code
WORKDIR /app
COPY app/ /app/
