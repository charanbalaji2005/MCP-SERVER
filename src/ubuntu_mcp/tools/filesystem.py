"""Filesystem tools: read, write, append, delete, copy, move, stat.

Every path is resolved through security.safe_path(), which confines
all operations inside the configured MCP_WORKSPACE directory.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ..config import SETTINGS
from ..exceptions import FileOperationError, NotFoundError, ValidationError
from ..security import safe_path


def _stat_dict(path: Path) -> dict:
    st = path.stat()
    return {
        "path": path.relative_to(SETTINGS.workspace_root).as_posix(),
        "absolute_path": str(path),
        "size_bytes": st.st_size,
        "modified_time": st.st_mtime,
        "created_time": st.st_ctime,
        "is_file": path.is_file(),
        "is_directory": path.is_dir(),
        "extension": path.suffix,
        "filename": path.name,
    }


async def read_file(path: str, encoding: str = "utf-8") -> dict:
    resolved = safe_path(path, must_exist=True)
    if not resolved.is_file():
        raise NotFoundError(f"'{path}' is not a file.")
    size = resolved.stat().st_size
    if size > SETTINGS.max_file_size:
        raise ValidationError(
            f"File is {size} bytes, exceeding the {SETTINGS.max_file_size}-byte limit."
        )
    try:
        content = resolved.read_text(encoding=encoding)
    except UnicodeDecodeError as exc:
        raise ValidationError(
            f"File is not valid {encoding} text (looks binary)."
        ) from exc
    return {
        "path": path,
        "size": size,
        "encoding": encoding,
        "content": content,
    }


async def write_file(path: str, content: str, overwrite: bool = True) -> dict:
    resolved = safe_path(path)
    if resolved.exists() and not overwrite:
        raise FileOperationError(f"'{path}' already exists and overwrite=False.")
    encoded = content.encode("utf-8")
    if len(encoded) > SETTINGS.max_file_size:
        raise ValidationError(
            f"Content is {len(encoded)} bytes, exceeding the "
            f"{SETTINGS.max_file_size}-byte limit."
        )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return {"path": path, "bytes_written": len(encoded), "success": True}


async def append_file(path: str, content: str) -> dict:
    resolved = safe_path(path, must_exist=True)
    if not resolved.is_file():
        raise NotFoundError(f"'{path}' is not a file.")
    encoded = content.encode("utf-8")
    new_size = resolved.stat().st_size + len(encoded)
    if new_size > SETTINGS.max_file_size:
        raise ValidationError("Appending would exceed the max file size limit.")
    with resolved.open("a", encoding="utf-8") as fh:
        fh.write(content)
    return {"path": path, "bytes_appended": len(encoded), "success": True}


async def delete_file(path: str) -> dict:
    resolved = safe_path(path, must_exist=True)
    if not resolved.is_file():
        raise NotFoundError(f"'{path}' is not a file.")
    resolved.unlink()
    return {"path": path, "deleted": True}


async def copy_file(source: str, destination: str) -> dict:
    src = safe_path(source, must_exist=True)
    if not src.is_file():
        raise NotFoundError(f"'{source}' is not a file.")
    dst = safe_path(destination)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return {"source": source, "destination": destination, "success": True}


async def move_file(source: str, destination: str) -> dict:
    src = safe_path(source, must_exist=True)
    if not src.is_file():
        raise NotFoundError(f"'{source}' is not a file.")
    dst = safe_path(destination)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return {"source": source, "destination": destination, "success": True}


async def file_exists(path: str) -> dict:
    resolved = safe_path(path)
    exists = resolved.is_file()
    return {"path": path, "exists": exists}


async def get_file_info(path: str) -> dict:
    resolved = safe_path(path, must_exist=True)
    if not resolved.is_file():
        raise NotFoundError(f"'{path}' is not a file.")
    return _stat_dict(resolved)
