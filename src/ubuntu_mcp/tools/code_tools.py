"""Code/text/data tools: project detection, in-workspace text search,
word counting, JSON formatting/validation, and CSV<->JSON conversion.
"""

from __future__ import annotations

import csv
import json
import re

from ..config import SETTINGS
from ..exceptions import NotFoundError, ValidationError
from ..security import safe_path

_PROJECT_MARKERS = {
    "Python": ["pyproject.toml", "requirements.txt", "setup.py"],
    "Node.js": ["package.json"],
    "Rust": ["Cargo.toml"],
    "Go": ["go.mod"],
    "Java (Maven)": ["pom.xml"],
    "Java/Kotlin (Gradle)": ["build.gradle", "build.gradle.kts"],
    ".NET": ["*.csproj", "*.sln"],
    "C/C++ (CMake)": ["CMakeLists.txt"],
    "Ruby": ["Gemfile"],
    "PHP": ["composer.json"],
}

_REGEX_TIMEOUT_PATTERN_LEN = 200  # crude guard against pathological patterns


async def detect_project_type(path: str = ".") -> dict:
    resolved = safe_path(path, must_exist=True)
    if not resolved.is_dir():
        raise NotFoundError(f"'{path}' is not a directory.")

    detected = []
    for project_type, markers in _PROJECT_MARKERS.items():
        for marker in markers:
            if "*" in marker:
                if list(resolved.glob(marker)):
                    detected.append(project_type)
                    break
            elif (resolved / marker).exists():
                detected.append(project_type)
                break

    return {"path": path, "detected_types": detected or ["unknown/generic"]}


async def search_text_in_files(
    path: str = ".", pattern: str = "", file_glob: str = "*", max_results: int = 50
) -> dict:
    if not pattern:
        raise ValidationError("pattern must not be empty.")
    if len(pattern) > _REGEX_TIMEOUT_PATTERN_LEN:
        raise ValidationError("pattern is too long.")
    if not 1 <= max_results <= 500:
        raise ValidationError("max_results must be between 1 and 500.")

    resolved = safe_path(path, must_exist=True)
    if not resolved.is_dir():
        raise NotFoundError(f"'{path}' is not a directory.")

    try:
        regex = re.compile(pattern)
    except re.error as exc:
        raise ValidationError(f"Invalid regex pattern: {exc}") from exc

    results = []
    for file_path in resolved.rglob(file_glob):
        if not file_path.is_file():
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                results.append(
                    {
                        "file": file_path.relative_to(SETTINGS.workspace_root).as_posix(),
                        "line": line_no,
                        "text": line.strip()[:300],
                    }
                )
                if len(results) >= max_results:
                    break
        if len(results) >= max_results:
            break

    return {"path": path, "pattern": pattern, "count": len(results), "matches": results}


async def count_words(text: str) -> dict:
    return {
        "words": len(text.split()),
        "characters": len(text),
        "characters_without_spaces": len(text.replace(" ", "").replace("\n", "").replace("\t", "")),
        "lines": len(text.splitlines()) or (1 if text else 0),
    }


async def format_json(json_text: str, indent: int = 2) -> dict:
    if not 0 <= indent <= 8:
        raise ValidationError("indent must be between 0 and 8.")
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON: {exc}") from exc
    return {"formatted": json.dumps(parsed, indent=indent, sort_keys=False)}


async def validate_json(json_text: str) -> dict:
    try:
        json.loads(json_text)
        return {"valid": True, "error": None}
    except json.JSONDecodeError as exc:
        return {"valid": False, "error": str(exc)}


async def csv_to_json(path: str) -> dict:
    resolved = safe_path(path, must_exist=True)
    if not resolved.is_file():
        raise NotFoundError(f"'{path}' is not a file.")

    with resolved.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        columns = reader.fieldnames or []

    return {"path": path, "columns": columns, "row_count": len(rows), "rows": rows}


async def csv_get_columns(path: str) -> dict:
    resolved = safe_path(path, must_exist=True)
    if not resolved.is_file():
        raise NotFoundError(f"'{path}' is not a file.")

    with resolved.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            header = []

    return {"path": path, "columns": header}
