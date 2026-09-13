"""Security boundary.

Two independent boundaries are enforced everywhere in this project:

1. FILESYSTEM: every filesystem/directory/git/code tool resolves its
   path through `safe_path()`, which confines the result inside
   MCP_WORKSPACE. Traversal via `..`, absolute paths outside the
   workspace, and symlinks that escape the workspace are all rejected.

2. NETWORK: `fetch_url()` in tools/network.py resolves the target
   hostname and rejects loopback, link-local, and private ranges
   unless MCP_ALLOW_PRIVATE_NETWORK=true, to prevent SSRF.

Nothing in this project shells out to an arbitrary, user-supplied
command. Git and process-listing tools call fixed, whitelisted
subcommands only (see tools/git_tools.py and tools/system.py).
"""

from __future__ import annotations

import ipaddress
import socket
from pathlib import Path

from .config import SETTINGS
from .exceptions import NotFoundError, SecurityError


def safe_path(user_path: str, *, must_exist: bool = False) -> Path:
    """Resolve `user_path` (relative to the workspace root) and verify
    the result stays inside the workspace. Raises SecurityError otherwise.
    """
    if user_path is None or user_path == "":
        raise SecurityError("A path is required.")

    if "\x00" in user_path:
        raise SecurityError("Path contains a null byte.")

    root = SETTINGS.workspace_root
    candidate = Path(user_path)

    # Treat both relative paths and paths that merely *look* absolute
    # as relative to the workspace root -- an AI client should never be
    # able to address the real filesystem root by typing "/etc/passwd".
    if candidate.is_absolute() or candidate.anchor:
        candidate = Path(*candidate.parts[1:]) if len(candidate.parts) > 1 else Path()

    resolved = (root / candidate).resolve()

    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise SecurityError(
            f"Path '{user_path}' resolves outside the allowed workspace."
        ) from exc

    if must_exist and not resolved.exists():
        # Not existing isn't a security violation -- surface it as a plain
        # not-found so callers/tests can distinguish "doesn't exist" from
        # "tried to escape the workspace".
        raise NotFoundError(f"Path '{user_path}' does not exist.")

    return resolved


_PRIVATE_NETWORKS = [
    ipaddress.ip_network(net)
    for net in (
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",
        "0.0.0.0/8",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
]


def is_private_or_loopback(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # unparsable -> treat as unsafe
    if ip.is_loopback or ip.is_link_local or ip.is_private or ip.is_reserved:
        return True
    return any(ip in net for net in _PRIVATE_NETWORKS)


def assert_public_host(hostname: str) -> None:
    """Resolve `hostname` and raise SecurityError if it maps to a
    private / loopback / link-local address, unless explicitly allowed.
    """
    if SETTINGS.allow_private_network:
        return

    if hostname.lower() in {"localhost", "localhost.localdomain"}:
        raise SecurityError("Requests to localhost are not allowed.")

    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise SecurityError(f"Could not resolve host '{hostname}'.") from exc

    for info in infos:
        addr = info[4][0]
        if is_private_or_loopback(addr):
            raise SecurityError(
                f"Host '{hostname}' resolves to a private/loopback address "
                "and is blocked to prevent SSRF."
            )
