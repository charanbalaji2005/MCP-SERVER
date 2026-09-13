"""Ubuntu MCP Server Web GUI, Interactive Terminal & MCP Portals Hub.

Provides:
- User onboarding / Registration (First-time setup)
- Device & Local Storage permission consent dialog & tracking
- Authentication (PBKDF2-HMAC-SHA256, session tokens)
- MCP Portals Hub (Register, aggregate, and browse multiple external MCP servers)
- Protected WebSocket endpoint (/ws/terminal) bridging xterm.js to Ubuntu/WSL bash
- REST API (/api/tools, /api/call-tool, /api/system-metrics, /api/status, /api/auth/*, /api/portals/*)
- Static files for the web dashboard & terminal interface
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psutil
import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

from ..config import SETTINGS
from ..server import mcp
from .auth import AUTH
from .portals import PORTALS

STATIC_DIR = Path(__file__).parent / "static"

TOOL_CATEGORIES: dict[str, str] = {
    "get_system_info": "system",
    "get_cpu_info": "system",
    "get_memory_info": "system",
    "get_disk_info": "system",
    "list_processes": "system",
    "get_service_status": "system",
    "read_file": "filesystem",
    "write_file": "filesystem",
    "append_file": "filesystem",
    "delete_file": "filesystem",
    "copy_file": "filesystem",
    "move_file": "filesystem",
    "file_exists": "filesystem",
    "get_file_info": "filesystem",
    "list_directory": "directories",
    "create_directory": "directories",
    "delete_directory": "directories",
    "directory_exists": "directories",
    "find_files": "directories",
    "get_directory_size": "directories",
    "fetch_url": "network",
    "check_connectivity": "network",
    "resolve_dns": "network",
    "validate_url": "network",
    "parse_url": "network",
    "build_url": "network",
    "git_status": "git",
    "git_log": "git",
    "git_diff": "git",
    "git_branches": "git",
    "git_current_branch": "git",
    "detect_project_type": "code",
    "search_text_in_files": "code",
    "count_words": "code",
    "format_json": "code",
    "validate_json": "code",
    "csv_to_json": "code",
    "csv_get_columns": "code",
}


def _get_bearer_token(request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return request.query_params.get("token")


def _detect_terminal_command(shell: str = "meridian") -> tuple[list[str], str]:
    is_win = platform.system() == "Windows"
    workspace_str = "/mnt/d/ubuntu-mcp-server/ubuntu-mcp-server/workspace"
    if is_win:
        wsl_path = shutil.which("wsl.exe") or "C:\\Windows\\System32\\wsl.exe"
        if os.path.exists(wsl_path):
            if shell == "bash":
                return [wsl_path, "-d", "Ubuntu", "--cd", workspace_str, "--", "bash", "-i"], "Ubuntu WSL Bash (Secondary)"
            return [wsl_path, "-d", "Ubuntu", "--cd", workspace_str, "--", "/usr/local/bin/meridian-shell"], "Meridian Shell 2.5 (Primary)"
        return ["powershell.exe", "-NoLogo"], "PowerShell (Windows Fallback)"
    else:
        if shell == "bash":
            bash_path = shutil.which("bash") or "/bin/bash"
            return [bash_path], "Native Linux (Bash)"
        meridian_path = shutil.which("meridian-shell") or "/usr/local/bin/meridian-shell"
        return [meridian_path], "Meridian Shell 2.5 (Primary)"


def _ensure_ttyd_daemons():
    import socket

    def is_port_open(port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.4)
                return s.connect_ex(("127.0.0.1", port)) == 0
        except Exception:
            return False

    is_win = platform.system() == "Windows"
    if is_win:
        wsl_path = shutil.which("wsl.exe") or "C:\\Windows\\System32\\wsl.exe"
        if not os.path.exists(wsl_path):
            return

        workspace_wsl = "/mnt/d/ubuntu-mcp-server/ubuntu-mcp-server/workspace"
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        # 1. Primary Terminal: Meridian Shell on Port 7682
        if not is_port_open(7682):
            try:
                subprocess.Popen(
                    [
                        wsl_path, "-d", "Ubuntu", "-u", "root", "--cd", workspace_wsl,
                        "--", "ttyd", "-W", "-p", "7682",
                        "-t", "fontSize=15", "-t", "cursorBlink=true", "-t", "cursorStyle=block",
                        "-t", "theme={'background':'#0a0e17'}",
                        "/usr/local/bin/meridian-shell",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                )
            except Exception:
                pass

        # 2. Secondary Terminal: Ubuntu Bash on Port 7681 (with auto-save history enabled)
        if not is_port_open(7681):
            try:
                subprocess.Popen(
                    [
                        wsl_path, "-d", "Ubuntu", "-u", "root", "--cd", workspace_wsl,
                        "--", "ttyd", "-W", "-p", "7681",
                        "-t", "fontSize=15", "-t", "cursorBlink=true", "-t", "cursorStyle=block",
                        "-t", "theme={'background':'#06090e'}",
                        "bash", "-i",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                )
            except Exception:
                pass


async def api_auth_status(request):
    """Check if first-time user setup is required."""
    setup_required = not AUTH.is_setup_completed()
    return JSONResponse(
        {
            "setup_required": setup_required,
            "storage_path": str(SETTINGS.workspace_root),
        }
    )


async def api_auth_register(request):
    """Register initial user and record local storage permission."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"success": False, "error": "Invalid JSON body"}, status_code=400)

    username = body.get("username", "")
    password = body.get("password", "")
    storage_perm = body.get("storage_permission", False)

    if not storage_perm:
        return JSONResponse(
            {"success": False, "error": "You must grant storage access permission to proceed."},
            status_code=400,
        )

    ok, msg, token = AUTH.register(username, password, storage_permission=storage_perm)
    if not ok:
        return JSONResponse({"success": False, "error": msg}, status_code=400)

    return JSONResponse(
        {
            "success": True,
            "message": msg,
            "token": token,
            "user": {
                "username": username.strip().lower(),
                "storage_permission_granted": True,
            },
        }
    )


async def api_auth_login(request):
    """Authenticate returning user."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"success": False, "error": "Invalid JSON body"}, status_code=400)

    username = body.get("username", "")
    password = body.get("password", "")

    ok, msg, token = AUTH.authenticate(username, password)
    if not ok:
        return JSONResponse({"success": False, "error": msg}, status_code=401)

    user = AUTH.validate_session(token)
    return JSONResponse(
        {
            "success": True,
            "message": msg,
            "token": token,
            "user": {
                "username": user.username if user else username,
                "storage_permission_granted": user.storage_permission_granted if user else True,
            },
        }
    )


async def api_auth_me(request):
    """Validate current session token."""
    token = _get_bearer_token(request)
    user = AUTH.validate_session(token)
    if not user:
        return JSONResponse({"authenticated": False}, status_code=401)
    return JSONResponse(
        {
            "authenticated": True,
            "user": {
                "username": user.username,
                "storage_permission_granted": user.storage_permission_granted,
                "created_at_utc": user.created_at_utc,
            },
        }
    )


async def api_auth_logout(request):
    """Revoke session token."""
    token = _get_bearer_token(request)
    if token:
        AUTH.revoke_session(token)
    return JSONResponse({"success": True, "message": "Logged out successfully."})


async def api_portals_list(request):
    """List all registered MCP portals."""
    portals = await PORTALS.list_portals()
    return JSONResponse({"success": True, "portals": portals})


async def api_portals_add(request):
    """Register and probe a new external MCP portal."""
    if AUTH.is_setup_completed():
        token = _get_bearer_token(request)
        if not AUTH.validate_session(token):
            return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"success": False, "error": "Invalid JSON body"}, status_code=400)

    name = body.get("name", "")
    url = body.get("url", "")
    transport = body.get("transport", "streamable-http")
    auth_header = body.get("auth_header")

    ok, msg, portal_data = await PORTALS.add_portal(name, url, transport, auth_header)
    if not ok:
        return JSONResponse({"success": False, "error": msg}, status_code=400)

    return JSONResponse({"success": True, "message": msg, "portal": portal_data})


async def api_portals_sync(request):
    """Re-probe and refresh tools from a specific portal."""
    portal_id = request.path_params.get("portal_id")
    ok, msg, portal_data = await PORTALS.sync_portal(portal_id)
    if not ok:
        return JSONResponse({"success": False, "error": msg, "portal": portal_data}, status_code=400)
    return JSONResponse({"success": True, "message": msg, "portal": portal_data})


async def api_portals_delete(request):
    """Remove a custom MCP portal."""
    if AUTH.is_setup_completed():
        token = _get_bearer_token(request)
        if not AUTH.validate_session(token):
            return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    portal_id = request.path_params.get("portal_id")
    ok, msg = PORTALS.delete_portal(portal_id)
    if not ok:
        return JSONResponse({"success": False, "error": msg}, status_code=400)
    return JSONResponse({"success": True, "message": msg})


async def api_status(request):
    """Return status and host information."""
    cmd, term_label = _detect_terminal_command()
    tools = await mcp.list_tools()
    portals = await PORTALS.list_portals()
    return JSONResponse(
        {
            "status": "online",
            "server_name": "Ubuntu MCP Server",
            "version": "1.0.0",
            "terminal_backend": term_label,
            "host_os": platform.system(),
            "host_release": platform.release(),
            "tools_count": len(tools),
            "portals_count": len(portals),
            "workspace": str(SETTINGS.workspace_root),
            "transport": SETTINGS.transport,
            "auth_enabled": True,
            "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )


async def api_tools(request):
    """List all tools across all connected portals (or filter by portal_id)."""
    filter_portal = request.query_params.get("portal")
    portals = await PORTALS.list_portals()
    result = []

    if not filter_portal or filter_portal == "local":
        local_tools = await mcp.list_tools()
        for t in local_tools:
            cat = TOOL_CATEGORIES.get(t.name, "general")
            schema = t.input_schema if hasattr(t, "input_schema") else {}
            result.append(
                {
                    "portal_id": "local",
                    "portal_name": "Ubuntu MCP Server",
                    "name": t.name,
                    "category": cat,
                    "description": t.description or "",
                    "schema": schema,
                }
            )

    for p in portals:
        if p["id"] == "local":
            continue
        if filter_portal and filter_portal != p["id"]:
            continue
        for t in p.get("tools", []):
            result.append(
                {
                    "portal_id": p["id"],
                    "portal_name": p["name"],
                    "name": t["name"],
                    "category": "remote",
                    "description": t.get("description", ""),
                    "schema": t.get("schema", {}),
                }
            )

    return JSONResponse({"success": True, "tools": result})


async def api_call_tool(request):
    """Execute any of the MCP tools (supports multi-portal dispatch)."""
    if AUTH.is_setup_completed():
        token = _get_bearer_token(request)
        user = AUTH.validate_session(token)
        if not user:
            return JSONResponse(
                {"success": False, "error": {"message": "Unauthorized. Please sign in."}},
                status_code=401,
            )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"message": "Invalid JSON body"}},
            status_code=400,
        )

    tool_name = body.get("tool")
    args = body.get("arguments", {})
    portal_id = body.get("portal_id", "local")

    if not tool_name:
        return JSONResponse(
            {"success": False, "error": {"message": "Missing 'tool' parameter"}},
            status_code=400,
        )

    ok, data, duration_ms, err = await PORTALS.call_tool(portal_id, tool_name, args)
    return JSONResponse(
        {
            "success": ok,
            "portal_id": portal_id,
            "tool": tool_name,
            "duration_ms": duration_ms,
            "data": data,
            "error": None if ok else {"message": err or "Execution failed"},
        },
        status_code=200 if ok else 500,
    )


async def api_system_metrics(request):
    """Get live CPU, memory, disk, and process stats."""
    if AUTH.is_setup_completed():
        token = _get_bearer_token(request)
        if not AUTH.validate_session(token):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        cpu_pct = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(str(SETTINGS.workspace_root))

        top_procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                top_procs.append(
                    {
                        "pid": p.info["pid"],
                        "name": p.info["name"],
                        "cpu": round(p.info["cpu_percent"] or 0.0, 1),
                        "memory": round(p.info["memory_percent"] or 0.0, 1),
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        top_procs.sort(key=lambda x: (x["cpu"], x["memory"]), reverse=True)

        return JSONResponse(
            {
                "cpu_percent": cpu_pct,
                "cpu_count": psutil.cpu_count(logical=True),
                "memory_total_gb": round(mem.total / (1024**3), 2),
                "memory_used_gb": round(mem.used / (1024**3), 2),
                "memory_percent": mem.percent,
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "disk_used_gb": round(disk.used / (1024**3), 2),
                "disk_percent": disk.percent,
                "processes": top_procs[:12],
            }
        )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def terminal_websocket_endpoint(websocket: WebSocket):
    """Interactive bidirectional terminal WebSocket."""
    await websocket.accept()

    token = websocket.query_params.get("token")
    user = None
    if AUTH.is_setup_completed():
        user = AUTH.validate_session(token)
        if not user:
            await websocket.send_text("\r\n\x1b[1;31m[AUTH ERROR] Unauthorized. Please sign in.\x1b[0m\r\n")
            await websocket.close(code=1008)
            return

    username = user.username if user else "guest"
    shell_choice = websocket.query_params.get("shell", "bash")
    cmd, label = _detect_terminal_command(shell=shell_choice)
    welcome_banner = (
        f"\r\n\x1b[1;38;5;208m   __  ____                     __               __  ___ __________ \x1b[0m\r\n"
        f"\x1b[1;38;5;208m  / / / / /_  __  ______  / /___  __     /  |/  / ____/ __ \\\x1b[0m\r\n"
        f"\x1b[1;38;5;208m / / / / __ \\/ / / / __ \\/ __/ / / /    / /|_/ / /   / /_/ /\x1b[0m\r\n"
        f"\x1b[1;38;5;208m/ /_/ / /_/ / /_/ / / / / /_/ /_/ /    / /  / / /___/ ____/ \x1b[0m\r\n"
        f"\x1b[1;38;5;208m\\____/_.___/\\__,_/_/ /_/\\__/\\__,_/    /_/  /_/\\____/_/      \x1b[0m\r\n"
        f"\r\n\x1b[1;32m Connected to {label} as \x1b[1;37m{username}\x1b[0m \x1b[1;32m(Device Storage Granted)\x1b[0m\r\n"
        f"\x1b[90m Type bash commands, run scripts, or explore MCP tools.\x1b[0m\r\n\r\n"
    )
    await websocket.send_text(welcome_banner)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        async def read_from_stdout():
            try:
                while proc.returncode is None:
                    chunk = await proc.stdout.read(1024)
                    if not chunk:
                        break
                    text = chunk.decode("utf-8", errors="replace")
                    text = text.replace("\r\n", "\n").replace("\n", "\r\n")
                    await websocket.send_text(text)
            except (asyncio.CancelledError, WebSocketDisconnect):
                pass
            except Exception:
                pass

        async def write_to_stdin():
            try:
                while True:
                    data = await websocket.receive_text()
                    try:
                        msg = json.loads(data)
                        if isinstance(msg, dict):
                            if msg.get("type") == "input":
                                raw_input = msg.get("data", "")
                                proc.stdin.write(raw_input.encode("utf-8"))
                                await proc.stdin.drain()
                                continue
                    except (json.JSONDecodeError, TypeError):
                        pass

                    proc.stdin.write(data.encode("utf-8"))
                    await proc.stdin.drain()
            except (asyncio.CancelledError, WebSocketDisconnect):
                pass
            except Exception:
                pass

        read_task = asyncio.create_task(read_from_stdout())
        write_task = asyncio.create_task(write_to_stdin())

        done, pending = await asyncio.wait(
            [read_task, write_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_text(f"\r\n\x1b[31mTerminal error: {exc}\x1b[0m\r\n")
        except Exception:
            pass
    finally:
        try:
            if "proc" in locals() and proc.returncode is None:
                proc.terminate()
        except Exception:
            pass


async def index_page(request):
    """Serve the single page application."""
    index_file = STATIC_DIR / "index.html"
    return FileResponse(index_file)


routes = [
    Route("/", endpoint=index_page),
    Route("/api/auth/status", endpoint=api_auth_status, methods=["GET"]),
    Route("/api/auth/register", endpoint=api_auth_register, methods=["POST"]),
    Route("/api/auth/login", endpoint=api_auth_login, methods=["POST"]),
    Route("/api/auth/me", endpoint=api_auth_me, methods=["GET"]),
    Route("/api/auth/logout", endpoint=api_auth_logout, methods=["POST"]),
    Route("/api/portals", endpoint=api_portals_list, methods=["GET"]),
    Route("/api/portals", endpoint=api_portals_add, methods=["POST"]),
    Route("/api/portals/{portal_id}/sync", endpoint=api_portals_sync, methods=["POST"]),
    Route("/api/portals/{portal_id}", endpoint=api_portals_delete, methods=["DELETE"]),
    Route("/api/status", endpoint=api_status, methods=["GET"]),
    Route("/api/tools", endpoint=api_tools, methods=["GET"]),
    Route("/api/call-tool", endpoint=api_call_tool, methods=["POST"]),
    Route("/api/system-metrics", endpoint=api_system_metrics, methods=["GET"]),
    WebSocketRoute("/ws/terminal", endpoint=terminal_websocket_endpoint),
]

class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/") or request.url.path == "/":
            response.headers["Cache-Control"] = "no-cache, must-revalidate, max-age=0"
        return response


middleware = [
    Middleware(CacheControlMiddleware),
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    ),
]

app = Starlette(routes=routes, middleware=middleware)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def run(host: str = "0.0.0.0", port: int = 8000):
    """Run the Web GUI server."""
    _ensure_ttyd_daemons()
    print(f"\n=======================================================")
    print(f"  Ubuntu MCP Server Web GUI, Terminal & Portals Hub")
    print(f"  Open in your browser: http://localhost:{port}")
    print(f"=======================================================\n")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run()
