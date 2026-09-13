"""MCP Portals Hub & Aggregator.

Manages connections to multiple MCP servers (Local, Streamable-HTTP, and SSE).
Discovers tools, tracks health & latency, and routes tool calls to the appropriate portal.
Stores registered portals in workspace/.mcp_portals.json.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx

from ..config import SETTINGS
from ..server import mcp

PORTALS_FILE = SETTINGS.workspace_root / ".mcp_portals.json"


@dataclass
class PortalRecord:
    id: str
    name: str
    url: str
    transport: str
    auth_header: Optional[str] = None
    status: str = "online"
    latency_ms: float = 0.0
    is_default: bool = False
    tools_count: int = 0
    tools: list[dict[str, Any]] = field(default_factory=list)
    last_synced_utc: Optional[str] = None
    error_message: Optional[str] = None


def _parse_mcp_response(res: httpx.Response) -> dict[str, Any]:
    """Parse JSON or SSE event stream from an MCP endpoint."""
    text = res.text.strip()
    if not text:
        return {}
    if text.startswith("{") and text.endswith("}"):
        try:
            return json.loads(text)
        except Exception:
            pass

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            data_str = line[5:].strip()
            if data_str:
                try:
                    return json.loads(data_str)
                except Exception:
                    continue
    return res.json()


class PortalManager:
    def __init__(self, file_path: Path = PORTALS_FILE):
        self.file_path = file_path
        self._portals: dict[str, PortalRecord] = {}
        self._init_default()
        self._load()

    def _init_default(self):
        """Register the built-in local Ubuntu MCP Server as the primary portal."""
        self._portals["local"] = PortalRecord(
            id="local",
            name="Ubuntu MCP Server (Local)",
            url="internal://local",
            transport="local",
            status="online",
            latency_ms=1.2,
            is_default=True,
            tools_count=38,
            tools=[],  
            last_synced_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

    def _load(self):
        """Load external portals from storage file."""
        if not self.file_path.exists():
            return
        try:
            data = json.loads(self.file_path.read_text(encoding="utf-8"))
            for p in data.get("portals", []):
                if p.get("id") == "local":
                    continue
                record = PortalRecord(**p)
                self._portals[record.id] = record
        except Exception:
            pass

    def _save(self):
        """Persist portals to storage file."""
        try:
            custom_portals = [
                asdict(p) for p in self._portals.values() if not p.is_default
            ]
            self.file_path.write_text(
                json.dumps({"portals": custom_portals}, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    async def list_portals(self) -> list[dict[str, Any]]:
        """Return all registered portals."""
        return [asdict(p) for p in self._portals.values()]

    def get_portal(self, portal_id: str) -> Optional[PortalRecord]:
        return self._portals.get(portal_id)

    async def add_portal(self, name: str, url: str, transport: str = "streamable-http", auth_header: Optional[str] = None) -> tuple[bool, str, Optional[dict[str, Any]]]:
        """Probe and register a new external MCP portal."""
        url = url.strip().rstrip("/")
        name = name.strip()
        if not name or not url:
            return False, "Name and URL are required.", None

        for existing in self._portals.values():
            if existing.url.lower() == url.lower():
                return False, f"Portal with URL '{url}' is already registered.", None

        portal_id = str(uuid.uuid4())[:8]

        ok, msg, tools, latency, session_id = await self._probe_portal(url, transport, auth_header)
        if not ok:
            return False, f"Failed to connect to portal: {msg}", None

        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        record = PortalRecord(
            id=portal_id,
            name=name,
            url=url,
            transport=transport,
            auth_header=auth_header,
            status="online",
            latency_ms=latency,
            is_default=False,
            tools_count=len(tools),
            tools=tools,
            last_synced_utc=now_str,
        )

        self._portals[portal_id] = record
        self._save()
        return True, "Portal connected successfully.", asdict(record)

    async def sync_portal(self, portal_id: str) -> tuple[bool, str, Optional[dict[str, Any]]]:
        """Re-probe and refresh tools from a specific portal."""
        if portal_id == "local":
            tools = await mcp.list_tools()
            self._portals["local"].tools_count = len(tools)
            self._portals["local"].last_synced_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            return True, "Local portal synced.", asdict(self._portals["local"])

        record = self._portals.get(portal_id)
        if not record:
            return False, "Portal not found.", None

        ok, msg, tools, latency, session_id = await self._probe_portal(record.url, record.transport, record.auth_header)
        if not ok:
            record.status = "error"
            record.error_message = msg
            self._save()
            return False, f"Sync failed: {msg}", asdict(record)

        record.status = "online"
        record.tools = tools
        record.tools_count = len(tools)
        record.latency_ms = latency
        record.error_message = None
        record.last_synced_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._save()
        return True, f"Synced {len(tools)} tools.", asdict(record)

    def delete_portal(self, portal_id: str) -> tuple[bool, str]:
        """Delete a custom portal."""
        if portal_id == "local":
            return False, "Cannot delete the default local Ubuntu MCP Server portal."
        if portal_id not in self._portals:
            return False, "Portal not found."
        del self._portals[portal_id]
        self._save()
        return True, "Portal removed."

    async def _probe_portal(self, url: str, transport: str, auth_header: Optional[str] = None) -> tuple[bool, str, list[dict[str, Any]], float, Optional[str]]:
        """Send JSON-RPC initialize and tools/list to external MCP server."""
        headers = {"Content-Type": "application/json"}
        if auth_header:
            headers["Authorization"] = auth_header

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                init_payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "ubuntu-mcp-portal-hub", "version": "1.0.0"},
                    },
                }
                init_res = await client.post(url, json=init_payload, headers=headers)
                session_id = init_res.headers.get("mcp-session-id")
                req_headers = dict(headers)
                if session_id:
                    req_headers["mcp-session-id"] = session_id

                await client.post(
                    url,
                    json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                    headers=req_headers,
                )

                tools_res = await client.post(
                    url,
                    json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                    headers=req_headers,
                )
                latency = round((time.perf_counter() - start_time) * 1000, 2)

                data = _parse_mcp_response(tools_res)
                tools_raw = data.get("result", {}).get("tools", [])
                tools = []
                for t in tools_raw:
                    tools.append(
                        {
                            "name": t.get("name"),
                            "description": t.get("description", ""),
                            "schema": t.get("inputSchema", t.get("input_schema", {})),
                        }
                    )
                return True, "Connected", tools, latency, session_id

            except Exception as e:
                latency = round((time.perf_counter() - start_time) * 1000, 2)
                return False, str(e), [], latency, None

    async def call_tool(self, portal_id: str, tool_name: str, arguments: dict[str, Any]) -> tuple[bool, Any, float, Optional[str]]:
        """Dispatch tool execution to local server or remote portal."""
        start_time = time.perf_counter()

        if portal_id == "local":
            try:
                call_res = await mcp.call_tool(tool_name, arguments)
                duration = round((time.perf_counter() - start_time) * 1000, 2)
                data = None
                for item in call_res.content:
                    if getattr(item, "type", None) == "text":
                        try:
                            data = json.loads(item.text)
                        except Exception:
                            data = item.text
                        break
                return not call_res.is_error, data, duration, None if not call_res.is_error else "Tool execution error"
            except Exception as exc:
                duration = round((time.perf_counter() - start_time) * 1000, 2)
                return False, None, duration, str(exc)

        portal = self._portals.get(portal_id)
        if not portal:
            return False, None, 0.0, f"Portal '{portal_id}' not found."

        headers = {"Content-Type": "application/json"}
        if portal.auth_header:
            headers["Authorization"] = portal.auth_header

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                init_res = await client.post(
                    portal.url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "ubuntu-mcp-portal-hub", "version": "1.0.0"},
                        },
                    },
                    headers=headers,
                )
                session_id = init_res.headers.get("mcp-session-id")
                call_headers = dict(headers)
                if session_id:
                    call_headers["mcp-session-id"] = session_id

                await client.post(
                    portal.url,
                    json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                    headers=call_headers,
                )

                req_payload = {
                    "jsonrpc": "2.0",
                    "id": int(time.time()),
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments},
                }
                res = await client.post(portal.url, json=req_payload, headers=call_headers)
                duration = round((time.perf_counter() - start_time) * 1000, 2)
                res_data = _parse_mcp_response(res)

                if "error" in res_data:
                    return False, res_data["error"], duration, res_data["error"].get("message", "Tool error")

                result_content = res_data.get("result", {}).get("content", [])
                out = None
                for c in result_content:
                    if c.get("type") == "text":
                        try:
                            out = json.loads(c.get("text"))
                        except Exception:
                            out = c.get("text")
                        break
                return True, out or res_data.get("result"), duration, None

            except Exception as e:
                duration = round((time.perf_counter() - start_time) * 1000, 2)
                return False, None, duration, str(e)


PORTALS = PortalManager()
