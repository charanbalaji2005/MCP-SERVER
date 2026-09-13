import subprocess

import pytest

from ubuntu_mcp.exceptions import NotFoundError
from ubuntu_mcp.tools import git_tools


def _init_repo(repo_dir):
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True)
    (repo_dir / "app.py").write_text("print('hi')\n")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo_dir, check=True)


async def test_git_status_and_log(workspace):
    _init_repo(workspace / "repo")
    (workspace / "repo" / "app.py").write_text("print('hi')\nprint('changed')\n")

    status = await git_tools.git_status("repo")
    assert any("app.py" in line for line in status["changes"])

    log = await git_tools.git_log("repo", limit=5)
    assert log["count"] == 1
    assert log["commits"][0]["subject"] == "init"


async def test_git_branches_and_current(workspace):
    _init_repo(workspace / "repo2")
    branches = await git_tools.git_branches("repo2")
    current = await git_tools.git_current_branch("repo2")
    assert current["branch"] in branches["branches"]


async def test_git_diff(workspace):
    _init_repo(workspace / "repo3")
    (workspace / "repo3" / "app.py").write_text("print('hi')\nprint('new line')\n")
    diff = await git_tools.git_diff("repo3")
    assert "new line" in diff["diff"]


async def test_non_git_directory_raises(workspace):
    (workspace / "not_a_repo").mkdir()
    with pytest.raises(NotFoundError):
        await git_tools.git_status("not_a_repo")


async def test_missing_directory_raises(workspace):
    with pytest.raises(NotFoundError):
        await git_tools.git_status("does_not_exist")
