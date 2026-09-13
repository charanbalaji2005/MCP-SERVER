"""MCP server entry point.

Builds an MCP server named "Ubuntu MCP Server" and registers every tool
from the tools/ package. Every tool is wrapped with @safe_tool so it
always returns a structured {success, data, error} result instead of
raising, and every filesystem/network/git operation is confined by the
boundaries in security.py.

Compatible with both mcp>=2 (class renamed MCPServer) and mcp 1.x
(class named FastMCP) -- see the try/except import below.
"""

from __future__ import annotations

try:  # mcp < 2.0
    from mcp.server.fastmcp import FastMCP as _MCPServerClass
except ModuleNotFoundError:  # mcp >= 2.0
    from mcp.server.mcpserver import MCPServer as _MCPServerClass

from .config import SETTINGS, configure_logging
from .models import safe_tool
from .tools import code_tools, directories, filesystem, git_tools, network, system

logger = configure_logging()

mcp = _MCPServerClass(
    name="Ubuntu MCP Server",
    instructions=(
        "Sandboxed filesystem, directory, Ubuntu system, network, git, and "
        "code/text tools. All filesystem paths are confined inside the "
        f"workspace at {SETTINGS.workspace_root}. Network tools block "
        "requests to private/loopback addresses to prevent SSRF. There is "
        "no arbitrary shell-command execution tool."
    ),
)

# ---------------------------------------------------------------------------
# Filesystem
# ---------------------------------------------------------------------------


@mcp.tool()
@safe_tool
async def read_file(path: str, encoding: str = "utf-8") -> dict:
    """Read a UTF-8 (or other specified encoding) text file from the workspace.

    Args:
        path: Path to the file, relative to the workspace root.
        encoding: Text encoding to decode with (default "utf-8").

    Returns:
        The file's path, size in bytes, encoding, and full text content.
        Fails if the file does not exist, isn't a file, exceeds the
        configured max file size, or isn't valid text in that encoding.
    """
    return await filesystem.read_file(path, encoding)


@mcp.tool()
@safe_tool
async def write_file(path: str, content: str, overwrite: bool = True) -> dict:
    """Create or overwrite a text file inside the workspace.

    Args:
        path: Destination path, relative to the workspace root. Parent
            directories are created automatically.
        content: Text content to write (UTF-8).
        overwrite: If False and the file already exists, fails instead
            of overwriting it.

    Returns:
        The path and number of bytes written.
    """
    return await filesystem.write_file(path, content, overwrite)


@mcp.tool()
@safe_tool
async def append_file(path: str, content: str) -> dict:
    """Append text to an existing file inside the workspace.

    Args:
        path: Path to an existing file, relative to the workspace root.
        content: Text to append.

    Returns:
        The path and number of bytes appended. Fails if the file does
        not exist or if appending would exceed the max file size.
    """
    return await filesystem.append_file(path, content)


@mcp.tool()
@safe_tool
async def delete_file(path: str) -> dict:
    """Delete a single file inside the workspace.

    Args:
        path: Path to the file to delete, relative to the workspace root.

    Returns:
        The deleted path. Fails if the path does not exist or is a
        directory (use delete_directory for directories).
    """
    return await filesystem.delete_file(path)


@mcp.tool()
@safe_tool
async def copy_file(source: str, destination: str) -> dict:
    """Copy a file within the workspace, preserving metadata.

    Args:
        source: Existing file path, relative to the workspace root.
        destination: Destination path; parent directories are created
            automatically.
    """
    return await filesystem.copy_file(source, destination)


@mcp.tool()
@safe_tool
async def move_file(source: str, destination: str) -> dict:
    """Move or rename a file within the workspace.

    Args:
        source: Existing file path, relative to the workspace root.
        destination: New path; parent directories are created automatically.
    """
    return await filesystem.move_file(source, destination)


@mcp.tool()
@safe_tool
async def file_exists(path: str) -> dict:
    """Check whether a given path exists and is a regular file.

    Args:
        path: Path to check, relative to the workspace root.
    """
    return await filesystem.file_exists(path)


@mcp.tool()
@safe_tool
async def get_file_info(path: str) -> dict:
    """Get metadata about a file: size, modified/created time, extension.

    Args:
        path: Path to the file, relative to the workspace root.
    """
    return await filesystem.get_file_info(path)


# ---------------------------------------------------------------------------
# Directories
# ---------------------------------------------------------------------------


@mcp.tool()
@safe_tool
async def list_directory(path: str = ".", recursive: bool = False) -> dict:
    """List the contents of a directory inside the workspace.

    Args:
        path: Directory to list, relative to the workspace root
            (default: the workspace root itself).
        recursive: If True, walk subdirectories too (capped by
            MCP_MAX_DIRECTORY_DEPTH).

    Returns:
        Each entry's name, relative path, whether it's a file or
        directory, and file size when applicable.
    """
    return await directories.list_directory(path, recursive)


@mcp.tool()
@safe_tool
async def create_directory(path: str) -> dict:
    """Create a directory (and any missing parent directories) in the workspace.

    Args:
        path: Directory path to create, relative to the workspace root.
    """
    return await directories.create_directory(path)


@mcp.tool()
@safe_tool
async def delete_directory(path: str, recursive: bool = False) -> dict:
    """Delete a directory inside the workspace.

    Args:
        path: Directory to delete, relative to the workspace root.
        recursive: Required to be True to delete a non-empty directory
            and everything inside it. The workspace root itself can
            never be deleted.
    """
    return await directories.delete_directory(path, recursive)


@mcp.tool()
@safe_tool
async def directory_exists(path: str) -> dict:
    """Check whether a given path exists and is a directory.

    Args:
        path: Path to check, relative to the workspace root.
    """
    return await directories.directory_exists(path)


@mcp.tool()
@safe_tool
async def find_files(path: str = ".", pattern: str = "*") -> dict:
    """Recursively find files under a directory matching a glob pattern.

    Args:
        path: Directory to search under, relative to the workspace root.
        pattern: Filename glob, e.g. "*.py" or "*.md" (matched against
            the filename only, not the full path).

    Returns:
        Up to 500 matching relative file paths.
    """
    return await directories.find_files(path, pattern)


@mcp.tool()
@safe_tool
async def get_directory_size(path: str = ".") -> dict:
    """Recursively calculate the total size of a directory's contents.

    Args:
        path: Directory to measure, relative to the workspace root.

    Returns:
        Total size in bytes and megabytes, plus the number of files counted.
    """
    return await directories.get_directory_size(path)


# ---------------------------------------------------------------------------
# Ubuntu / system
# ---------------------------------------------------------------------------


@mcp.tool()
@safe_tool
async def get_system_info() -> dict:
    """Get basic host information: OS, kernel release, architecture,
    hostname, Python version, and boot time."""
    return await system.get_system_info()


@mcp.tool()
@safe_tool
async def get_cpu_info() -> dict:
    """Get CPU information: core counts, current utilization (overall
    and per-core), clock frequency, and 1/5/15-minute load averages."""
    return await system.get_cpu_info()


@mcp.tool()
@safe_tool
async def get_memory_info() -> dict:
    """Get RAM and swap usage in gigabytes and as a percentage."""
    return await system.get_memory_info()


@mcp.tool()
@safe_tool
async def get_disk_info(path: str = ".") -> dict:
    """Get disk usage (total/used/free, in GB) for the filesystem
    containing the given workspace-relative path.

    Args:
        path: Path (inside the workspace) whose filesystem to inspect.
    """
    return await system.get_disk_info(path)


@mcp.tool()
@safe_tool
async def list_processes(limit: int = 20, sort_by: str = "cpu") -> dict:
    """List running processes on the host (read-only; cannot start, stop,
    or signal anything).

    Args:
        limit: Max number of processes to return (1-200).
        sort_by: "cpu" or "memory" -- which usage metric to sort by,
            descending.

    Returns:
        Each process's pid, name, username, cpu%, memory%, and status.
    """
    return await system.list_processes(limit, sort_by)


@mcp.tool()
@safe_tool
async def get_service_status(service_name: str) -> dict:
    """Get the `systemctl status` output for one systemd service (read-only;
    cannot start, stop, restart, enable, or disable services).

    Args:
        service_name: Service unit name, e.g. "nginx" or "ssh.service".
            Only letters, digits, '@', '.', '_', and '-' are allowed.
    """
    return await system.get_service_status(service_name)


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------


@mcp.tool()
@safe_tool
async def fetch_url(url: str, timeout: int | None = None) -> dict:
    """Fetch a public HTTP/HTTPS URL and return its status, headers, and body.

    Blocks requests to localhost, loopback, link-local, and private IP
    ranges to prevent SSRF (unless MCP_ALLOW_PRIVATE_NETWORK=true).
    Response bodies are capped at MCP_MAX_RESPONSE_SIZE bytes.

    Args:
        url: The http:// or https:// URL to fetch.
        timeout: Optional per-request timeout in seconds (defaults to
            MCP_HTTP_TIMEOUT).
    """
    return await network.fetch_url(url, timeout)


@mcp.tool()
@safe_tool
async def check_connectivity(host: str, port: int, timeout: int = 3) -> dict:
    """Check whether a TCP port on a public host is reachable.

    Args:
        host: Hostname or IP to test (private/loopback hosts are blocked).
        port: TCP port number (1-65535).
        timeout: Connection timeout in seconds.
    """
    return await network.check_connectivity(host, port, timeout)


@mcp.tool()
@safe_tool
async def resolve_dns(hostname: str) -> dict:
    """Resolve a hostname to its IP address(es) and flag whether any are private.

    Args:
        hostname: The hostname to resolve.
    """
    return await network.resolve_dns(hostname)


@mcp.tool()
@safe_tool
async def validate_url(url: str) -> dict:
    """Validate that a string is a well-formed http/https URL (syntax
    check only; does not make a network request).

    Args:
        url: The URL string to validate.
    """
    return await network.validate_url(url)


@mcp.tool()
@safe_tool
async def parse_url(url: str) -> dict:
    """Break a URL down into scheme, hostname, port, path, query, and fragment.

    Args:
        url: The URL to parse.
    """
    return await network.parse_url(url)


@mcp.tool()
@safe_tool
async def build_url(base_url: str, path: str = "", query: dict | None = None) -> dict:
    """Construct a URL from a base URL, an appended path, and optional
    query parameters.

    Args:
        base_url: Base http/https URL.
        path: Path segment to append.
        query: Optional dict of query parameters to encode and attach.
    """
    return await network.build_url(base_url, path, query)


# ---------------------------------------------------------------------------
# Git (read-only; fixed subcommands only)
# ---------------------------------------------------------------------------


@mcp.tool()
@safe_tool
async def git_status(path: str = ".") -> dict:
    """Get `git status` (branch info + changed files) for a repository
    inside the workspace.

    Args:
        path: Path to the git repository, relative to the workspace root.
    """
    return await git_tools.git_status(path)


@mcp.tool()
@safe_tool
async def git_log(path: str = ".", limit: int = 10) -> dict:
    """Get recent commit history for a repository inside the workspace.

    Args:
        path: Path to the git repository, relative to the workspace root.
        limit: Number of commits to return (1-200).
    """
    return await git_tools.git_log(path, limit)


@mcp.tool()
@safe_tool
async def git_diff(path: str = ".", staged: bool = False, file_path: str | None = None) -> dict:
    """Get the current diff for a repository inside the workspace.

    Args:
        path: Path to the git repository, relative to the workspace root.
        staged: If True, show staged (index) changes instead of the
            working-tree diff.
        file_path: Optional single file to limit the diff to.
    """
    return await git_tools.git_diff(path, staged, file_path)


@mcp.tool()
@safe_tool
async def git_branches(path: str = ".") -> dict:
    """List local branches for a repository inside the workspace, marking
    which one is currently checked out.

    Args:
        path: Path to the git repository, relative to the workspace root.
    """
    return await git_tools.git_branches(path)


@mcp.tool()
@safe_tool
async def git_current_branch(path: str = ".") -> dict:
    """Get the name of the currently checked-out branch.

    Args:
        path: Path to the git repository, relative to the workspace root.
    """
    return await git_tools.git_current_branch(path)


# ---------------------------------------------------------------------------
# Code / text / data
# ---------------------------------------------------------------------------


@mcp.tool()
@safe_tool
async def detect_project_type(path: str = ".") -> dict:
    """Guess the project type(s) present in a directory by looking for
    common marker files (pyproject.toml, package.json, Cargo.toml, etc.).

    Args:
        path: Directory to inspect, relative to the workspace root.
    """
    return await code_tools.detect_project_type(path)


@mcp.tool()
@safe_tool
async def search_text_in_files(
    path: str = ".", pattern: str = "", file_glob: str = "*", max_results: int = 50
) -> dict:
    """Recursively regex-search text files under a directory (like a
    scoped grep), confined to the workspace.

    Args:
        path: Directory to search under, relative to the workspace root.
        pattern: Python regular expression to search each line for.
        file_glob: Glob to filter which files are searched, e.g. "*.py".
        max_results: Maximum number of matching lines to return (1-500).
    """
    return await code_tools.search_text_in_files(path, pattern, file_glob, max_results)


@mcp.tool()
@safe_tool
async def count_words(text: str) -> dict:
    """Count words, characters, and lines in a block of text.

    Args:
        text: The text to analyze.
    """
    return await code_tools.count_words(text)


@mcp.tool()
@safe_tool
async def format_json(json_text: str, indent: int = 2) -> dict:
    """Pretty-print (reformat) a JSON string with the given indentation.

    Args:
        json_text: Raw JSON text to parse and reformat.
        indent: Number of spaces per indent level (0-8).
    """
    return await code_tools.format_json(json_text, indent)


@mcp.tool()
@safe_tool
async def validate_json(json_text: str) -> dict:
    """Check whether a string is valid JSON without modifying it.

    Args:
        json_text: The text to validate.
    """
    return await code_tools.validate_json(json_text)


@mcp.tool()
@safe_tool
async def csv_to_json(path: str) -> dict:
    """Read a CSV file from the workspace and convert it to a list of
    row objects keyed by header column.

    Args:
        path: Path to the CSV file, relative to the workspace root.
    """
    return await code_tools.csv_to_json(path)


@mcp.tool()
@safe_tool
async def csv_get_columns(path: str) -> dict:
    """Read just the header row of a CSV file in the workspace.

    Args:
        path: Path to the CSV file, relative to the workspace root.
    """
    return await code_tools.csv_get_columns(path)


def run() -> None:
    tool_count = None
    try:
        # best-effort tool count for the startup log line only
        tool_count = len(mcp._tool_manager.list_tools())  # type: ignore[attr-defined]
    except Exception:
        pass

    if SETTINGS.transport == "stdio":
        logger.info(
            "Starting Ubuntu MCP Server over stdio (tools registered: %s). "
            "This mode expects an MCP client (e.g. Claude Code, Claude "
            "Desktop) to launch this process directly -- it is LOCAL ONLY "
            "and is not reachable over the network.",
            tool_count or "unknown",
        )
        mcp.run(transport="stdio")
    elif SETTINGS.transport == "streamable-http":
        logger.warning(
            "Starting Ubuntu MCP Server over streamable-http on %s:%s "
            "(tools registered: %s). This binds a network port with NO "
            "built-in authentication. Do not expose it directly to the "
            "internet -- put it behind a reverse proxy (e.g. nginx/Caddy) "
            "that terminates TLS and enforces auth, or restrict it to a "
            "private network/VPN.",
            SETTINGS.http_host,
            SETTINGS.http_port,
            tool_count or "unknown",
        )
        mcp.run(
            transport="streamable-http",
            host=SETTINGS.http_host,
            port=SETTINGS.http_port,
        )
    else:
        raise ValueError(
            f"Unknown MCP_TRANSPORT '{SETTINGS.transport}'. Use 'stdio' or 'streamable-http'."
        )


if __name__ == "__main__":
    run()
