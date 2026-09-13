# syntax=docker/dockerfile:1
FROM ubuntu:24.04

LABEL maintainer="Ubuntu MCP Server Maintainers"
LABEL description="Ubuntu MCP Server with Web GUI & Interactive Linux Terminal"

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV MCP_WORKSPACE=/app/workspace
ENV MCP_TRANSPORT=streamable-http
ENV MCP_HTTP_HOST=0.0.0.0
ENV MCP_HTTP_PORT=8765

# Install system dependencies
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    procps \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files
COPY . /app

# Setup venv and install dependencies
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -e ".[dev]" websockets

ENV PATH="/opt/venv/bin:$PATH"

# Expose Web GUI (8000) and MCP HTTP (8765)
EXPOSE 8000 8765

# Start Web GUI & MCP Server
CMD ["python3", "run_gui.py", "--host", "0.0.0.0", "--port", "8000", "--no-browser"]
