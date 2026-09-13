import pytest

from ubuntu_mcp.exceptions import ValidationError
from ubuntu_mcp.tools import system


async def test_get_system_info_shape():
    info = await system.get_system_info()
    assert "os" in info
    assert "hostname" in info
    assert "python_version" in info


async def test_get_cpu_info_shape():
    info = await system.get_cpu_info()
    assert info["logical_cores"] >= 1
    assert 0.0 <= info["current_usage_percent"] <= 100.0


async def test_get_memory_info_shape():
    info = await system.get_memory_info()
    assert info["total_gb"] > 0
    assert 0.0 <= info["used_percent"] <= 100.0


async def test_get_disk_info_default_path(workspace):
    info = await system.get_disk_info(".")
    assert info["total_gb"] > 0


async def test_list_processes_validates_limit():
    with pytest.raises(ValidationError):
        await system.list_processes(limit=0)
    with pytest.raises(ValidationError):
        await system.list_processes(limit=1000)


async def test_list_processes_validates_sort_by():
    with pytest.raises(ValidationError):
        await system.list_processes(sort_by="disk")


async def test_list_processes_returns_entries():
    result = await system.list_processes(limit=5, sort_by="memory")
    assert result["sorted_by"] == "memory"
    assert len(result["processes"]) <= 5


async def test_get_service_status_rejects_bad_names():
    with pytest.raises(ValidationError):
        await system.get_service_status("nginx; rm -rf /")
    with pytest.raises(ValidationError):
        await system.get_service_status("$(whoami)")


async def test_get_service_status_accepts_valid_name():
    result = await system.get_service_status("cron")
    assert result["service_name"] == "cron"
    assert "available" in result
