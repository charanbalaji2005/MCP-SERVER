"""Interactive test client for Ubuntu MCP Server.

Allows testing all 38 tools directly from your terminal.
Run with:
    .venv\\Scripts\\python.exe interactive_client.py
"""

import json
import subprocess
import sys
from pathlib import Path

BAT_PATH = Path(__file__).parent / "run_ubuntu_mcp.bat"


class MCPTestClient:
    def __init__(self):
        self.proc = subprocess.Popen(
            ["cmd.exe", "/c", str(BAT_PATH)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.req_id = 0

    def send_request(self, method: str, params: dict | None = None) -> dict:
        self.req_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self.req_id,
            "method": method,
            "params": params or {},
        }
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            return {"error": "Server closed connection"}
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return {"raw": line}

    def send_notification(self, method: str, params: dict | None = None):
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()

    def initialize(self):
        resp = self.send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "interactive-client", "version": "1.0.0"},
            },
        )
        self.send_notification("notifications/initialized")
        return resp

    def list_tools(self):
        return self.send_request("tools/list")

    def call_tool(self, tool_name: str, arguments: dict | None = None):
        return self.send_request(
            "tools/call",
            {"name": tool_name, "arguments": arguments or {}},
        )

    def close(self):
        if self.proc:
            self.proc.terminate()


def main():
    print("=" * 60)
    print("  Ubuntu MCP Server - Interactive Terminal Client")
    print("=" * 60)
    print("Connecting to Ubuntu MCP Server via WSL...")

    client = MCPTestClient()
    init_res = client.initialize()
    server_info = init_res.get("result", {}).get("serverInfo", {})
    print(f"Connected to: {server_info.get('name', 'MCP Server')}")

    tools_res = client.list_tools()
    tools = {t["name"]: t for t in tools_res.get("result", {}).get("tools", [])}
    print(f"Loaded {len(tools)} tools from Ubuntu WSL.\n")

    MENU = """Quick commands:
  [1] system      - Get Ubuntu OS, kernel & host info
  [2] cpu         - Get CPU count and usage info
  [3] memory      - Get RAM & swap usage
  [4] disk        - Get disk usage
  [5] processes   - List top processes running in Ubuntu
  [6] tools       - List all 38 available tools with descriptions
  [7] call <name> [json_args] - Call any tool manually
  [q] quit / exit - Disconnect and exit
"""
    print(MENU)

    shortcuts = {
        "1": "get_system_info",
        "system": "get_system_info",
        "2": "get_cpu_info",
        "cpu": "get_cpu_info",
        "3": "get_memory_info",
        "memory": "get_memory_info",
        "4": "get_disk_info",
        "disk": "get_disk_info",
        "5": "list_processes",
        "processes": "list_processes",
    }

    try:
        while True:
            cmd = input("\nmcp-ubuntu> ").strip()
            if not cmd:
                continue
            if cmd.lower() in ("q", "quit", "exit"):
                print("Exiting...")
                break

            if cmd.lower() in ("6", "tools", "help"):
                print(f"\n--- Available Tools ({len(tools)}) ---")
                for name, info in sorted(tools.items()):
                    desc = info.get("description", "").split("\n")[0]
                    print(f"  * {name:<22} : {desc}")
                continue

            tool_name = shortcuts.get(cmd.lower())
            tool_args = {}

            if not tool_name:
                if cmd.startswith("call "):
                    parts = cmd[5:].strip().split(maxsplit=1)
                    tool_name = parts[0]
                    if len(parts) > 1:
                        try:
                            tool_args = json.loads(parts[1])
                        except Exception as err:
                            print(f"Invalid JSON arguments: {err}")
                            continue
                elif cmd in tools:
                    tool_name = cmd
                else:
                    print(f"Unknown command or tool: '{cmd}'. Type 'help' or 'tools'.")
                    continue

            print(f"Calling tool '{tool_name}' on Ubuntu...")
            res = client.call_tool(tool_name, tool_args)
            content = res.get("result", {}).get("content", [])
            for c in content:
                if c.get("type") == "text":
                    try:
                        parsed = json.loads(c.get("text", "{}"))
                        print(json.dumps(parsed, indent=2))
                    except Exception:
                        print(c.get("text"))
            if res.get("error"):
                print("Error:", res["error"])
    finally:
        client.close()


if __name__ == "__main__":
    main()
