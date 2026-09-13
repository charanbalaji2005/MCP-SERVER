"""Environment-driven configuration for the MCP server.

All values come from the environment (optionally loaded from a local
.env file via python-dotenv). Nothing here is hardcoded, and nothing
secret is ever logged.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or not val.strip():
        return default
    try:
        return int(val)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    workspace_root: Path
    max_file_size: int
    max_response_size: int
    http_timeout: int
    max_directory_depth: int
    log_level: str
    allow_private_network: bool
    transport: str
    http_host: str
    http_port: int


def load_settings() -> Settings:
    workspace = Path(os.getenv("MCP_WORKSPACE", "./workspace")).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    return Settings(
        workspace_root=workspace,
        max_file_size=_env_int("MCP_MAX_FILE_SIZE", 10 * 1024 * 1024),
        max_response_size=_env_int("MCP_MAX_RESPONSE_SIZE", 5 * 1024 * 1024),
        http_timeout=_env_int("MCP_HTTP_TIMEOUT", 10),
        max_directory_depth=_env_int("MCP_MAX_DIRECTORY_DEPTH", 12),
        log_level=os.getenv("MCP_LOG_LEVEL", "INFO").upper(),
        allow_private_network=_env_bool("MCP_ALLOW_PRIVATE_NETWORK", False),
        transport=os.getenv("MCP_TRANSPORT", "stdio").strip().lower(),
        http_host=os.getenv("MCP_HTTP_HOST", "127.0.0.1"),
        http_port=_env_int("MCP_HTTP_PORT", 8765),
    )


SETTINGS = load_settings()


def configure_logging() -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, SETTINGS.log_level, logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    logger = logging.getLogger("ubuntu_mcp")
    logger.info("Workspace root: %s", SETTINGS.workspace_root)
    return logger
