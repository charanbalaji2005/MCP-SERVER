import json

from ubuntu_mcp.server import mcp


async def test_all_tools_registered():
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    # spot-check one tool from each category rather than an exhaustive list
    for expected in (
        "read_file",
        "list_directory",
        "get_system_info",
        "fetch_url",
        "git_status",
        "detect_project_type",
    ):
        assert expected in names
    assert len(tools) >= 35


async def test_call_tool_returns_structured_success(workspace):
    result = await mcp.call_tool("get_system_info", {})
    payload = json.loads(result.content[0].text)
    assert payload["success"] is True
    assert "os" in payload["data"]


async def test_call_tool_returns_structured_error(workspace):
    result = await mcp.call_tool("read_file", {"path": "nope.txt"})
    payload = json.loads(result.content[0].text)
    assert payload["success"] is False
    assert payload["error"]["code"] in {"SECURITY_ERROR", "NOT_FOUND"}


async def test_call_tool_blocks_traversal(workspace):
    result = await mcp.call_tool("read_file", {"path": "../../etc/passwd"})
    payload = json.loads(result.content[0].text)
    assert payload["success"] is False
