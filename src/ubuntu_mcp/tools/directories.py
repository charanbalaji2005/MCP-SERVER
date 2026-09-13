"""Directory tools: list, create, delete, exists, find, size."""

from __future__ import annotations

import fnmatch
import shutil
from pathlib import Path

from ..config import SETTINGS
from ..exceptions import FileOperationError, NotFoundError, ValidationError
from ..security import safe_path


def _entry_dict(entry: Path) -> dict:
    return {
        "name": entry.name,
        "path": entry.relative_to(SETTINGS.workspace_root).as_posix(),
        "is_directory": entry.is_dir(),
        "is_file": entry.is_file(),
        "size_bytes": entry.stat().st_size if entry.is_file() else None,
    }


async def list_directory(path: str = ".", recursive: bool = False) -> dict:
    resolved = safe_path(path, must_exist=True)
    if not resolved.is_dir():
        raise NotFoundError(f"'{path}' is not a directory.")

    entries: list[dict] = []
    if recursive:
        max_depth = SETTINGS.max_directory_depth
        root_depth = len(resolved.parts)
        for entry in resolved.rglob("*"):
            if len(entry.parts) - root_depth > max_depth:
                continue
            entries.append(_entry_dict(entry))
    else:
        for entry in sorted(resolved.iterdir()):
            entries.append(_entry_dict(entry))

    return {"path": path, "recursive": recursive, "count": len(entries), "entries": entries}


async def create_directory(path: str) -> dict:
    resolved = safe_path(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return {"path": path, "created": True}


async def delete_directory(path: str, recursive: bool = False) -> dict:
    resolved = safe_path(path, must_exist=True)
    if not resolved.is_dir():
        raise NotFoundError(f"'{path}' is not a directory.")
    if resolved == SETTINGS.workspace_root:
        raise ValidationError("Refusing to delete the workspace root itself.")

    if any(resolved.iterdir()):
        if not recursive:
            raise FileOperationError(
                f"'{path}' is not empty; pass recursive=True to delete it and its contents."
            )
        shutil.rmtree(resolved)
    else:
        resolved.rmdir()
    return {"path": path, "deleted": True}


async def directory_exists(path: str) -> dict:
    resolved = safe_path(path)
    return {"path": path, "exists": resolved.is_dir()}


async def find_files(path: str = ".", pattern: str = "*") -> dict:
    resolved = safe_path(path, must_exist=True)
    if not resolved.is_dir():
        raise NotFoundError(f"'{path}' is not a directory.")

    max_depth = SETTINGS.max_directory_depth
    root_depth = len(resolved.parts)
    matches: list[str] = []
    for entry in resolved.rglob("*"):
        if len(entry.parts) - root_depth > max_depth:
            continue
        if entry.is_file() and fnmatch.fnmatch(entry.name, pattern):
            matches.append(entry.relative_to(SETTINGS.workspace_root).as_posix())
        if len(matches) >= 500:
            break

    return {"path": path, "pattern": pattern, "count": len(matches), "matches": matches}


async def get_directory_size(path: str = ".") -> dict:
    resolved = safe_path(path, must_exist=True)
    if not resolved.is_dir():
        raise NotFoundError(f"'{path}' is not a directory.")

    total = 0
    file_count = 0
    for entry in resolved.rglob("*"):
        if entry.is_file():
            total += entry.stat().st_size
            file_count += 1

    return {
        "path": path,
        "total_bytes": total,
        "total_megabytes": round(total / (1024 * 1024), 3),
        "file_count": file_count,
    }
