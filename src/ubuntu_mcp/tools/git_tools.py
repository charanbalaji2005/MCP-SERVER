"""Git tools: status, log, diff, branches, current branch.

Every function here calls a fixed `git <subcommand>` invocation via
asyncio.create_subprocess_exec (never a shell string), against a
repository path that has already passed through security.safe_path().
There is no way to pass arbitrary shell syntax through these tools.
"""

from __future__ import annotations

import asyncio

from ..exceptions import NotFoundError, ToolExecutionError, ValidationError
from ..security import safe_path


async def _run_git(repo_dir, args: list[str], timeout: int = 10) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(repo_dir),
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except FileNotFoundError as exc:
        raise ToolExecutionError("git is not installed on this host.") from exc
    except asyncio.TimeoutError as exc:
        raise ToolExecutionError(f"git {' '.join(args)} timed out.") from exc

    if proc.returncode != 0:
        raise ToolExecutionError(
            f"git {' '.join(args)} failed: {stderr.decode(errors='replace').strip()}"
        )
    return stdout.decode(errors="replace")


def _repo_dir(path: str):
    resolved = safe_path(path, must_exist=True)
    if not resolved.is_dir():
        raise NotFoundError(f"'{path}' is not a directory.")
    if not (resolved / ".git").exists():
        raise NotFoundError(f"'{path}' is not a git repository (no .git found).")
    return resolved


async def git_status(path: str = ".") -> dict:
    repo = _repo_dir(path)
    output = await _run_git(repo, ["status", "--porcelain=v1", "--branch"])
    lines = output.splitlines()
    branch_line = lines[0] if lines else ""
    changes = lines[1:]
    return {"path": path, "branch_info": branch_line.lstrip("#").strip(), "changes": changes}


async def git_log(path: str = ".", limit: int = 10) -> dict:
    if not 1 <= limit <= 200:
        raise ValidationError("limit must be between 1 and 200.")
    repo = _repo_dir(path)
    fmt = "%H%x1f%an%x1f%ad%x1f%s"
    output = await _run_git(
        repo, ["log", f"-{limit}", f"--pretty=format:{fmt}", "--date=iso-strict"]
    )
    commits = []
    for line in output.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 4:
            commits.append(
                {"hash": parts[0], "author": parts[1], "date": parts[2], "subject": parts[3]}
            )
    return {"path": path, "count": len(commits), "commits": commits}


async def git_diff(path: str = ".", staged: bool = False, file_path: str | None = None) -> dict:
    repo = _repo_dir(path)
    args = ["diff"]
    if staged:
        args.append("--staged")
    if file_path:
        args.extend(["--", file_path])
    output = await _run_git(repo, args)
    return {"path": path, "staged": staged, "diff": output}


async def git_branches(path: str = ".") -> dict:
    repo = _repo_dir(path)
    output = await _run_git(repo, ["branch", "--list"])
    branches = []
    current = None
    for line in output.splitlines():
        name = line.strip().lstrip("* ").strip()
        if not name:
            continue
        if line.strip().startswith("*"):
            current = name
        branches.append(name)
    return {"path": path, "current": current, "branches": branches}


async def git_current_branch(path: str = ".") -> dict:
    repo = _repo_dir(path)
    output = await _run_git(repo, ["rev-parse", "--abbrev-ref", "HEAD"])
    return {"path": path, "branch": output.strip()}
