import pytest

from ubuntu_mcp.exceptions import FileOperationError, NotFoundError, SecurityError, ValidationError
from ubuntu_mcp.tools import filesystem


async def test_write_and_read_roundtrip(workspace):
    await filesystem.write_file("a.txt", "hello world")
    result = await filesystem.read_file("a.txt")
    assert result["content"] == "hello world"
    assert result["size"] == 11


async def test_write_no_overwrite_fails(workspace):
    await filesystem.write_file("a.txt", "v1")
    with pytest.raises(FileOperationError):
        await filesystem.write_file("a.txt", "v2", overwrite=False)


async def test_append_file(workspace):
    await filesystem.write_file("log.txt", "line1\n")
    await filesystem.append_file("log.txt", "line2\n")
    result = await filesystem.read_file("log.txt")
    assert result["content"] == "line1\nline2\n"


async def test_append_missing_file_raises(workspace):
    with pytest.raises(NotFoundError):
        await filesystem.append_file("missing.txt", "x")


async def test_delete_file(workspace):
    await filesystem.write_file("del.txt", "bye")
    await filesystem.delete_file("del.txt")
    exists = await filesystem.file_exists("del.txt")
    assert exists["exists"] is False


async def test_delete_missing_file_raises(workspace):
    with pytest.raises(NotFoundError):
        await filesystem.delete_file("nope.txt")


async def test_copy_and_move(workspace):
    await filesystem.write_file("src.txt", "content")
    await filesystem.copy_file("src.txt", "copy.txt")
    assert (await filesystem.read_file("copy.txt"))["content"] == "content"

    await filesystem.move_file("copy.txt", "moved.txt")
    assert (await filesystem.file_exists("copy.txt"))["exists"] is False
    assert (await filesystem.read_file("moved.txt"))["content"] == "content"


async def test_get_file_info(workspace):
    await filesystem.write_file("info.txt", "12345")
    info = await filesystem.get_file_info("info.txt")
    assert info["size_bytes"] == 5
    assert info["extension"] == ".txt"
    assert info["filename"] == "info.txt"


async def test_read_file_size_limit(workspace):
    from ubuntu_mcp.config import SETTINGS

    original = SETTINGS.max_file_size
    await filesystem.write_file("big.txt", "0123456789")
    object.__setattr__(SETTINGS, "max_file_size", 5)
    try:
        with pytest.raises(ValidationError):
            await filesystem.read_file("big.txt")
    finally:
        object.__setattr__(SETTINGS, "max_file_size", original)


@pytest.mark.parametrize(
    "bad_path",
    ["../outside.txt", "../../etc/passwd", "a/../../b.txt"],
)
async def test_path_traversal_is_blocked(workspace, bad_path):
    """Paths that would climb out of the workspace via '..' are rejected
    outright as a security violation."""
    with pytest.raises(SecurityError):
        await filesystem.read_file(bad_path)


async def test_absolute_path_is_confined_not_escaped(workspace):
    """An absolute path like '/etc/passwd' is NOT rejected as a security
    error -- it's safely re-rooted inside the workspace (so it never
    touches the real /etc/passwd) and simply doesn't exist there."""
    with pytest.raises(NotFoundError):
        await filesystem.read_file("/etc/passwd")


async def test_empty_path_is_rejected(workspace):
    with pytest.raises(SecurityError):
        await filesystem.read_file("")
