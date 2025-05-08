# Use Alpine as the base image for smaller size and potentially fewer vulnerabilities
FROM alpine:latest AS builder

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# Install Python and build dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    gcc \
    musl-dev \
    python3-dev

# Create and use a virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install external dependencies in the virtual environment
COPY pyproject.toml .
RUN pip install --upgrade pip && \
    pip install -e .[server,schema]

# Copy the source code
COPY . .

# Install the package itself (this includes any dependencies not in requirements.txt)
RUN pip install --no-cache-dir .

# Create a non-privileged system user and group for running the application
RUN addgroup -S neko && \
    adduser -S -G neko -s /sbin/nologin -h /app -g "Non-privileged app user" neko

# Create a runtime stage to minimize the final image size
FROM alpine:latest AS runtime

# Add image metadata
LABEL org.opencontainers.image.description="NekoConf: The purr-fect balance of power and simplicity for configuration management. " \
      org.opencontainers.image.source="https://github.com/neko-Foundation/NekoConf" \
      org.opencontainers.image.licenses="MIT"


# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Install Python runtime only (no build tools)
RUN apk add --no-cache python3

# Create the same user in the runtime image
RUN addgroup -S neko && \
    adduser -S -G neko -s /sbin/nologin -h /app -g "Non-privileged app user" neko

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy the application from the builder stage
COPY --from=builder /app /app

# Set proper ownership
RUN chown -R neko:neko /app

# Switch to non-root user
USER neko

# Expose the proxy port
EXPOSE 8000

# Command to run the application with the correct module path
ENTRYPOINT ["nekoconf"]
CMD ["server", "--config", "config.yaml"]
