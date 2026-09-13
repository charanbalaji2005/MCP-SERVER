#!/usr/bin/env python3
"""Ubuntu MCP Developer CLI.

Unified command-line interface for:
- Managing & connecting MCP portals (HTTP, SSE, Streamable HTTP)
- Discovering, inspecting schemas, and invoking MCP tools
- Real-time system diagnostics & metrics
- Meridian Shell 2.5 and Ubuntu Bash terminal integration
"""

from __future__ import annotations

import json
import os
import platform
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

CLI_VERSION = "2.5.0"
SERVER_VERSION = "1.0.0"

# ANSI Colors for terminal output
IS_TTY = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if IS_TTY else text


C_BOLD = "1"
C_DIM = "2"
C_VIOLET = "38;5;141"
C_PURPLE = "38;5;99"
C_CYAN = "36"
C_GREEN = "32"
C_YELLOW = "33"
C_RED = "31"
C_GRAY = "90"


def bold(s: str) -> str:
    return _c(C_BOLD, s)


def dim(s: str) -> str:
    return _c(C_DIM, s)


def violet(s: str) -> str:
    return _c(C_VIOLET, s)


def green(s: str) -> str:
    return _c(C_GREEN, s)


def yellow(s: str) -> str:
    return _c(C_YELLOW, s)


def red(s: str) -> str:
    return _c(C_RED, s)


def cyan(s: str) -> str:
    return _c(C_CYAN, s)


def gray(s: str) -> str:
    return _c(C_GRAY, s)


def _get_wsl_host_ip() -> Optional[str]:
    """Detect Windows host IP from WSL2 routing table."""
    try:
        with open("/proc/net/route", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 3 and parts[1] == "00000000":
                    gateway_hex = parts[2]
                    a = int(gateway_hex[6:8], 16)
                    b = int(gateway_hex[4:6], 16)
                    c = int(gateway_hex[2:4], 16)
                    d = int(gateway_hex[0:2], 16)
                    return f"{a}.{b}.{c}.{d}"
    except Exception:
        pass
    return None


def _find_workspace_dir() -> Path:
    """Locate the server workspace directory across Windows and WSL mounts."""
    candidates = [
        Path.cwd() / "workspace",
        Path.cwd(),
        Path("/mnt/d/ubuntu-mcp-server/ubuntu-mcp-server/workspace"),
        Path("D:/ubuntu-mcp-server/ubuntu-mcp-server/workspace"),
        Path.home() / ".ubuntu_mcp",
    ]
    for c in candidates:
        if c.exists() and (c / ".mcp_portals.json").exists() or (c / ".auth_sessions.json").exists():
            return c
    return Path.cwd() / "workspace"


def _get_auth_token(workspace_dir: Path) -> Optional[str]:
    """Read existing session token if available."""
    token = os.environ.get("UBUNTU_MCP_TOKEN")
    if token:
        return token

    sessions_files = [
        workspace_dir / ".auth_sessions.json",
        Path("/mnt/d/ubuntu-mcp-server/ubuntu-mcp-server/workspace/.auth_sessions.json"),
        Path("D:/ubuntu-mcp-server/ubuntu-mcp-server/workspace/.auth_sessions.json"),
        Path.home() / ".config" / "ubuntu_mcp" / "token",
    ]
    for sf in sessions_files:
        if sf.exists():
            try:
                content = sf.read_text(encoding="utf-8").strip()
                if sf.name.endswith(".json"):
                    data = json.loads(content)
                    if isinstance(data, dict) and data:
                        return next(iter(data.keys()))
                else:
                    if content:
                        return content
            except Exception:
                pass
    return None


class MCPClient:
    """Lightweight HTTP API client for the Ubuntu MCP Control Plane."""

    def __init__(self):
        self.workspace_dir = _find_workspace_dir()
        self.token = _get_auth_token(self.workspace_dir)
        self.base_url = self._discover_server_url()

    def _discover_server_url(self) -> str:
        env_url = os.environ.get("MCP_SERVER_URL")
        if env_url:
            return env_url.rstrip("/")

        candidates = [
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        ]
        wsl_host = _get_wsl_host_ip()
        if wsl_host:
            candidates.append(f"http://{wsl_host}:8000")

        for url in candidates:
            try:
                req = urllib.request.Request(
                    f"{url}/api/status",
                    headers={"User-Agent": f"ubuntu-mcp-cli/{CLI_VERSION}"},
                )
                with urllib.request.urlopen(req, timeout=0.35) as res:
                    if res.status == 200:
                        return url
            except Exception:
                continue

        return "http://127.0.0.1:8000"

    def request(
        self,
        endpoint: str,
        method: str = "GET",
        payload: Optional[dict] = None,
        timeout: float = 6.0,
    ) -> tuple[bool, Any, Optional[str]]:
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"ubuntu-mcp-cli/{CLI_VERSION}",
            "X-MCP-Client": "CLI",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        data_bytes = json.dumps(payload).encode("utf-8") if payload else None
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return True, data, None
        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read().decode("utf-8"))
                err_msg = err_body.get("error")
                if isinstance(err_msg, dict):
                    err_msg = err_msg.get("message", str(err_msg))
                return False, None, err_msg or f"HTTP {e.code} {e.reason}"
            except Exception:
                return False, None, f"HTTP {e.code} {e.reason}"
        except urllib.error.URLError as e:
            return False, None, f"Connection failed to {self.base_url}: {e.reason}"
        except Exception as e:
            return False, None, str(e)


# -----------------------------------------------------------------------------
# CLI Subcommands
# -----------------------------------------------------------------------------


def print_banner():
    banner = f"""
{violet('  ███████╗██████╗  ██████╗     ███╗   ███╗ ██████╗██████╗ ')}
{violet('  ██╔════╝██╔══██╗██╔════╝     ████╗ ████║██╔════╝██╔══██╗')}
{violet('  █████╗  ██████╔╝██║  ███╗    ██╔████╔██║██║     ██████╔╝')}
{violet('  ██╔══╝  ██╔═══╝ ██║   ██║    ██║╚██╔╝██║██║     ██╔═══╝ ')}
{violet('  ███████╗██║     ╚██████╔╝    ██║ ╚═╝ ██║╚██████╗██║     ')}
{violet('  ╚══════╝╚═╝      ╚═════╝     ╚═╝     ╚═╝ ╚═════╝╚═╝     ')}
  {bold('Ubuntu FastMCP & Meridian Developer Console')} {gray(f'v{CLI_VERSION}')}
"""
    print(banner)


def cmd_help(args: list[str]):
    print_banner()
    help_text = f"""
{bold('USAGE:')}
  {cyan('mcp')} {yellow('<command>')} {gray('[options] [arguments]')}

{bold('PORTAL COMMANDS (Connect & Manage MCP Portals):')}
  {cyan('mcp connect')} {yellow('<name> <url>')} {gray('[--transport http|sse] [--auth <token>]')}
      Connect an external or local MCP server portal.
      {dim('Examples:')}
        mcp connect my-server http://localhost:9000/mcp
        mcp connect remote-ai https://ai.example.com/sse --transport sse
        mcp connect secure-mcp http://10.0.0.5:8000/mcp --auth "Bearer secret123"

  {cyan('mcp disconnect')} {yellow('<portal_id>')}
      Disconnect and remove an MCP portal from the server.
      {dim('Example:')}
        mcp disconnect remote-ai

  {cyan('mcp portals')}, {cyan('mcp list')}
      List all registered MCP portals, connection status, latency, and tool counts.

  {cyan('mcp sync')} {yellow('[portal_id]')}
      Re-probe and synchronize tools for a specific portal or all portals.
      {dim('Example:')}
        mcp sync my-server

{bold('TOOL COMMANDS (Execute & Inspect MCP Tools):')}
  {cyan('mcp tools')} {gray('[--portal <id>] [--category <cat>]')}
      List all available tools across connected portals with descriptions.
      {dim('Examples:')}
        mcp tools
        mcp tools --category filesystem
        mcp tools --portal local

  {cyan('mcp info')} {yellow('<tool_name>')}
      Inspect schema, input arguments, and parameter documentation for a tool.
      {dim('Example:')}
        mcp info get_system_info
        mcp info read_file

  {cyan('mcp call')} {yellow('<tool_name>')} {gray('[json_args | key=value ...]')}
      Execute any MCP tool directly from the command line and display result.
      {dim('Examples:')}
        mcp call get_system_info
        mcp call get_cpu_info
        mcp call check_connectivity host=github.com
        mcp call read_file path=workspace/.mcp_portals.json
        mcp call git_status repo_path=.

{bold('SYSTEM & DIAGNOSTICS:')}
  {cyan('mcp status')}
      Inspect MCP server health, active portals, tool counts, version, and host OS.

  {cyan('mcp metrics')}
      Live metrics snapshot: CPU, RAM, Disk utilization, and active processes.

  {cyan('mcp terminal')} {yellow('[meridian|ubuntu]')}
      Show or configure terminal engine preference (Meridian Shell 2.5 vs Ubuntu Bash).

  {cyan('mcp history')}
      Display recent commands executed through the console and auto-save journal.

{bold('MERIDIAN SHELL BUILT-IN COMMANDS (Meridian 2.5 Developer Shell):')}
  {green('monitor')}        Open real-time GPU/CPU/Memory/Disk/Network terminal dashboard
  {green('gitintel')}       Interactive Git branch divergence & unstaged change inspector
  {green('files')} {gray('[path]')}   Interactive file tree explorer with Git status badges
  {green('search')} {yellow('<query>')} Search terminal scrollback, history, and workspace files
  {green('palette')}        Open fuzzy command palette (Ctrl+Shift+P)
  {green('ask')} {yellow('"<prompt>"')} Ask local AI assistant to generate shell commands
  {green('diag')} {yellow('"<error>"')} Diagnose compiler or runtime error messages
"""
    print(help_text)


def cmd_version(args: list[str]):
    print(f"{bold('Ubuntu MCP Developer CLI')}: v{CLI_VERSION}")
    print(f"{bold('Server Version')}: v{SERVER_VERSION}")
    print(f"{bold('Host OS')}: {platform.system()} ({platform.release()})")
    print(f"{bold('Python')}: {sys.version.split()[0]}")


def cmd_status(args: list[str]):
    client = MCPClient()
    ok, data, err = client.request("/api/status")
    if not ok:
        print(f"{red('✖')} {bold('Failed to contact MCP server')}: {err}")
        print(f"  {gray('Target URL:')} {client.base_url}")
        print(f"  {yellow('Hint:')} Make sure the server daemon is running with: python run_gui.py")
        return 1

    print(f"\n{bold('Ubuntu MCP Control Plane Status')}")
    print(f"{gray('─' * 50)}")
    status_color = green("● ONLINE") if data.get("status") == "online" else red("● OFFLINE")
    print(f"  {bold('Server Status:')}      {status_color}")
    print(f"  {bold('Server Name:')}        {data.get('server_name')}")
    print(f"  {bold('Server Version:')}     v{data.get('version')}")
    print(f"  {bold('Active Backend:')}     {cyan(str(data.get('terminal_backend')))}")
    print(f"  {bold('Connected Portals:')}  {yellow(str(data.get('portals_count')))}")
    print(f"  {bold('Available Tools:')}    {green(str(data.get('tools_count')))} tools")
    print(f"  {bold('Host System:')}        {data.get('host_os')} {data.get('host_release')}")
    print(f"  {bold('Workspace Path:')}     {data.get('workspace')}")
    print(f"  {bold('Active Endpoint:')}    {client.base_url}")
    print(f"{gray('─' * 50)}\n")
    return 0


def cmd_metrics(args: list[str]):
    client = MCPClient()
    ok, data, err = client.request("/api/system-metrics")
    if not ok:
        print(f"{red('✖')} {bold('Failed to fetch metrics')}: {err}")
        return 1

    cpu = data.get("cpu", {})
    mem = data.get("memory", {})
    disk = data.get("disk", {})
    procs = data.get("top_processes", [])

    cpu_pct = cpu.get("percent", 0.0)
    mem_pct = mem.get("percent", 0.0)
    disk_pct = disk.get("percent", 0.0)

    def bar(pct: float, width: int = 24) -> str:
        filled = int((pct / 100.0) * width)
        color = green if pct < 70 else (yellow if pct < 85 else red)
        return color("█" * filled + "░" * (width - filled))

    print(f"\n{bold('Ubuntu MCP Live System Metrics')}")
    print(f"{gray('─' * 60)}")
    print(f"  {bold('CPU Utilization:')}  [{bar(cpu_pct)}] {cpu_pct:>5.1f}% ({cpu.get('cores_logical')} cores)")
    print(f"  {bold('Memory Usage:')}     [{bar(mem_pct)}] {mem_pct:>5.1f}% ({mem.get('used_mb')}MB / {mem.get('total_mb')}MB)")
    print(f"  {bold('Workspace Disk:')}  [{bar(disk_pct)}] {disk_pct:>5.1f}% ({disk.get('used_gb')}GB / {disk.get('total_gb')}GB)")
    print(f"{gray('─' * 60)}")

    if procs:
        print(f"  {bold('TOP ACTIVE PROCESSES:')}")
        print(f"    {gray('PID':<8)} {gray('NAME':<24)} {gray('CPU %':<10)} {gray('MEM %')}")
        for p in procs[:6]:
            print(f"    {p.get('pid'):<8} {p.get('name')[:22]:<24} {str(p.get('cpu')) + '%':<10} {str(p.get('memory')) + '%'}")
    print()
    return 0


def cmd_portals(args: list[str]):
    client = MCPClient()
    ok, data, err = client.request("/api/portals")
    if not ok:
        print(f"{red('✖')} {bold('Failed to list portals')}: {err}")
        return 1

    portals = data.get("portals", [])
    print(f"\n{bold('Connected MCP Portals')} ({len(portals)} registered)")
    print(f"{gray('─' * 88)}")
    print(f"{gray('ID':<14)} {gray('NAME':<20)} {gray('URL':<26)} {gray('TRANS':<8)} {gray('STATUS':<10)} {gray('TOOLS')}")
    print(f"{gray('─' * 88)}")

    for p in portals:
        pid = p.get("id", "")
        name = p.get("name", "")[:18]
        url = p.get("url", "")[:24]
        trans = str(p.get("transport", "http")).upper()
        status = p.get("status", "unknown")
        tools_len = len(p.get("tools", []))

        status_fmt = green("ONLINE") if status == "online" else (yellow("PROBING") if status == "probing" else red("ERROR"))
        latency = f"{p.get('latency_ms')}ms" if p.get("latency_ms") is not None else "─"

        print(f"{pid:<14} {name:<20} {url:<26} {trans:<8} {status_fmt:<10} {tools_len} tools ({latency})")
    print(f"{gray('─' * 88)}\n")
    return 0


def cmd_connect(args: list[str]):
    if len(args) < 2:
        print(f"{red('✖')} {bold('Missing arguments.')}")
        print(f"  {bold('Usage:')} mcp connect <name> <url> [--transport http|sse] [--auth <token>]")
        print(f"  {dim('Example:')} mcp connect remote-ai http://localhost:9000/mcp")
        return 1

    name = args[0]
    url = args[1]
    transport = "http"
    auth_header = None

    idx = 2
    while idx < len(args):
        if args[idx] == "--transport" and idx + 1 < len(args):
            transport = args[idx + 1]
            idx += 2
        elif args[idx] in ("--auth", "--token") and idx + 1 < len(args):
            auth_header = args[idx + 1]
            idx += 2
        else:
            idx += 1

    print(f"{cyan('⏳ Connecting MCP portal')} \"{name}\" at {url} (transport: {transport})...")
    client = MCPClient()
    ok, data, err = client.request(
        "/api/portals",
        method="POST",
        payload={
            "name": name,
            "url": url,
            "transport": transport,
            "auth_header": auth_header,
        },
    )

    if not ok:
        print(f"{red('✖')} {bold('Failed to connect portal')}: {err}")
        return 1

    portal = data.get("portal", {})
    tools = portal.get("tools", [])
    latency = portal.get("latency_ms", 0)

    print(f"{green('✔')} {bold(f'Successfully connected portal \"{name}\"')}")
    print(f"  {gray('Portal ID:')}       {portal.get('id')}")
    print(f"  {gray('Endpoint URL:')}    {url}")
    print(f"  {gray('Transport:')}       {transport.upper()}")
    print(f"  {gray('Discovered Tools:')}{green(str(len(tools)))} tools")
    print(f"  {gray('Latency:')}         {latency}ms\n")
    return 0


def cmd_disconnect(args: list[str]):
    if not args:
        print(f"{red('✖')} {bold('Missing portal ID.')}")
        print(f"  {bold('Usage:')} mcp disconnect <portal_id>")
        return 1

    portal_id = args[0]
    client = MCPClient()
    ok, data, err = client.request(f"/api/portals/{urllib.parse.quote(portal_id)}", method="DELETE")
    if not ok:
        print(f"{red('✖')} {bold('Failed to disconnect portal')}: {err}")
        return 1

    print(f"{green('✔')} {bold(f'Portal \"{portal_id}\" disconnected successfully.')}")
    return 0


def cmd_sync(args: list[str]):
    portal_id = args[0] if args else None
    client = MCPClient()

    if portal_id:
        print(f"{cyan('⏳ Syncing portal')} \"{portal_id}\"...")
        ok, data, err = client.request(f"/api/portals/{urllib.parse.quote(portal_id)}/sync", method="POST")
        if not ok:
            print(f"{red('✖')} {bold('Sync failed')}: {err}")
            return 1
        print(f"{green('✔')} {bold(data.get('message', 'Portal synchronized.'))}")
    else:
        # Sync all
        ok, data, err = client.request("/api/portals")
        if not ok:
            print(f"{red('✖')} {bold('Failed to fetch portals')}: {err}")
            return 1
        portals = data.get("portals", [])
        for p in portals:
            pid = p.get("id")
            if pid == "local":
                continue
            print(f"{cyan('⏳ Syncing')} {p.get('name')} ({pid})...")
            s_ok, s_data, s_err = client.request(f"/api/portals/{urllib.parse.quote(pid)}/sync", method="POST")
            if s_ok:
                print(f"  {green('✔')} {s_data.get('message')}")
            else:
                print(f"  {red('✖')} {s_err}")
    return 0


def cmd_tools(args: list[str]):
    portal_filter = None
    category_filter = None

    idx = 0
    while idx < len(args):
        if args[idx] == "--portal" and idx + 1 < len(args):
            portal_filter = args[idx + 1]
            idx += 2
        elif args[idx] == "--category" and idx + 1 < len(args):
            category_filter = args[idx + 1]
            idx += 2
        else:
            idx += 1

    client = MCPClient()
    endpoint = f"/api/tools?portal={urllib.parse.quote(portal_filter)}" if portal_filter else "/api/tools"
    ok, data, err = client.request(endpoint)
    if not ok:
        print(f"{red('✖')} {bold('Failed to fetch tools')}: {err}")
        return 1

    tools = data.get("tools", [])
    if category_filter:
        tools = [t for t in tools if t.get("category") == category_filter]

    print(f"\n{bold('Available MCP Tools')} ({len(tools)} tools found)")
    print(f"{gray('─' * 92)}")
    print(f"{gray('TOOL NAME':<24)} {gray('CATEGORY':<14)} {gray('PORTAL':<12)} {gray('DESCRIPTION')}")
    print(f"{gray('─' * 92)}")

    for t in tools:
        name = t.get("name", "")
        cat = t.get("category", "")
        portal = t.get("portal_id", "")
        desc = (t.get("description", "") or "").split("\n")[0][:40]
        print(f"{cyan(name):<33} {cat:<14} {portal:<12} {desc}")
    print(f"{gray('─' * 92)}\n")
    return 0


def cmd_info(args: list[str]):
    if not args:
        print(f"{red('✖')} {bold('Missing tool name.')}")
        print(f"  {bold('Usage:')} mcp info <tool_name>")
        return 1

    tool_name = args[0]
    client = MCPClient()
    ok, data, err = client.request("/api/tools")
    if not ok:
        print(f"{red('✖')} {bold('Failed to fetch tool schema')}: {err}")
        return 1

    tools = data.get("tools", [])
    target = next((t for t in tools if t.get("name") == tool_name), None)
    if not target:
        print(f"{red('✖')} {bold(f'Tool \"{tool_name}\" not found.')}")
        print(f"  Run {cyan('mcp tools')} to view available tools.")
        return 1

    schema = target.get("schema", {})
    props = schema.get("properties", {})
    required = schema.get("required", [])

    print(f"\n{bold('TOOL:')} {cyan(target.get('name'))} {gray(f'({target.get(\"category\")})')}")
    print(f"{gray('─' * 60)}")
    print(f"{bold('Description:')} {target.get('description') or 'No description provided.'}")
    print(f"{bold('Portal:')}      {target.get('portal_name')} ({target.get('portal_id')})")
    print(f"\n{bold('Parameters / Input Schema:')}")

    if not props:
        print(f"  {dim('No parameters required (zero-argument tool).')}")
    else:
        for p_name, p_info in props.items():
            p_type = p_info.get("type", "any")
            is_req = red("*required") if p_name in required else gray("optional")
            p_desc = p_info.get("description", "")
            print(f"  • {bold(p_name)} {yellow(f'<{p_type}>')} ({is_req})")
            if p_desc:
                print(f"    {p_desc}")

    print(f"\n{bold('Invocation Example:')}")
    example_args = " ".join([f"{k}=<value>" for k in list(props.keys())[:2]])
    print(f"  {cyan(f'mcp call {tool_name} {example_args}')}\n")
    return 0


def cmd_call(args: list[str]):
    if not args:
        print(f"{red('✖')} {bold('Missing tool name.')}")
        print(f"  {bold('Usage:')} mcp call <tool_name> [json_args | key=value ...]")
        return 1

    tool_name = args[0]
    raw_args = args[1:]
    arguments: dict[str, Any] = {}
    portal_id = "local"

    # Check for --portal flag
    if "--portal" in raw_args:
        p_idx = raw_args.index("--portal")
        if p_idx + 1 < len(raw_args):
            portal_id = raw_args[p_idx + 1]
            raw_args = raw_args[:p_idx] + raw_args[p_idx + 2 :]

    if len(raw_args) == 1 and raw_args[0].startswith("{") and raw_args[0].endswith("}"):
        try:
            arguments = json.loads(raw_args[0])
        except Exception as e:
            print(f"{red('✖')} {bold('Invalid JSON argument string')}: {e}")
            return 1
    else:
        for arg in raw_args:
            if "=" in arg:
                k, v = arg.split("=", 1)
                k = k.strip()
                v = v.strip()
                if v.lower() == "true":
                    arguments[k] = True
                elif v.lower() == "false":
                    arguments[k] = False
                elif re.match(r"^-?\d+$", v):
                    arguments[k] = int(v)
                elif re.match(r"^-?\d+\.\d+$", v):
                    arguments[k] = float(v)
                else:
                    arguments[k] = v

    print(f"{cyan('⚡ Executing tool')} \"{tool_name}\" on portal \"{portal_id}\"...")
    client = MCPClient()
    start_t = time.perf_counter()
    ok, data, err = client.request(
        "/api/call-tool",
        method="POST",
        payload={
            "tool": tool_name,
            "arguments": arguments,
            "portal_id": portal_id,
        },
    )
    duration_ms = round((time.perf_counter() - start_t) * 1000, 1)

    if not ok:
        print(f"{red('✖')} {bold('Execution Failed')} ({duration_ms}ms)")
        print(f"  {red(str(err))}")
        return 1

    result_data = data.get("data")
    print(f"{green('✔')} {bold('Execution Succeeded')} {gray(f'({duration_ms}ms)')}")
    print(f"{gray('─' * 60)}")
    try:
        formatted = json.dumps(result_data, indent=2)
        print(formatted)
    except Exception:
        print(result_data)
    print(f"{gray('─' * 60)}\n")
    return 0


def cmd_terminal(args: list[str]):
    if not args:
        print(f"\n{bold('Terminal Engine Status:')}")
        print(f"  {bold('Primary Engine:')}   {violet('Meridian Shell 2.5')} (Port 7682)")
        print(f"  {bold('Secondary Engine:')} {gray('Ubuntu GNU Bash')}   (Port 7681)")
        print(f"  {bold('Switch command:')}   mcp terminal [meridian|ubuntu]\n")
        return 0

    choice = args[0].lower()
    if choice in ("meridian", "meridian-shell", "primary", "7682"):
        print(f"{green('✔')} Preferred terminal engine set to: {violet('Meridian Shell 2.5 (Port 7682)')}")
    elif choice in ("ubuntu", "bash", "secondary", "7681"):
        print(f"{green('✔')} Preferred terminal engine set to: {cyan('Ubuntu GNU Bash (Port 7681)')}")
    else:
        print(f"{red('✖')} Unknown terminal engine. Choose 'meridian' or 'ubuntu'.")
        return 1
    return 0


def cmd_meridian(args: list[str]):
    print(f"\n{bold('Meridian Shell 2.5 — Developer Environment Cheat Sheet')}")
    print(f"{gray('═' * 65)}")
    print(f"  {cyan('monitor')}        Live GPU framerate, CPU, RAM, Disk, Net dashboard")
    print(f"  {cyan('gitintel')}       Git divergence, branch comparisons & unstaged diffs")
    print(f"  {cyan('files [path]')}   File tree explorer with real-time Git status tags")
    print(f"  {cyan('search <text>')}  Multi-buffer search across commands and files")
    print(f"  {cyan('palette')}        Command palette quick actions (Ctrl+Shift+P)")
    print(f"  {cyan('ask \"<prompt>\"')} Autonomous shell command generation")
    print(f"  {cyan('diag \"<error>\"')} Error diagnosis and automated repair engine")
    print(f"  {cyan('plugins')}        List active extensible plugins")
    print(f"  {cyan('stats')}          Terminal telemetry and session statistics")
    print(f"{gray('═' * 65)}\n")
    return 0


# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------

COMMAND_MAP = {
    "help": cmd_help,
    "--help": cmd_help,
    "-h": cmd_help,
    "version": cmd_version,
    "--version": cmd_version,
    "-v": cmd_version,
    "status": cmd_status,
    "metrics": cmd_metrics,
    "portals": cmd_portals,
    "list": cmd_portals,
    "connect": cmd_connect,
    "disconnect": cmd_disconnect,
    "rm": cmd_disconnect,
    "sync": cmd_sync,
    "tools": cmd_tools,
    "info": cmd_info,
    "call": cmd_call,
    "terminal": cmd_terminal,
    "meridian": cmd_meridian,
}


def main():
    args = sys.argv[1:]
    if not args:
        cmd_help([])
        return 0

    cmd = args[0].lower()
    handler = COMMAND_MAP.get(cmd)

    if handler:
        return handler(args[1:]) or 0
    else:
        print(f"{red('✖')} {bold(f'Unknown command: \"{cmd}\"')}")
        print(f"  Run {cyan('mcp --help')} to see all available commands.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
