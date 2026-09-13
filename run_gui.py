#!/usr/bin/env python3
"""Launcher for Ubuntu MCP Web Console & Interactive Terminal.

Usage:
    python run_gui.py [--host 0.0.0.0] [--port 8000] [--no-browser]
"""

import argparse
import sys
import threading
import time
import webbrowser
from pathlib import Path

root_dir = Path(__file__).resolve().parent
src_dir = root_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from ubuntu_mcp.web.server import run


def open_browser_later(url: str, delay: float = 1.2):
    def _open():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    t = threading.Thread(target=_open, daemon=True)
    t.start()


def main():
    parser = argparse.ArgumentParser(description="Ubuntu MCP Web GUI & Terminal Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")
    args = parser.parse_args()

    local_url = f"http://localhost:{args.port}"
    if not args.no_browser:
        open_browser_later(local_url)

    run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
