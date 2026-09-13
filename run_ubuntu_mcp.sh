#!/usr/bin/env bash
source /home/charan_balaji/.venvs/ubuntu-mcp/bin/activate
cd /mnt/d/ubuntu-mcp-server/ubuntu-mcp-server
python -m ubuntu_mcp "$@"
