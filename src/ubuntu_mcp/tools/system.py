"""Ubuntu/system tools: safe, read-only introspection only.

No tool in this module executes an arbitrary, user-supplied command.
`get_service_status` shells out to a fixed `systemctl status --no-pager`
invocation with a strictly validated service name; that is the only
subprocess call in this module.
"""

from __future__ import annotations

import asyncio
import platform
import re
import socket
from datetime import datetime, timezone

import psutil

from ..exceptions import ValidationError
from ..security import safe_path

_SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9@._-]{1,128}$")


async def get_system_info() -> dict:
    uname = platform.uname()
    boot_ts = psutil.boot_time()
    return {
        "os": uname.system,
        "os_release": platform.release(),
        "os_version": uname.version,
        "architecture": platform.machine(),
        "hostname": socket.gethostname(),
        "python_version": platform.python_version(),
        "processor": uname.processor or platform.processor() or "unknown",
        "boot_time_utc": datetime.fromtimestamp(boot_ts, tz=timezone.utc).isoformat(),
    }


async def get_cpu_info() -> dict:
    freq = psutil.cpu_freq()
    return {
        "logical_cores": psutil.cpu_count(logical=True),
        "physical_cores": psutil.cpu_count(logical=False),
        "current_usage_percent": psutil.cpu_percent(interval=0.3),
        "per_core_usage_percent": psutil.cpu_percent(interval=0.0, percpu=True),
        "frequency_mhz": {
            "current": round(freq.current, 1) if freq else None,
            "min": freq.min if freq else None,
            "max": freq.max if freq else None,
        },
        "load_average": (
            dict(zip(("1min", "5min", "15min"), psutil.getloadavg()))
            if hasattr(psutil, "getloadavg")
            else None
        ),
    }


async def get_memory_info() -> dict:
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    gb = 1024 ** 3
    return {
        "total_gb": round(vm.total / gb, 2),
        "available_gb": round(vm.available / gb, 2),
        "used_gb": round(vm.used / gb, 2),
        "used_percent": vm.percent,
        "swap_total_gb": round(swap.total / gb, 2),
        "swap_used_gb": round(swap.used / gb, 2),
        "swap_percent": swap.percent,
    }


async def get_disk_info(path: str = ".") -> dict:
    resolved = safe_path(path, must_exist=True)
    usage = psutil.disk_usage(str(resolved))
    gb = 1024 ** 3
    return {
        "path": path,
        "total_gb": round(usage.total / gb, 2),
        "used_gb": round(usage.used / gb, 2),
        "free_gb": round(usage.free / gb, 2),
        "used_percent": usage.percent,
    }


async def list_processes(limit: int = 20, sort_by: str = "cpu") -> dict:
    if not 1 <= limit <= 200:
        raise ValidationError("limit must be between 1 and 200.")
    if sort_by not in {"cpu", "memory"}:
        raise ValidationError("sort_by must be 'cpu' or 'memory'.")

    procs = []
    for p in psutil.process_iter(
        ["pid", "name", "username", "cpu_percent", "memory_percent", "status"]
    ):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
    procs.sort(key=lambda i: i.get(key) or 0.0, reverse=True)

    return {"sorted_by": sort_by, "count": min(limit, len(procs)), "processes": procs[:limit]}


async def get_service_status(service_name: str) -> dict:
    """Read-only `systemctl status <service> --no-pager` for one whitelisted
    service name (letters, digits, '@', '.', '_', '-' only)."""
    if not _SERVICE_NAME_RE.match(service_name):
        raise ValidationError(
            "service_name may only contain letters, digits, '@', '.', '_' and '-'."
        )

    try:
        proc = await asyncio.create_subprocess_exec(
            "systemctl",
            "status",
            service_name,
            "--no-pager",
            "--full",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
    except FileNotFoundError:
        return {
            "service_name": service_name,
            "available": False,
            "note": "systemctl is not available on this host.",
        }
    except asyncio.TimeoutError:
        return {"service_name": service_name, "available": False, "note": "Timed out."}

    return {
        "service_name": service_name,
        "available": True,
        "exit_code": proc.returncode,
        "output": stdout.decode(errors="replace") or stderr.decode(errors="replace"),
    }
