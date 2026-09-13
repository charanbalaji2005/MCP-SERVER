import pytest

from ubuntu_mcp.exceptions import ValidationError
from ubuntu_mcp.tools import code_tools, directories, filesystem


async def test_count_words():
    result = await code_tools.count_words("The quick brown fox\njumps over")
    assert result["words"] == 6
    assert result["lines"] == 2


async def test_format_json_valid():
    result = await code_tools.format_json('{"b":2,"a":1}', indent=2)
    assert result["formatted"] == '{\n  "b": 2,\n  "a": 1\n}'


async def test_format_json_invalid_raises():
    with pytest.raises(ValidationError):
        await code_tools.format_json("{not valid json")


async def test_validate_json():
    assert (await code_tools.validate_json('{"a": 1}'))["valid"] is True
    assert (await code_tools.validate_json("{a: 1}"))["valid"] is False


async def test_detect_project_type_python(workspace):
    await filesystem.write_file("pyproject.toml", "[project]\nname='x'\n")
    result = await code_tools.detect_project_type(".")
    assert "Python" in result["detected_types"]


async def test_detect_project_type_unknown(workspace):
    result = await code_tools.detect_project_type(".")
    assert result["detected_types"] == ["unknown/generic"]


async def test_search_text_in_files(workspace):
    await directories.create_directory("src")
    await filesystem.write_file("src/a.py", "def foo():\n    return TODO\n")
    await filesystem.write_file("src/b.py", "def bar():\n    return 42\n")

    result = await code_tools.search_text_in_files(".", pattern="TODO", file_glob="*.py")
    assert result["count"] == 1
    assert result["matches"][0]["file"] == "src/a.py"


async def test_search_text_rejects_empty_pattern(workspace):
    with pytest.raises(ValidationError):
        await code_tools.search_text_in_files(".", pattern="")


async def test_csv_to_json_and_columns(workspace):
    await filesystem.write_file("data.csv", "name,age\nAlice,30\nBob,25\n")

    columns = await code_tools.csv_get_columns("data.csv")
    assert columns["columns"] == ["name", "age"]

    as_json = await code_tools.csv_to_json("data.csv")
    assert as_json["row_count"] == 2
    assert as_json["rows"][0] == {"name": "Alice", "age": "30"}
