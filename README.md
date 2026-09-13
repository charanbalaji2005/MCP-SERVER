# Ubuntu MCP Server & Web Console

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP Protocol](https://img.shields.io/badge/MCP-2024--11--05-orange.svg)](https://modelcontextprotocol.io)
[![Tests: 61 passed](https://img.shields.io/badge/tests-61%20passed-brightgreen.svg)](https://pytest.org)
[![Docker Support](https://img.shields.io/badge/docker-ready-2496ED.svg)](https://www.docker.com/)

A sandboxed [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server exposing **38 tools** for filesystem, directory, Ubuntu system, network, git, and code/text operations — packaged with a **futuristic Web GUI & Interactive Linux Terminal** (xterm.js + WebSockets).

Connect directly with MCP-compatible AI clients (**Antigravity IDE, Claude Desktop, Cursor, Claude Code**) or interact directly through your browser!

---

## ⚡ Quick Start — Launch Web GUI & Terminal

```bash
# Clone the repository
git clone https://github.com/<your-username>/ubuntu-mcp-server.git
cd ubuntu-mcp-server

# Run the Web Console (opens automatically at http://localhost:8000)
python run_gui.py
# Or on Windows: .\run_gui.bat
# Or on Linux:   ./run_gui.sh
```

### ✨ Web Console Features:
1. **🖥️ Interactive Linux Terminal**: Full ANSI color, real-time bash prompt, autocomplete, vim/nano support, connected to the active Ubuntu/WSL session!
2. **⚡ MCP Playground & Tool Explorer**: Browse all 38 tools, fill schema-driven argument forms, and execute tools live with formatted JSON outputs and latency metrics.
3. **📊 Live System Monitor**: Real-time dials for CPU, RAM, Disk utilization, and a live top processes table.
4. **🔌 1-Click Integration Hub**: Instant copy-paste configurations for Antigravity, Claude Desktop, Cursor, and Docker.

---

## Architecture


```
        AI Client (Claude Code / Claude Desktop / Cursor / ...)
                          │
                          │  MCP protocol (stdio, or streamable-http if remote)
                          ▼
                 ┌─────────────────────┐
                 │  Ubuntu MCP Server  │
                 │   (MCPServer/       │
                 │    FastMCP)         │
                 └──────────┬──────────┘
                             │
      ┌───────────┬─────────┼─────────┬───────────┬──────────┐
      ▼           ▼         ▼         ▼           ▼          ▼
 Filesystem   Directories  System   Network      Git      Code/Text
  8 tools      6 tools     6 tools  6 tools     5 tools    7 tools
      │           │         │         │           │          │
      └───────────┴─────────┼─────────┴───────────┴──────────┘
                             ▼
                     Security boundary
                (security.py: workspace sandbox
                 + SSRF-blocking network guard)
                             │
                             ▼
                        Ubuntu host
```

There is **no arbitrary shell-execution tool**. The only subprocess calls
in the project are fixed, whitelisted invocations: `git <fixed subcommand>`
and `systemctl status <validated-name> --no-pager`. Nothing here accepts a
free-form command string from the AI client.

## Features / tool list

All tool names below are exactly what the MCP client sees.

**Filesystem** (`src/ubuntu_mcp/tools/filesystem.py`)
`read_file`, `write_file`, `append_file`, `delete_file`, `copy_file`,
`move_file`, `file_exists`, `get_file_info`

**Directories** (`directories.py`)
`list_directory`, `create_directory`, `delete_directory`,
`directory_exists`, `find_files`, `get_directory_size`

**Ubuntu / system** (`system.py`) — all read-only
`get_system_info`, `get_cpu_info`, `get_memory_info`, `get_disk_info`,
`list_processes`, `get_service_status`

**Network** (`network.py`) — SSRF-guarded
`fetch_url`, `check_connectivity`, `resolve_dns`, `validate_url`,
`parse_url`, `build_url`

**Git** (`git_tools.py`) — read-only, fixed subcommands only
`git_status`, `git_log`, `git_diff`, `git_branches`, `git_current_branch`

**Code / text / data** (`code_tools.py`)
`detect_project_type`, `search_text_in_files`, `count_words`,
`format_json`, `validate_json`, `csv_to_json`, `csv_get_columns`

Every tool returns the same predictable shape:

```json
{"success": true,  "data": {...}, "error": null}
{"success": false, "data": null,  "error": {"code": "...", "message": "..."}}
```

## Requirements

- Ubuntu (or any modern Linux/macOS) with Python 3.10+
- `git` (for the git tools; everything else works without it)
- `systemctl` optional (only `get_service_status` needs it; it degrades
  gracefully to `{"available": false}` if missing)

## Installation

### Quick path

```bash
git clone <your-fork-or-copy-of-this-repo> ubuntu-mcp-server
cd ubuntu-mcp-server
./deploy/install.sh
```

This installs OS packages, creates `.venv/`, installs the project,
copies `.env.example` → `.env`, and runs the test suite as a smoke check.

### Manual path (Ubuntu/Linux/macOS)

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git   # Ubuntu only

python3 -m venv .venv
source .venv/bin/activate           # macOS/Linux
# .venv\Scripts\activate            # Windows (PowerShell)

pip install --upgrade pip
pip install -e ".[dev]"

cp .env.example .env
```

## Environment configuration

All configuration is read from environment variables (optionally via
`.env`, loaded with `python-dotenv`). See `.env.example` for the full,
commented list. Key ones:

| Variable | Default | Purpose |
|---|---|---|
| `MCP_WORKSPACE` | `./workspace` | Sandbox root. Every filesystem/git/code tool is confined here. |
| `MCP_MAX_FILE_SIZE` | `10485760` (10 MB) | Max file size for read/write/append. |
| `MCP_MAX_RESPONSE_SIZE` | `5242880` (5 MB) | Max bytes `fetch_url` will buffer. |
| `MCP_HTTP_TIMEOUT` | `10` | Default `fetch_url` timeout, seconds. |
| `MCP_ALLOW_PRIVATE_NETWORK` | `false` | Set `true` to let `fetch_url`/`check_connectivity` reach private/loopback hosts. |
| `MCP_TRANSPORT` | `stdio` | `stdio` (local, client-launched) or `streamable-http` (remote). |
| `MCP_HTTP_HOST` / `MCP_HTTP_PORT` | `127.0.0.1` / `8765` | Bind address for `streamable-http`. |

Never commit your real `.env`.

## Running locally (stdio — the normal case)

```bash
source .venv/bin/activate
python -m ubuntu_mcp
```

In `stdio` mode the process expects to be **launched by an MCP client**,
which owns its stdin/stdout. Running it by hand like this will just sit
there — that's expected; an MCP client is what talks to it. To see it
actually respond, configure a client (next section) instead of running
it standalone.

## Testing

```bash
source .venv/bin/activate
pytest -q
```

61 tests cover every tool module, including: happy paths, invalid input,
path-traversal / workspace-escape attempts, SSRF blocking (loopback and
private IPs rejected), a real throwaway git repo, and a full round trip
through the actual MCP `call_tool()` protocol layer (not just the
underlying functions). Network tests mock `httpx` — no live network
access is required to run the suite.

## MCP client configuration

Exact configuration syntax depends on your specific client (Claude Code,
Claude Desktop, Cursor, etc.) — check that client's docs for where this
config file lives. The common shape (stdio, local) looks like:

```json
{
  "mcpServers": {
    "ubuntu-mcp": {
      "command": "/absolute/path/to/ubuntu-mcp-server/.venv/bin/python",
      "args": ["-m", "ubuntu_mcp"],
      "env": {
        "MCP_WORKSPACE": "/absolute/path/to/a/workspace/directory"
      }
    }
  }
}
```

Use absolute paths — the client launches this as its own subprocess, so
relative paths resolve against wherever the client happens to run from.

## Example prompts once connected

- "List everything in my workspace."
- "Read `notes.md` and summarize it."
- "How much CPU and memory is this machine using right now?"
- "Show me `git log` for the `api` project, last 5 commits."
- "Is `nginx` running?"
- "Fetch `https://example.com/status.json` and tell me what's in it."
- "Find all Python files under `src/` that mention `TODO`."
- "Convert `data.csv` to JSON."

## Remote deployment

**Local (default, recommended):**

```
AI Client  →  spawns this process directly  →  talks over stdio
```

No network port is opened. This is the safest mode and needs no
authentication of its own, because the client process owns the pipe.

**Remote (opt-in, `MCP_TRANSPORT=streamable-http`):**

```
AI Client  →  HTTPS  →  reverse proxy (TLS + auth)  →  Ubuntu MCP Server (streamable-http)  →  Ubuntu host
```

Running with `MCP_TRANSPORT=streamable-http` binds a plain HTTP port
with **no built-in authentication**. Do not expose that port to the
internet directly. Put it behind a reverse proxy (nginx, Caddy, etc.)
that terminates TLS and enforces auth, or keep it reachable only over a
private network / VPN / SSH tunnel. `deploy/ubuntu-mcp.service` is a
systemd template for running this mode as a background service:

```bash
sudo cp deploy/ubuntu-mcp.service /etc/systemd/system/ubuntu-mcp@.service
sudo systemctl daemon-reload
sudo systemctl enable --now ubuntu-mcp@yourusername
journalctl -u ubuntu-mcp@yourusername -f
```

(Only `streamable-http` mode makes sense as a systemd service — `stdio`
mode has no persistent process to supervise, since it's designed to be
spawned per-client-session.)

## Security model

1. **Filesystem sandbox** (`security.safe_path`): every path is resolved
   relative to `MCP_WORKSPACE`. `..` traversal and absolute paths that
   would land outside the workspace are rejected; an absolute-looking
   path like `/etc/passwd` is safely re-rooted *inside* the workspace
   rather than touching the real one.
2. **Network SSRF guard** (`security.assert_public_host`): `fetch_url`
   and `check_connectivity` resolve the target hostname and reject
   loopback, link-local, and RFC1918 private ranges unless you explicitly
   set `MCP_ALLOW_PRIVATE_NETWORK=true`.
3. **No arbitrary command execution**: git and systemd tools only ever
   invoke a fixed subcommand list via `asyncio.create_subprocess_exec`
   (never a shell string), with strictly validated arguments.
4. **Structured, leak-free errors**: every tool is wrapped by
   `@safe_tool`, which catches exceptions and returns
   `{"success": false, "error": {...}}` — never a raw traceback,
   environment variable, or secret.

## Troubleshooting

- **"No module named ubuntu_mcp"** — activate the venv (`source
  .venv/bin/activate`) or reinstall with `pip install -e .`.
- **`get_service_status` returns `available: false`** — `systemctl`
  isn't installed/available on this host (e.g. inside some containers);
  this is expected, not a bug.
- **`fetch_url` / `check_connectivity` raise a security error** — the
  target resolved to a private/loopback address; that's the SSRF guard
  working as intended. Set `MCP_ALLOW_PRIVATE_NETWORK=true` only if you
  trust the target and understand the tradeoff.
- **git tools say "not a git repository"** — the path must contain a
  `.git` directory; run `git init` there first.

## How to add a new tool

1. Implement the function in the relevant `tools/*.py` module (or a new
   module), following the existing pattern: `async def my_tool(...) ->
   dict`, raising one of the exceptions in `exceptions.py` on failure.
2. In `server.py`, add:

   ```python
   @mcp.tool()
   @safe_tool
   async def my_tool(arg: str) -> dict:
       """One-line summary.

       Args:
           arg: what it's for.
       """
       return await my_module.my_tool(arg)
   ```

3. Add tests in `tests/test_<module>.py` covering the happy path and at
   least one failure path.
4. Run `pytest -q`.

## Publish to Your Own GitHub Account

You can publish this entire project to your personal GitHub repository:

```bash
# 1. Initialize git in the project root (if not already done)
git init
git add .
git commit -m "feat: Ubuntu MCP Server with Web Console, Terminal & 38 Tools"

# 2. Add your GitHub remote repository
git remote add origin https://github.com/<your-username>/ubuntu-mcp-server.git
git branch -M main

# 3. Push to GitHub!
git push -u origin main
```

## Docker Deployment

Build and run in seconds with Docker:

```bash
docker compose up -d --build
```
Then visit `http://localhost:8000` for the Web Console & Terminal, and `http://localhost:8765/mcp` for the MCP endpoint.

## License

MIT — see `LICENSE`.

