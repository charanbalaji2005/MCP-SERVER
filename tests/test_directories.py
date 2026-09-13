import pytest

from ubuntu_mcp.exceptions import FileOperationError, NotFoundError, ValidationError
from ubuntu_mcp.tools import directories, filesystem


async def test_create_and_list_directory(workspace):
    await directories.create_directory("sub")
    await filesystem.write_file("sub/a.txt", "1")
    await filesystem.write_file("sub/b.txt", "2")

    listing = await directories.list_directory("sub")
    names = sorted(e["name"] for e in listing["entries"])
    assert names == ["a.txt", "b.txt"]


async def test_list_directory_recursive(workspace):
    await directories.create_directory("sub/nested")
    await filesystem.write_file("sub/a.txt", "1")
    await filesystem.write_file("sub/nested/b.txt", "2")

    listing = await directories.list_directory("sub", recursive=True)
    paths = sorted(e["path"] for e in listing["entries"])
    assert "sub/nested/b.txt" in paths


async def test_directory_exists(workspace):
    await directories.create_directory("exists_here")
    assert (await directories.directory_exists("exists_here"))["exists"] is True
    assert (await directories.directory_exists("does_not_exist"))["exists"] is False


async def test_delete_empty_directory(workspace):
    await directories.create_directory("empty")
    await directories.delete_directory("empty")
    assert (await directories.directory_exists("empty"))["exists"] is False


async def test_delete_nonempty_requires_recursive(workspace):
    await directories.create_directory("full")
    await filesystem.write_file("full/f.txt", "x")
    with pytest.raises(FileOperationError):
        await directories.delete_directory("full", recursive=False)

    await directories.delete_directory("full", recursive=True)
    assert (await directories.directory_exists("full"))["exists"] is False


async def test_cannot_delete_workspace_root(workspace):
    with pytest.raises(ValidationError):
        await directories.delete_directory(".", recursive=True)


async def test_find_files_by_pattern(workspace):
    await directories.create_directory("proj")
    await filesystem.write_file("proj/main.py", "x")
    await filesystem.write_file("proj/readme.md", "x")
    await filesystem.write_file("proj/notes.py", "x")

    result = await directories.find_files("proj", "*.py")
    assert sorted(result["matches"]) == ["proj/main.py", "proj/notes.py"]


async def test_get_directory_size(workspace):
    await directories.create_directory("sized")
    await filesystem.write_file("sized/a.txt", "12345")
    await filesystem.write_file("sized/b.txt", "12345678")

    result = await directories.get_directory_size("sized")
    assert result["total_bytes"] == 13
    assert result["file_count"] == 2


async def test_list_missing_directory_raises(workspace):
    with pytest.raises(NotFoundError):
        await directories.list_directory("nope")
